#!/usr/bin/env python3
"""
Obsidian Vault MCP Server — JSON-RPC 2.0 over stdio.

将 Obsidian 知识库的 wiki/ 操作暴露为 MCP 工具，
供 Claude Code、Codex 等 AI 工具调用。

启动方式:
  python3 server.py                    # MCP stdio 模式
  python3 server.py --cli <command>    # CLI 模式（给 Codex 降级使用）

环境变量:
  OBSIDIAN_VAULT_PATH  — vault 根目录（默认: 当前目录）
"""

import json
import sys
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List

# 添加父目录到 path 以支持 from . import
sys.path.insert(0, str(Path(__file__).parent))

from indexer import append_log, get_log, get_stats, rebuild_index, lint, search
from wiki import create_page, update_page, upsert_page, delete_page, ingest

# ── 配置 ────────────────────────────────────────────────

VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", os.getcwd())).resolve()

# ── 工具定义 ────────────────────────────────────────────

TOOLS = [
    {
        "name": "wiki_stats",
        "description": "获取 wiki 知识库统计：来源、实体、概念、对比页数量。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "wiki_search",
        "description": "全文搜索 wiki/ 目录，返回匹配的页面和上下文片段。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "wiki_get_log",
        "description": "获取最近的操作日志。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "获取最近 n 条日志（默认 10）",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "wiki_lint",
        "description": "全库健康检查：断裂链接、index 同步、孤儿页面、frontmatter 完整性。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "wiki_read_page",
        "description": "读取 wiki/ 或 raw/ 中的文件内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对路径（如 'wiki/概念/内容判断力.md' 或 'raw/钟老师聊TK/xxx.md'）",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "wiki_list_raw",
        "description": "列出 raw/ 目录下的文件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "可选 glob 过滤（如 '钟老师*'）",
                },
            },
            "required": [],
        },
    },
    {
        "name": "wiki_create_page",
        "description": "创建新的 wiki 页面。自动维护 index.md 和 log.md。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "页面类型: entity / concept / source / comparison",
                    "enum": ["entity", "concept", "source", "comparison"],
                },
                "title": {
                    "type": "string",
                    "description": "页面标题（来源页会自动添加日期前缀）",
                },
                "content": {
                    "type": "string",
                    "description": "页面正文（Markdown，不含 frontmatter）",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "来源引用列表（如 ['wiki/来源/xxx']）",
                },
            },
            "required": ["type", "title", "content"],
        },
    },
    {
        "name": "wiki_update_page",
        "description": "更新已有 wiki 页面内容（完整替换）。自动创建备份。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对路径（如 'wiki/概念/内容判断力.md'）",
                },
                "content": {
                    "type": "string",
                    "description": "新的完整页面内容（含 frontmatter）",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "wiki_upsert_page",
        "description": "创建或更新 wiki/ 下的自定义路径页面（完整替换）。自动创建目录，更新时自动备份。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对路径（如 'wiki/OPCAgent/产品报告/产品A.md'）",
                },
                "content": {
                    "type": "string",
                    "description": "新的完整页面内容（含 frontmatter）",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "wiki_delete_page",
        "description": "安全删除 wiki 页面：检查入链 → 备份 → 删除 → 重建 index。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要删除的文件相对路径",
                },
                "force": {
                    "type": "boolean",
                    "description": "强制删除（忽略入链检查）",
                    "default": False,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "wiki_ingest",
        "description": (
            "完整摄入管道：从 raw 文件创建来源摘要页 → 检测实体/概念（≥2 来源则创建）"
            "→ 更新 index.md → 追加 log.md。一步完成。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "raw_path": {
                    "type": "string",
                    "description": "raw 目录下的相对路径（如 '钟老师聊TK/76344851.md'）",
                },
                "title": {
                    "type": "string",
                    "description": "来源页标题（无日期前缀）",
                },
                "summary": {
                    "type": "string",
                    "description": "一句话简介",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                    "description": "提及的实体 [{name, description}]",
                },
                "concepts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                    "description": "提及的概念 [{name, description}]",
                },
            },
            "required": ["raw_path", "title"],
        },
    },
    {
        "name": "wiki_rebuild_index",
        "description": "从文件系统完全重建 index.md（修复不同步时使用）。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ── 工具调用分发 ────────────────────────────────────────

def call_tool(name: str, arguments: Dict[str, Any]) -> str:
    """执行工具并返回文本结果"""

    if name == "wiki_stats":
        stats = get_stats(VAULT_PATH)
        return json.dumps(stats, ensure_ascii=False)

    elif name == "wiki_search":
        return search(VAULT_PATH, arguments["query"])

    elif name == "wiki_get_log":
        n = arguments.get("n", 10)
        return get_log(VAULT_PATH, n)

    elif name == "wiki_lint":
        return lint(VAULT_PATH)

    elif name == "wiki_read_page":
        file_path = VAULT_PATH / arguments["path"]
        if not file_path.exists():
            return f"文件不存在: {arguments['path']}"
        return file_path.read_text(encoding="utf-8")

    elif name == "wiki_list_raw":
        raw_dir = VAULT_PATH / "raw"
        pattern = arguments.get("pattern", "*")
        if not raw_dir.exists():
            return "raw/ 目录不存在或为空"
        files = sorted(raw_dir.rglob(pattern))
        # 只显示文件，过滤目录
        result = []
        for f in files:
            if f.is_file() and not f.name.startswith("."):
                result.append(str(f.relative_to(VAULT_PATH)))
        if not result:
            return f"raw/ 中没有匹配 '{pattern}' 的文件"
        return "\n".join(result[:100])  # 最多 100 个

    elif name == "wiki_create_page":
        ok, msg, path = create_page(
            VAULT_PATH,
            arguments["type"],
            arguments["title"],
            arguments.get("content", ""),
            arguments.get("sources", []),
            arguments.get("tags", []),
        )
        if ok:
            return msg
        return f"错误: {msg}"

    elif name == "wiki_update_page":
        ok, msg = update_page(
            VAULT_PATH,
            arguments["path"],
            arguments["content"],
        )
        return msg

    elif name == "wiki_upsert_page":
        ok, msg = upsert_page(
            VAULT_PATH,
            arguments["path"],
            arguments["content"],
        )
        return msg

    elif name == "wiki_delete_page":
        ok, msg = delete_page(
            VAULT_PATH,
            arguments["path"],
            arguments.get("force", False),
        )
        return msg

    elif name == "wiki_ingest":
        result = ingest(
            VAULT_PATH,
            arguments["raw_path"],
            arguments.get("title"),
            arguments.get("summary", ""),
            arguments.get("tags", []),
            arguments.get("entities", []),
            arguments.get("concepts", []),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    elif name == "wiki_rebuild_index":
        return rebuild_index(VAULT_PATH)

    else:
        return f"未知工具: {name}"


# ── MCP JSON-RPC 2.0 协议 ──────────────────────────────

def _send(response: Dict):
    """向 stdout 发送 JSON-RPC 响应"""
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _log(msg: str):
    """向 stderr 写日志（不干扰 stdio 协议）"""
    print(f"[MCP Server] {msg}", file=sys.stderr, flush=True)


def handle_request(req: Dict) -> Dict:
    """处理单个 JSON-RPC 请求"""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    # ── initialize ──
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "obsidian-vault",
                    "version": "1.0.0",
                },
            },
        }

    # ── tools/list ──
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS,
            },
        }

    # ── tools/call ──
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            result_text = call_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text,
                        }
                    ],
                },
            }
        except Exception as e:
            _log(f"Tool error [{tool_name}]: {traceback.format_exc()}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"工具执行错误: {str(e)}",
                        }
                    ],
                    "isError": True,
                },
            }

    # ── notifications/initialized ──
    elif method == "notifications/initialized":
        # 客户端确认初始化完成，无需响应
        return None

    # ── ping ──
    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }


