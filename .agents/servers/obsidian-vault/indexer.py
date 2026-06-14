"""
Index & Log 自动维护。

原则：
- 每次 wiki 页面创建/删除后，自动更新 index.md
- 每次操作后，自动追加 log.md
- 提供重建和校验功能
"""

from datetime import date, datetime
from pathlib import Path
import re
from typing import Dict, List, Tuple

import schema


# ── Log 操作 ───────────────────────────────────────────

def append_log(vault: Path, operation: str, details: str) -> str:
    """
    追加操作日志到 wiki/log.md。

    operation: init / ingest / query / lint / update / create / delete
    details: 操作说明（多行用 \n 分隔）
    """
    log_path = vault / "wiki" / "log.md"

    # 确保存在
    if not log_path.exists():
        _init_log(log_path)

    today = date.today().isoformat()
    lines = details.strip().split("\n")
    bullets = "\n".join(f"- {line.strip()}" for line in lines if line.strip())

    entry = f"\n## [{today}] {operation} | {lines[0][:60]}\n\n{bullets}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

    return f"已追加日志: [{today}] {operation}"


def get_log(vault: Path, n: int = 10) -> str:
    """获取最近 n 条日志"""
    log_path = vault / "wiki" / "log.md"
    if not log_path.exists():
        return "（日志文件不存在）"

    content = log_path.read_text(encoding="utf-8")
    entries = re.split(r"\n## \[", content)
    if len(entries) <= 1:
        return content

    # 第一个是 log header，后面的每条是 "YYYY-MM-DD] ..."
    recent = entries[-n:]
    result = entries[0]  # header
    for e in recent:
        result += "\n## [" + e

    return result


def _init_log(log_path: Path):
    """初始化日志文件"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    log_path.write_text(f"""---
type: concept
tags: [meta, log]
created: {today}
updated: {today}
---

# Operation Log — 操作日志

> 仅追加。记录所有 wiki 操作。

