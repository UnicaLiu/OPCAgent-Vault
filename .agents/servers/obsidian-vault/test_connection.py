#!/usr/bin/env python3
"""
MCP 连接测试脚本 —— 验证 Codex（或 Claude）能否正常连接 Obsidian Vault MCP Server。

用法:
  python3 test_connection.py

这个脚本模拟一次完整的 MCP 握手，验证三层协议都通。
Codex 那边可以直接运行这个脚本确认环境正确。
"""

import subprocess
import json
import sys
import os
from pathlib import Path

VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", os.getcwd()))
SERVER = VAULT / ".agents/servers/obsidian-vault/server.py"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def info(msg):
    print(f"  {CYAN}→{RESET} {msg}")


def send(proc, msg: dict) -> dict:
    """Send a JSON-RPC message and return the response."""
    line = json.dumps(msg, ensure_ascii=False)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    response_line = proc.stdout.readline()
    return json.loads(response_line)


def main():
    print(f"\n{BOLD}Obsidian Vault MCP · 连接测试{RESET}")
    print(f"Vault: {VAULT}")
    print(f"Server: {SERVER}")
    print()

    if not SERVER.exists():
        print(f"{RED}错误: MCP Server 不存在: {SERVER}{RESET}")
        sys.exit(1)

    # ── 启动 Server ──
    info("启动 MCP Server...")
    proc = subprocess.Popen(
        ["python3", str(SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # ── Layer 1: Initialize ──
        info("Layer 1: initialize 握手...")
        resp = send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "codex-connection-test", "version": "1.0"},
            },
        })

        if resp.get("result", {}).get("serverInfo", {}).get("name") == "obsidian-vault":
            ok(f"Server: {resp['result']['serverInfo']['name']} v{resp['result']['serverInfo']['version']}")
        else:
            fail(f"initialize 失败: {resp}")
            sys.exit(1)

        # ── Layer 2: Tools List ──
        info("Layer 2: tools/list 获取工具清单...")
        resp = send(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })

        tools = resp.get("result", {}).get("tools", [])
        if tools:
            ok(f"获取到 {len(tools)} 个工具:")
            for t in tools:
                print(f"      {t['name']} — {t['description'][:60]}")
        else:
            fail("tools/list 返回空")
            sys.exit(1)

        # ── Layer 3: Tool Call ──
        info("Layer 3: tools/call wiki_stats 获取统计...")
        resp = send(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "wiki_stats", "arguments": {}},
        })

        content = resp.get("result", {}).get("content", [])
        if content:
            text = content[0]["text"]
            stats = json.loads(text)
            ok(f"知识库统计: {stats['total']} 页 (来源:{stats['source']} 实体:{stats['entity']} 概念:{stats['concept']} 对比:{stats['comparison']})")
        else:
            fail(f"wiki_stats 调用失败: {resp}")
            sys.exit(1)

        # ── 完成 ──
        print(f"\n{BOLD}{GREEN}✅ 三层协议全部通过 — MCP 连接正常{RESET}\n")

        # 输出 JSON 格式的结果（方便 Codex 解析）
        print("--- JSON 结果 ---")
        print(json.dumps({
            "status": "ok",
            "server": "obsidian-vault",
            "version": "1.0.0",
            "tools": len(tools),
            "wiki": stats,
        }, ensure_ascii=False, indent=2))

    except Exception as e:
        fail(f"异常: {e}")
        sys.exit(1)

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
