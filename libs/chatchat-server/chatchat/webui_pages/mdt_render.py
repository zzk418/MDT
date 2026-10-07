"""聊天回答渲染前的 Markdown 规整。

原先在页面里直接 `text.replace("\\n", "\\n\\n")`，目的是让模型的单换行文本不至于
挤成一段；但 Markdown 表格、列表都要求行与行紧邻，被撑成空行后表格就渲染成
一堆竖线。这里逐行处理，兼顾两边：

- 代码块（``` 围栏内）原样保留，避免改动代码内容
- 表格行（以 | 开头，或下一行是表格）不加尾随空格
- 空行保持，作为段落分隔
- 其余非空行行尾补两个空格，形成 Markdown 硬换行

与 Streamlit 无关，便于单测。
"""

from typing import List


def render_md(text: str) -> str:
    lines = (text or "").split("\n")
    out: List[str] = []
    in_code = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not stripped or not nxt:
            out.append(line)  # 空行 / 末尾：保留段落分隔
            continue
        if stripped.startswith("|") or nxt.startswith("|"):
            out.append(line)  # 表格行：保持紧邻
            continue

        out.append(line + "  ")  # 其余行：硬换行

    return "\n".join(out)
