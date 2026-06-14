"""
Wiki Schema — 从 CLAUDE.md 编码为可执行的校验规则。

所有 wiki/ 写入操作都经由此模块校验，不合规的直接拒绝。
"""

from datetime import datetime, date
from pathlib import Path
import re
from typing import Optional, List, Dict, Tuple

# ── 页面类型 ──────────────────────────────────────────

PAGE_TYPES = ["entity", "concept", "source", "comparison"]

TYPE_DIR = {
    "entity": "实体",
    "concept": "概念",
    "source": "来源",
    "comparison": "对比",
}

# ── Frontmatter 模板 ──────────────────────────────────

def make_frontmatter(page_type: str, tags: List[str], created: str = None) -> str:
    """生成标准 YAML frontmatter"""
    if created is None:
        created = date.today().isoformat()
    tags_str = ", ".join(tags)
    return f"""---
type: {page_type}
tags: [{tags_str}]
created: {created}
updated: {created}
---"""


# ── 文件名校验 ─────────────────────────────────────────

def validate_source_filename(filename: str) -> Tuple[bool, str]:
    """
    来源页文件名必须以 YYYY-MM-DD 开头。
    返回 (is_valid, error_message)
    """
    name = Path(filename).stem
    if re.match(r"^\d{4}-\d{2}-\d{2}\s", name):
        return True, ""
    return False, "来源页文件名必须以 YYYY-MM-DD 开头（如 '2026-05-14 标题.md'）"


# ── 创建时机规则 ───────────────────────────────────────

def check_creation_threshold(
    page_type: str,
    ref_count: int,
    vault_path: Path,
) -> Tuple[bool, str]:
    """
    检查是否满足创建条件（Karpathy 自下而上原则）：
    - entity / concept / comparison: 必须 ≥2 篇不同来源提及
    - source: 始终允许
    """
    if page_type == "source":
        return True, ""
    if ref_count >= 2:
        return True, ""
    type_cn = TYPE_DIR.get(page_type, page_type)
    return False, (
        f"创建 {type_cn} 页需要 ≥2 篇不同来源提及，当前只有 {ref_count} 篇。"
        f"请先在来源摘要页中列出该 {type_cn}，等第二篇来源出现后再创建。"
    )


# ── Frontmatter 校验 ──────────────────────────────────

def validate_frontmatter(content: str) -> Tuple[bool, str, dict]:
    """
    校验已有页面的 frontmatter。
    返回 (is_valid, error_message, parsed_dict)
    """
    if not content.startswith("---"):
        return False, "缺少 YAML frontmatter（必须以 --- 开头）", {}

    # 找第二个 ---
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False, "frontmatter 未闭合（缺少结尾的 ---）", {}

    fm_text = parts[1].strip()
    fm = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()

    # 必须字段
    required = ["type", "tags", "created"]
    missing = [k for k in required if k not in fm]
    if missing:
        return False, f"缺少必需字段: {', '.join(missing)}", fm

    # type 值校验
    if fm.get("type", "").strip() not in PAGE_TYPES:
        return False, f"type 值必须是 {' / '.join(PAGE_TYPES)} 之一", fm

    return True, "", fm


# ── Wikilink 检查 ──────────────────────────────────────

WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")


def extract_wikilinks(content: str) -> List[str]:
    """提取内容中所有的 wiki-link 目标"""
    return [m.group(1).strip() for m in WIKILINK_PATTERN.finditer(content)]


def check_wikilinks(vault_path: Path, content: str) -> List[str]:
    """
    检查 wikilink 目标是否存在。返回断裂链接列表。
    """
    broken = []
    targets = extract_wikilinks(content)
    seen = set()

    for target in targets:
        if target in seen:
            continue
        seen.add(target)

        # 尝试多种路径解析
        resolved = _resolve_wikilink(vault_path, target)
        if resolved is None:
            broken.append(target)

    return broken


def _resolve_wikilink(vault_path: Path, target: str) -> Optional[Path]:
    """尝试将 wikilink 目标解析为实际文件路径"""
    # 去掉开头的 wiki/ 如果有（非标准链接）
    clean = target.removeprefix("wiki/").removeprefix("/")

    candidates = [
        vault_path / f"{clean}.md",
        vault_path / "wiki" / f"{clean}.md",
        vault_path / "wiki" / "实体" / f"{clean}.md",
        vault_path / "wiki" / "概念" / f"{clean}.md",
        vault_path / "wiki" / "来源" / f"{clean}.md",
        vault_path / "wiki" / "对比" / f"{clean}.md",
        vault_path / "raw" / f"{clean}.md",
        vault_path / f"raw/{clean}",
        vault_path / clean,  # raw 文件可能无扩展名
    ]

    # 如果 target 本身已包含路径，也直接试
    candidates.insert(0, vault_path / f"{clean}.md")

    for c in candidates:
        if c.exists():
            return c

    return None


# ── Index 同步检查 ─────────────────────────────────────

def count_wiki_files(vault_path: Path) -> Dict[str, int]:
    """扫描 wiki/ 目录，统计各类型页面数"""
    wiki = vault_path / "wiki"
    counts = {"source": 0, "entity": 0, "concept": 0, "comparison": 0}

    dir_map = {
        "来源": "source",
        "实体": "entity",
        "概念": "concept",
        "对比": "comparison",
    }

    for dir_name, type_key in dir_map.items():
        d = wiki / dir_name
        if d.exists():
            counts[type_key] = len(list(d.glob("*.md")))

    return counts
