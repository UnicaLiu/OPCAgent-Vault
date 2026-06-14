"""
Wiki 页面 CRUD — 所有 wiki/ 写入操作的唯一入口。

原则：
- 每个写入操作都是原子的（完整写入文件）
- 创建/更新后自动维护 index.md 和 log.md
- 校验由 schema.py 在调用前完成
"""

from datetime import date
from pathlib import Path
import shutil
from typing import Optional, List, Dict, Tuple

import schema
import indexer


def create_page(
    vault: Path,
    page_type: str,
    title: str,
    content: str,
    sources: List[str] = None,
    tags: List[str] = None,
    created: str = None,
) -> Tuple[bool, str, Path]:
    """
    创建 wiki 页面。

    返回 (success, message, file_path)
    """
    sources = sources or []
    tags = tags or []

    # 1. 类型校验
    if page_type not in schema.PAGE_TYPES:
        return False, f"无效的页面类型 '{page_type}'", None

    # 2. 文件名生成
    dir_name = schema.TYPE_DIR[page_type]
    if page_type == "source":
        # 保证日期前缀
        if not title.startswith("20"):  # 未带日期
            title = f"{date.today().isoformat()} {title}"
        fname, msg = _sanitize_filename(title)
        if not fname:
            return False, msg, None
    else:
        fname, msg = _sanitize_filename(title)
        if not fname:
            return False, msg, None

    file_path = vault / "wiki" / dir_name / f"{fname}.md"

    # 3. 重复检查
    if file_path.exists():
        return False, f"页面已存在: wiki/{dir_name}/{fname}.md", file_path

    # 4. 拼装内容
    fm = schema.make_frontmatter(page_type, tags, created)

    # 添加 sources 引用（如提供）
    sources_block = ""
    if sources:
        source_links = "\n".join(f"- [[{s}]]" for s in sources)
        sources_block = f"\n**来源**：\n{source_links}\n"

    full_content = f"{fm}\n\n# {title}\n\n{sources_block}\n{content}\n"

    # 5. 写入
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(full_content, encoding="utf-8")

    # 6. 更新 index
    idx_msg = indexer.update_index(vault, page_type, title)

    # 7. 追加日志
    indexer.append_log(vault, "create", f"创建 {schema.TYPE_DIR[page_type]}页: [[{title}]]")

    return True, f"已创建 {schema.TYPE_DIR[page_type]}页: {title}\n{idx_msg}", file_path


def update_page(
    vault: Path,
    relative_path: str,
    new_content: str,
) -> Tuple[bool, str]:
    """
    更新已有 wiki 页面（完整替换内容）。

    relative_path: 如 'wiki/概念/内容判断力.md'
    """
    file_path = vault / relative_path

    if not file_path.exists():
        return False, f"文件不存在: {relative_path}"

    # 保留旧内容作为备份
    backup_path = file_path.with_suffix(".md.bak." + date.today().isoformat())
    shutil.copy2(file_path, backup_path)

    # 更新 updated 字段
    today = date.today().isoformat()
    if new_content.startswith("---"):
        parts = new_content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            if "updated:" in fm_text:
                import re
                fm_text = re.sub(r"updated:\s*\S+", f"updated: {today}", fm_text)
            else:
                fm_text = fm_text.rstrip() + f"\nupdated: {today}"
            new_content = f"---{fm_text}---{parts[2]}"

    file_path.write_text(new_content, encoding="utf-8")

    return True, f"已更新: {relative_path} (备份: {backup_path.name})"


def upsert_page(
    vault: Path,
    relative_path: str,
    new_content: str,
) -> Tuple[bool, str]:
    """
    创建或更新 wiki/ 下的自定义路径页面。

    用于项目型知识区，如 'wiki/OPCAgent/产品报告/xxx.md'。
    """
    safe_path = Path(relative_path)
    if safe_path.is_absolute() or ".." in safe_path.parts:
        return False, f"非法路径: {relative_path}"
    if not safe_path.parts or safe_path.parts[0] != "wiki":
        return False, "upsert-page 只允许写入 wiki/ 下的页面。"
    if safe_path.suffix != ".md":
        return False, "upsert-page 只允许写入 .md 文件。"

    file_path = vault / safe_path
    if file_path.exists():
        return update_page(vault, relative_path, new_content)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(new_content, encoding="utf-8")
    indexer.append_log(vault, "upsert", f"创建自定义页面: {relative_path}")
    return True, f"已创建: {relative_path}"


