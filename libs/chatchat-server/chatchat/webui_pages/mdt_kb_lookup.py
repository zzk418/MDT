"""MDT 知识库显式检索（不依赖 embedding）。

当前知识库只有几篇文档、合计一万多字，整篇放进上下文完全放得下，所以不走
向量检索：直接读 content 目录，按提问里的病种/主题关键词路由到相关文档，整篇
注入。好处是不需要 ollama / 嵌入模型（内网部署少一个依赖），知识库文件改了
立即生效（不用重建索引），引用来源也是确定的。

语料变大以后（放入指南全文、病例库，达到十万字/上千 chunk 量级），把
select_context() 换成向量检索或 BM25 混合即可，调用方（mdt_teaching.py）不用改。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

# 自动路由时最多注入几篇文档
MAX_AUTO_DOCS = 3
# 注入上下文的字符上限（防止知识库变大后把请求撑爆）
MAX_CONTEXT_CHARS = 40000

# (文档名包含的片段, 触发关键词)。关键词与提问都转小写后做子串匹配。
ROUTES: List[Tuple[str, Tuple[str, ...]]] = [
    (
        "03_前列腺癌",
        ("前列腺", "psa", "gleason", "isup", "mhspc", "crpc", "去势", "阿比特龙",
         "恩扎鲁胺", "阿帕他胺", "达罗他胺", "多西他赛", "镭-223", "psma",
         "奥拉帕利", "骨转移", "主动监测", "根治性前列腺切除"),
    ),
    (
        "04_膀胱癌",
        ("膀胱", "bcg", "turbt", "nmibc", "mibc", "膀胱灌注", "尿流改道",
         "新膀胱", "顺铂", "膀胱切除", "原位癌", "保膀胱"),
    ),
    (
        "05_肾癌",
        ("肾癌", "肾细胞癌", "rcc", "肾部分", "肾切除", "消融", "r.e.n.a.l",
         "renal", "imdc", "上尿路", "utuc", "输尿管", "减瘤", "肾输尿管"),
    ),
    (
        "01_泌尿肿瘤mdt组织运行",
        ("组织架构", "组织运行", "流程", "会前", "资料准备", "准入", "主持人",
         "协调员", "会议记录", "职责", "质控", "随访安排"),
    ),
    (
        "02_泌尿肿瘤mdt病例评估",
        ("病例摘要", "风险分层", "治疗目标", "提问清单", "首选方案", "备选方案",
         "讨论问题", "评估框架", "资料缺口"),
    ),
    (
        "06_泌尿肿瘤mdt论文证据",
        ("论文", "证据等级", "文献", "系统综述", "荟萃", "pubmed", "随机对照",
         "研究局限", "证据边界"),
    ),
]


def _kb_content_dir(kb_name: str) -> Path:
    from chatchat.settings import Settings  # 延迟导入，避免与 webui 启动顺序耦合

    return Path(Settings.basic_settings.KB_ROOT_PATH) / kb_name / "content"


def read_documents(kb_name: str) -> List[Tuple[Path, str]]:
    """读取知识库 content 下的全部 markdown，按文件名排序。"""
    folder = _kb_content_dir(kb_name)
    if not folder.is_dir():
        return []
    docs: List[Tuple[Path, str]] = []
    for path in sorted(folder.glob("*.md")):
        try:
            docs.append((path, path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return docs


def _score(question: str, filename: str) -> Tuple[int, List[str]]:
    """按关键词给单篇文档打分；命中的词越长越具体，权重越高。"""
    lowered = question.lower()
    for fragment, keywords in ROUTES:
        if fragment.lower() not in filename.lower():
            continue
        hits = [kw for kw in keywords if kw in lowered]
        return sum(len(kw) for kw in hits), hits
    return 0, []


def _hit_sections(text: str, hits: List[str]) -> List[str]:
    """找出命中了提问关键词的小节标题，用于展示引用出处。

    标题和正文都参与匹配——像 BCG、NMIBC 这类词通常只出现在小节正文里。
    """
    if not hits:
        return []

    titles: List[str] = []
    current_title = None
    current_lines: List[str] = []

    def flush() -> None:
        if current_title is None:
            return
        body = "\n".join(current_lines).lower()
        if any(hit in current_title.lower() or hit in body for hit in hits):
            titles.append(current_title)

    for line in text.splitlines():
        match = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if match:
            flush()
            current_title = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return titles[:4]


def select_context(
    question: str, kb_name: str, scope: str = "auto"
) -> Tuple[str, List[Dict]]:
    """按提问选资料并拼成可注入的上下文。

    返回 (context_text, sources)；sources 每项形如
    {"file": "03_前列腺癌MDT决策框架.md", "sections": ["4. 去势抵抗性前列腺癌"]}。
    scope="all" 时不做路由，直接把全部文档注入。
    """
    docs = read_documents(kb_name)
    if not docs:
        return "", []

    if scope == "all":
        picked = [(path, text, []) for path, text in docs]
    else:
        scored = []
        for path, text in docs:
            score, hits = _score(question, path.name)
            if score > 0:
                scored.append((score, path, text, hits))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored:
            picked = [(path, text, hits) for _, path, text, hits in scored[:MAX_AUTO_DOCS]]
        else:
            # 没命中任何病种/主题关键词就全量兜底：体量小，宁可多给不可漏
            picked = [(path, text, []) for path, text in docs]

    blocks: List[str] = []
    sources: List[Dict] = []
    used = 0
    for path, text, hits in picked:
        if blocks and used + len(text) > MAX_CONTEXT_CHARS:
            break
        used += len(text)
        blocks.append(f"=== 资料：{path.name} ===\n{text}")
        sources.append({"file": path.name, "sections": _hit_sections(text, hits)})

    header = (
        "以下是从 MDT 知识库中选取的资料。请优先依据这些资料回答；"
        "引用时写明出自哪份文档的哪一节；资料没有覆盖的内容要明确说明"
        "“知识库中未涉及”，不要编造。\n\n"
    )
    return header + "\n\n".join(blocks), sources


def sources_markdown(sources: List[Dict]) -> str:
    """把来源渲染成给用户看的 markdown。"""
    if not sources:
        return "（本次提问未匹配到知识库资料）"
    lines = []
    for item in sources:
        sections = item.get("sections") or []
        suffix = f"｜命中章节：{'、'.join(sections)}" if sections else ""
        lines.append(f"- `{item['file']}`{suffix}")
    return "**依据资料**\n" + "\n".join(lines)