def run_mcp():
    """MCP stdio 主循环"""
    _log(f"Starting MCP server, vault: {VAULT_PATH}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _log(f"JSON parse error: {e}")
            continue

        response = handle_request(request)
        if response is not None:
            _send(response)


# ── CLI 降级模式 ───────────────────────────────────────

def run_cli():
    """命令行模式（给不支持 MCP 的工具降级使用）"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Obsidian Vault — 知识库管理 CLI",
        epilog="环境变量 OBSIDIAN_VAULT_PATH 设置 vault 路径（默认当前目录）",
    )

    subs = parser.add_subparsers(dest="command", help="操作命令")

    # stats
    subs.add_parser("stats", help="获取 wiki 统计")

    # search
    p = subs.add_parser("search", help="全文搜索")
    p.add_argument("query", help="搜索关键词")

    # log
    p = subs.add_parser("log", help="查看操作日志")
    p.add_argument("-n", type=int, default=10, help="最近 n 条")

    # lint
    subs.add_parser("lint", help="全库健康检查")

    # read
    p = subs.add_parser("read", help="读取文件")
    p.add_argument("path", help="文件相对路径")

    # list-raw
    p = subs.add_parser("list-raw", help="列出 raw/ 文件")
    p.add_argument("pattern", nargs="?", default="*", help="过滤模式")

    # create-page
    p = subs.add_parser("create-page", help="创建 wiki 页面")
    p.add_argument("type", choices=["entity", "concept", "source", "comparison"])
    p.add_argument("title", help="页面标题")
    p.add_argument("--content", default="", help="正文内容")
    p.add_argument("--tags", nargs="*", default=[], help="标签")
    p.add_argument("--sources", nargs="*", default=[], help="来源引用")

    # update-page
    p = subs.add_parser("update-page", help="更新页面")
    p.add_argument("path", help="文件路径")
    p.add_argument("--content", required=True, help="新内容（或 - 从 stdin 读取）")

    # upsert-page
    p = subs.add_parser("upsert-page", help="创建或更新 wiki/ 下的自定义路径页面")
    p.add_argument("path", help="文件路径")
    p.add_argument("--content", required=True, help="新内容（或 - 从 stdin 读取）")

    # delete-page
    p = subs.add_parser("delete-page", help="删除页面")
    p.add_argument("path", help="文件路径")
    p.add_argument("--force", action="store_true", help="强制删除")

    # ingest
    p = subs.add_parser("ingest", help="完整摄入 raw 文件")
    p.add_argument("raw_path", help="raw 文件路径")
    p.add_argument("--title", required=True, help="来源页标题")
    p.add_argument("--summary", default="", help="一句话简介")
    p.add_argument("--tags", nargs="*", default=[], help="标签")

    # rebuild-index
    subs.add_parser("rebuild-index", help="重建 index.md")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 分发命令
    cmd = args.command

    if cmd == "stats":
        print(json.dumps(get_stats(VAULT_PATH), ensure_ascii=False, indent=2))

    elif cmd == "search":
        print(search(VAULT_PATH, args.query))

    elif cmd == "log":
        print(get_log(VAULT_PATH, args.n))

    elif cmd == "lint":
        print(lint(VAULT_PATH))

    elif cmd == "read":
        file_path = VAULT_PATH / args.path
        if not file_path.exists():
            print(f"文件不存在: {args.path}")
        else:
            print(file_path.read_text(encoding="utf-8"))

    elif cmd == "list-raw":
        raw_dir = VAULT_PATH / "raw"
        if raw_dir.exists():
            for f in sorted(raw_dir.rglob(args.pattern)):
                if f.is_file() and not f.name.startswith("."):
                    print(str(f.relative_to(VAULT_PATH)))

    elif cmd == "create-page":
        content = args.content
        if content == "-":
            content = sys.stdin.read()
        ok, msg, _ = create_page(
            VAULT_PATH, args.type, args.title,
            content, args.sources, args.tags,
        )
        print(msg)

    elif cmd == "update-page":
        content = args.content
        if content == "-":
            content = sys.stdin.read()
        ok, msg = update_page(VAULT_PATH, args.path, content)
        print(msg)

    elif cmd == "upsert-page":
        content = args.content
        if content == "-":
            content = sys.stdin.read()
        ok, msg = upsert_page(VAULT_PATH, args.path, content)
        print(msg)

    elif cmd == "delete-page":
        ok, msg = delete_page(VAULT_PATH, args.path, args.force)
        print(msg)

    elif cmd == "ingest":
        result = ingest(
            VAULT_PATH, args.raw_path, args.title,
            args.summary, args.tags, [], [],
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "rebuild-index":
        print(rebuild_index(VAULT_PATH))


# ── 入口 ────────────────────────────────────────────────

if __name__ == "__main__":
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        run_cli()
    else:
        run_mcp()