def delete_page(
    vault: Path,
    relative_path: str,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    安全删除 wiki 页面。

    1. 创建备份
    2. 检查入链（如有关联页面会受影响）
    3. 删除文件
    4. 更新 index
    """
    file_path = vault / relative_path

    if not file_path.exists():
        return False, f"文件不存在: {relative_path}"

    if not force:
        # 检查入链
        backlinks = _find_backlinks(vault, file_path)
        if backlinks:
            bl_list = "\n".join(f"  - {b}" for b in backlinks[:10])
            return False, (
                f"该页面被 {len(backlinks)} 个页面引用，不能直接删除。"
                f"请先清理入链或使用 force=True。\n引用页面:\n{bl_list}"
            )

    # 备份
    backup_path = file_path.with_suffix(".md.deleted." + date.today().isoformat())
    shutil.copy2(file_path, backup_path)

    # 删除
    file_path.unlink()

    # 重建 index
    indexer.rebuild_index(vault)

    indexer.append_log(vault, "delete", f"删除: {relative_path}")

    return True, f"已删除: {relative_path} (备份: {backup_path.name})"


def ingest(
    vault: Path,
    raw_path: str,
    title: str = None,
    summary: str = "",
    tags: List[str] = None,
    entities: List[str] = None,
    concepts: List[str] = None,
) -> Dict:
    """
    完整摄入管道 —— 从 raw 文件到 wiki 知识库。

    这是 MCP Server 最核心的工具。
    由 AI 工具调用，提供已分析好的内容，server 负责建页 + 级联更新。

    参数:
        raw_path: raw 目录下的相对路径
        title: 来源页标题（不含日期前缀）
        summary: 一句话简介
        tags: 标签列表
        entities: 提及的实体列表 [(name, description), ...]
        concepts: 提及的概念列表 [(name, description), ...]

    返回:
        {created: [...], updated: [...], stats: {...}}
    """
    tags = tags or []
    entities = entities or []
    concepts = concepts or []
    result = {"created": [], "updated": [], "stats": {}}

    # 1. 验证 raw 文件存在
    raw_file = vault / "raw" / raw_path
    if not raw_file.exists():
        return {"error": f"raw 文件不存在: raw/{raw_path}"}

    # 2. 创建来源摘要页
    today = date.today().isoformat()
    source_title = title or raw_file.stem
    source_content = _build_source_content(raw_path, summary)

    ok, msg, src_path = create_page(
        vault,
        "source",
        source_title,
        source_content,
        sources=[f"raw/{raw_path}"],
        tags=tags + ["notebooklm-import"] if "notebooklm" in str(raw_path).lower() else tags,
    )

    if not ok:
        return {"error": f"创建来源页失败: {msg}"}

    src_rel = str(src_path.relative_to(vault))
    result["created"].append(src_rel)

    # 3. 处理实体
    for entity_name, entity_desc in entities:
        existing = _find_existing(vault, "entity", entity_name)
        if existing:
            result["updated"].append(str(existing.relative_to(vault)))
        else:
            # 检查是否 ≥2 篇来源提及
            ref_count = _count_source_refs(vault, entity_name) + 1
            if ref_count >= 2:
                ok2, msg2, ent_path = create_page(
                    vault,
                    "entity",
                    entity_name,
                    entity_desc,
                    tags=["entity"],
                )
                if ok2:
                    result["created"].append(str(ent_path.relative_to(vault)))

    # 4. 处理概念
    for concept_name, concept_desc in concepts:
        existing = _find_existing(vault, "concept", concept_name)
        if existing:
            # 添加新来源引用
            result["updated"].append(str(existing.relative_to(vault)))
        else:
            ref_count = _count_source_refs(vault, concept_name) + 1
            if ref_count >= 2:
                ok2, msg2, con_path = create_page(
                    vault,
                    "concept",
                    concept_name,
                    concept_desc,
                    tags=["concept"],
                )
                if ok2:
                    result["created"].append(str(con_path.relative_to(vault)))

    # 5. 日志
    indexer.append_log(vault, "ingest", f"摄入 raw/{raw_path} → {src_rel}")

    # 6. 返回统计
    result["stats"] = indexer.get_stats(vault)

    return result


# ── 内部辅助 ─────────────────────────────────────────────

def _sanitize_filename(name: str) -> Tuple[str, str]:
    """清理文件名中的非法字符"""
    illegal = '<>:"/\\|?*'
    cleaned = name
    for ch in illegal:
        cleaned = cleaned.replace(ch, "-")
    cleaned = cleaned.strip()
    if not cleaned:
        return "", "文件名为空"
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    return cleaned, ""


def _find_existing(vault: Path, page_type: str, title: str) -> Optional[Path]:
    """在 wiki 中查找同名页面"""
    dir_name = schema.TYPE_DIR[page_type]
    # 尝试精确匹配和模糊匹配
    d = vault / "wiki" / dir_name
    if not d.exists():
        return None

    exact = d / f"{title}.md"
    if exact.exists():
        return exact

    # 模糊：遍历所有文件找同名（忽略 frontmatter 差异）
    for f in d.glob("*.md"):
        if f.stem == title:
            return f

    return None


def _count_source_refs(vault: Path, name: str) -> int:
    """统计有多少篇来源摘要页提到了这个名称"""
    sources_dir = vault / "wiki" / "来源"
    if not sources_dir.exists():
        return 0

    count = 0
    for f in sources_dir.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        # 简单出现次数统计（作为近似）
        if name in content:
            count += 1

    return count


def _find_backlinks(vault: Path, target: Path) -> List[str]:
    """查找所有链接到 target 的页面"""
    backlinks = []
    target_name = target.stem

    wiki_dir = vault / "wiki"
    if not wiki_dir.exists():
        return backlinks

    for md in wiki_dir.rglob("*.md"):
        if md == target:
            continue
        content = md.read_text(encoding="utf-8")
        if f"[[{target_name}]]" in content or f"[[{target_name}|" in content:
            backlinks.append(str(md.relative_to(vault)))

    return backlinks


def _build_source_content(raw_path: str, summary: str = "") -> str:
    """构建来源摘要页的正文内容"""
    parts = []
    parts.append(f"> 原始资料：[[raw/{raw_path}]]\n")
    if summary:
        parts.append(f"**摘要**：{summary}\n")
    parts.append("## 要点\n")
    parts.append("（待补充）\n")
    return "\n".join(parts)
