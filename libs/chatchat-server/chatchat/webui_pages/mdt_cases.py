"""病例库：Markdown + YAML frontmatter，放 KB_ROOT/_cases 下。

为什么放这儿：`data/knowledge_base/` 已经在 compose 挂载范围内，Windows 开发机和
纯镜像部署都能直接用，不需要改 compose；同时又不在任何知识库的 content 目录里，
不会被知识库检索当成资料。

一条病例 = 一个 .md 文件，改文件即生效（页面每次渲染重新读取，不用重启容器）：

    ---
    id: prostate_001
    title: 转移性激素敏感性前列腺癌
    disease: 前列腺癌
    difficulty: 高级
    tags: [转移性, 内分泌治疗, 骨转移]
    description: 男性68岁，排尿困难3个月…
    images:
      - path: images/prostate_001_bone_scan.jpg
        caption: 全身骨显像示多发异常浓聚
    ---

    ## 基本信息
    …

影像放 `_cases/images/`，随病例一起走私有 git 仓库同步（见 sync_to_cloud）。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

CASES_KB_NAME = "_cases"
FRONTMATTER_KEYS = ("id", "title", "disease", "difficulty", "tags", "description", "images")


def cases_dir() -> Path:
    from chatchat.settings import Settings  # 延迟导入，避免与启动顺序耦合

    return Path(Settings.basic_settings.KB_ROOT_PATH) / CASES_KB_NAME


def images_dir() -> Path:
    return cases_dir() / "images"


def _safe_name(name: str) -> str:
    """只保留安全字符，避免路径穿越与奇怪文件名。"""
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", (name or "").strip())
    return cleaned.strip("._") or f"case_{datetime.now():%Y%m%d%H%M%S}"


def parse_case_file(path: Path) -> Optional[Dict]:
    """解析单个病例文件；格式不对返回 None（跳过而不是让页面崩）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return None

    try:
        meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None

    case = {k: meta.get(k) for k in FRONTMATTER_KEYS}
    case["id"] = str(case.get("id") or path.stem)
    case["title"] = str(case.get("title") or path.stem)
    case["disease"] = str(case.get("disease") or "未分类")
    case["difficulty"] = str(case.get("difficulty") or "未标注")
    case["tags"] = [str(t) for t in (case.get("tags") or [])]
    case["description"] = str(case.get("description") or "")
    images = case.get("images") or []
    normalized = []
    for item in images:
        if isinstance(item, str):
            normalized.append({"path": item, "caption": Path(item).name})
        elif isinstance(item, dict) and item.get("path"):
            normalized.append(
                {"path": str(item["path"]), "caption": str(item.get("caption") or "")}
            )
    case["images"] = normalized
    case["content"] = "\n".join(lines[end + 1 :]).strip()
    case["file"] = path.name
    return case


def load_cases() -> Dict[str, List[Dict]]:
    """返回 {病种: [病例, ...]}，按标题排序。目录不存在时返回空 dict。"""
    folder = cases_dir()
    grouped: Dict[str, List[Dict]] = {}
    if not folder.is_dir():
        return grouped
    for path in sorted(folder.glob("*.md")):
        case = parse_case_file(path)
        if not case:
            continue
        grouped.setdefault(case["disease"], []).append(case)
    for cases in grouped.values():
        cases.sort(key=lambda c: c["title"])
    return grouped


def case_count() -> int:
    return sum(len(v) for v in load_cases().values())


def dump_case(case: Dict) -> str:
    meta = {
        "id": case.get("id"),
        "title": case.get("title"),
        "disease": case.get("disease"),
        "difficulty": case.get("difficulty"),
        "tags": case.get("tags") or [],
        "description": case.get("description") or "",
    }
    if case.get("images"):
        meta["images"] = case["images"]
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{front}---\n\n{(case.get('content') or '').strip()}\n"


def save_case(case: Dict) -> Path:
    """写回病例文件（新增或覆盖），返回文件路径。"""
    case = dict(case)
    case["id"] = _safe_name(case.get("id") or case.get("title") or "")
    folder = cases_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{case['id']}.md"
    path.write_text(dump_case(case), encoding="utf-8")
    return path


def delete_case(case_id: str) -> bool:
    folder = cases_dir()
    target = folder / f"{_safe_name(case_id)}.md"
    if target.is_file():
        target.unlink()
        return True
    return False


def image_abs_path(rel_path: str) -> Optional[Path]:
    """把 frontmatter 里的相对路径解析为绝对路径，并挡住路径穿越。"""
    if not rel_path:
        return None
    base = cases_dir().resolve()
    try:
        candidate = (base / rel_path).resolve()
    except OSError:
        return None
    if base != candidate and base not in candidate.parents:
        return None
    return candidate


def save_uploaded_images(case_id: str, files: List) -> List[Dict]:
    """保存上传的影像到 images/，返回可直接写进 frontmatter 的 [{path, caption}]。

    files 是 Streamlit 的 UploadedFile 列表；caption 默认取原文件名，之后可在
    病例 md 里直接改。
    """
    out: List[Dict] = []
    if not files:
        return out
    folder = images_dir()
    folder.mkdir(parents=True, exist_ok=True)
    prefix = _safe_name(case_id)
    for f in files:
        raw_name = Path(getattr(f, "name", "image.jpg")).name
        suffix = Path(raw_name).suffix.lower() or ".jpg"
        if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            continue
        stamp = datetime.now().strftime("%H%M%S%f")[:10]
        target = folder / f"{prefix}_{stamp}{suffix}"
        try:
            target.write_bytes(f.getbuffer() if hasattr(f, "getbuffer") else f.read())
        except OSError:
            continue
        out.append({"path": f"images/{target.name}", "caption": Path(raw_name).stem})
    return out


def sync_to_cloud() -> Tuple[bool, str]:
    """把整个病例库（含影像）镜像到私有 git 仓库。"""
    from chatchat.server.knowledge_base.kb_backup import mirror_directory

    return mirror_directory(cases_dir(), CASES_KB_NAME, "病例库")