---
""", encoding="utf-8")


# ── Index 操作 ─────────────────────────────────────────

def update_index(vault: Path, page_type: str, title: str) -> str:
    """
    在 index.md 中添加新页面条目，更新 stats。

    返回操作信息。
    """
    index_path = vault / "wiki" / "index.md"
    if not index_path.exists():
        return _init_index(vault)

    content = index_path.read_text(encoding="utf-8")
    type_cn = schema.TYPE_DIR[page_type]

    # 检查是否已存在
    if f"[[{title}]]" in content:
        return "（index 中已存在，跳过）"

    # 在对应的 ## section 中插入
    section_marker = f"## {type_cn}"
    if section_marker not in content:
        # section 不存在，追加新 section
        new_row = _build_index_row(page_type, title)
        content = content.rstrip() + f"\n\n## {type_cn}\n\n{new_row}\n"
    else:
        # 在 section 末尾插入
        new_row = _build_index_row(page_type, title)
        # 找到该 section 的结束位置（下一个 ## 或文件尾）
        sections = re.split(r"(^## )", content, flags=re.MULTILINE)
        new_content = ""
        found = False
        inserted = False
        for i, part in enumerate(sections):
            if part.startswith("## ") and type_cn in part:
                found = True
            if found and not inserted:
                if part.startswith("## ") and type_cn not in part:
                    # 下一个 section 开始，在此前插入
                    new_content = new_content.rstrip() + f"\n{new_row}\n\n" + part
                    inserted = True
                    found = False
                    continue
            new_content += part
        if not inserted:
            new_content = new_content.rstrip() + f"\n{new_row}\n"

        content = new_content

    # 更新 stats
    content = _update_stats(content, vault)

    index_path.write_text(content, encoding="utf-8")
    return f"已更新 index.md: {type_cn} → {title}"


def rebuild_index(vault: Path) -> str:
    """
    从文件系统完全重建 index.md。
    用于修复 index 与实际文件不同步的情况。
    """
    wiki = vault / "wiki"
    if not wiki.exists():
        return "wiki/ 目录不存在"

    # 收集所有页面
    pages = {"来源": [], "实体": [], "概念": [], "对比": []}
    for dir_name in pages:
        d = wiki / dir_name
        if d.exists():
            for md in sorted(d.glob("*.md")):
                pages[dir_name].append(md.stem)

    # 计算 stats
    total = sum(len(v) for v in pages.values())
    today = date.today().isoformat()

    # 构建 index
    lines = [
        "---",
        "type: concept",
        "tags: [meta, index]",
        f"created: {today}",
        f"updated: {today}",
        "---",
        "",
        "# Wiki Index — 知识库索引",
        "",
        "> 这是整个知识库的内容索引。通过 MCP Server 自动维护。",
        "",
        "## Stats",
        "",
        f"- **来源摘要**：{len(pages['来源'])} 篇",
        f"- **实体页**：{len(pages['实体'])} 个",
        f"- **概念页**：{len(pages['概念'])} 个",
        f"- **对比页**：{len(pages['对比'])} 个",
        f"- **总计**：{total} 个页面",
        f"- **最后更新**：{today}",
        "",
        "---",
    ]

    for dir_name, items in pages.items():
        lines.append(f"\n## {dir_name}\n")
        if items:
            for item in items:
                lines.append(f"| [[wiki/{dir_name}/{item}]] | （待补充简介） | — |")
        else:
            lines.append("| （暂无） | — | — |")
        lines.append("")

    content = "\n".join(lines)

    index_path = wiki / "index.md"
    index_path.write_text(content, encoding="utf-8")

    return f"已重建 index.md: {total} 个页面"


def get_stats(vault: Path) -> Dict[str, int]:
    """获取当前 wiki 统计"""
    counts = schema.count_wiki_files(vault)
    counts["total"] = sum(counts.values())
    return counts


def _update_stats(content: str, vault: Path) -> str:
    """更新 index.md 中的 Stats 数字"""
    counts = schema.count_wiki_files(vault)
    total = sum(counts.values())
    today = date.today().isoformat()

    content = re.sub(
        r"-\s+\*\*来源摘要\*\*：\d+ 篇",
        f"- **来源摘要**：{counts['source']} 篇",
        content,
    )
    content = re.sub(
        r"-\s+\*\*实体页\*\*：\d+ 个",
        f"- **实体页**：{counts['entity']} 个",
        content,
    )
    content = re.sub(
        r"-\s+\*\*概念页\*\*：\d+ 个",
        f"- **概念页**：{counts['concept']} 个",
        content,
    )
    content = re.sub(
        r"-\s+\*\*对比页\*\*：\d+ 个",
        f"- **对比页**：{counts['comparison']} 个",
        content,
    )
    content = re.sub(
        r"-\s+\*\*总计\*\*：\d+ 个页面",
        f"- **总计**：{total} 个页面",
        content,
    )
    content = re.sub(
        r"-\s+\*\*最后更新\*\*：\S+",
        f"- **最后更新**：{today}",
        content,
    )

    return content


def _init_index(vault: Path) -> str:
    """首次创建 index.md"""
    result = rebuild_index(vault)
    return f"已初始化 index.md\n{result}"


def _build_index_row(page_type: str, title: str) -> str:
    """生成 index 表格行"""
    type_cn = schema.TYPE_DIR[page_type]
    return f"| [[wiki/{type_cn}/{title}]] | （待补充简介） | — |"


# ── Lint 检查 ───────────────────────────────────────────

def lint(vault: Path) -> str:
    """
    全库健康检查。返回检查报告。

    检查项:
    - index.md 与文件系统是否同步
    - 断裂 wikilinks
    - 孤儿页面（无入链）
    - frontmatter 完整性
    """
    wiki = vault / "wiki"
    if not wiki.exists():
        return "wiki/ 目录不存在"

    issues = []
    warnings = []

    # 1. 检查 index 同步
    actual = schema.count_wiki_files(vault)
    index_content = (wiki / "index.md").read_text(encoding="utf-8") if (wiki / "index.md").exists() else ""

    for type_key, count in actual.items():
        pattern = {
            "source": r"来源摘要.*?(\d+)",
            "entity": r"实体页.*?(\d+)",
            "concept": r"概念页.*?(\d+)",
            "comparison": r"对比页.*?(\d+)",
        }.get(type_key)
        if pattern:
            m = re.search(pattern, index_content)
            if m and int(m.group(1)) != count:
                issues.append(f"index stats 不同步: {type_key} (index: {m.group(1)}, actual: {count})")

    total_actual = sum(actual.values())
    m = re.search(r"总计.*?(\d+)", index_content)
    if m and int(m.group(1)) != total_actual:
        issues.append(f"index total 不同步: index={m.group(1)}, actual={total_actual}")

    # 2. 检查断裂 wikilinks
    all_links = {}
    for md in wiki.rglob("*.md"):
        if md.name in ("index.md", "log.md"):
            continue
        content = md.read_text(encoding="utf-8")
        targets = schema.extract_wikilinks(content)
        all_links[str(md.relative_to(vault))] = targets

    for src, targets in all_links.items():
        for tgt in targets:
            if schema._resolve_wikilink(vault, tgt) is None:
                issues.append(f"断链: {src} → [[{tgt}]]")

    # 3. 检查孤儿页面
    all_targets = set()
    for targets in all_links.values():
        all_targets.update(targets)

    for md in wiki.rglob("*.md"):
        if md.name in ("index.md", "log.md"):
            continue
        stem = md.stem
        rel = str(md.relative_to(vault))
        # 检查是否有页面链接到它
        has_inlink = False
        for targets in all_links.values():
            if stem in targets or f"wiki/{md.parent.name}/{stem}" in targets:
                has_inlink = True
                break
        if not has_inlink and md.parent.name != "来源":
            # 实体/概念/对比 页面无入链 → 孤儿
            warnings.append(f"孤儿页面（无入链）: {rel}")

    # 4. 检查 frontmatter
    for md in wiki.rglob("*.md"):
        if md.name in ("index.md", "log.md"):
            continue
        content = md.read_text(encoding="utf-8")
        valid, err, _ = schema.validate_frontmatter(content)
        if not valid:
            warnings.append(f"frontmatter 问题: {md.relative_to(vault)} — {err}")

    # 组装报告
    lines = [f"# Wiki Lint Report — {date.today()}\n"]
    lines.append(f"## Issues ({len(issues)})\n")
    if issues:
        for i in issues:
            lines.append(f"- ❌ {i}")
    else:
        lines.append("- ✅ 无问题")

    lines.append(f"\n## Warnings ({len(warnings)})\n")
    if warnings:
        for w in warnings:
            lines.append(f"- ⚠️ {w}")
    else:
        lines.append("- ✅ 无警告")

    lines.append(f"\n## Stats\n")
    lines.append(f"- 来源: {actual['source']} | 实体: {actual['entity']} | 概念: {actual['concept']} | 对比: {actual['comparison']}")
    lines.append(f"- 总计: {total_actual} 个页面")

    return "\n".join(lines)


def search(vault: Path, query: str) -> str:
    """
    全文搜索 wiki/ 目录。
    返回匹配的文件列表和上下文片段。
    """
    wiki = vault / "wiki"
    if not wiki.exists():
        return "wiki/ 目录不存在"

    results = []
    for md in sorted(wiki.rglob("*.md")):
        try:
            content = md.read_text(encoding="utf-8")
            if query.lower() in content.lower():
                rel_path = str(md.relative_to(vault))
                # 提取匹配行上下文
                lines = content.split("\n")
                match_lines = []
                for i, line in enumerate(lines):
                    if query.lower() in line.lower():
                        ctx_start = max(0, i - 1)
                        ctx_end = min(len(lines), i + 2)
                        snippet = "\n".join(lines[ctx_start:ctx_end])
                        match_lines.append(f"  L{i+1}: {snippet[:120]}")
                results.append((rel_path, match_lines[:3]))  # 最多3个匹配片段
        except Exception:
            continue

    if not results:
        return f"未找到包含 '{query}' 的页面"

    output = [f"搜索 '{query}' — {len(results)} 个匹配:\n"]
    for path, snippets in results[:20]:  # 最多20个文件
        output.append(f"## [[{path}]]\n")
        for s in snippets:
            output.append(s + "\n")

    return "\n".join(output)
