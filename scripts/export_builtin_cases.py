#!/usr/bin/env python3
"""把 mdt_teaching.py 里内置的 MDT_CASE_STUDIES 导出为病例库文件。

一次性迁移脚本：之后病例都在 data/knowledge_base/_cases/*.md 里维护，改文件即生效。
已存在的文件默认不覆盖（--force 覆盖）。

用法:
    python scripts/export_builtin_cases.py [--force]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

SRC = Path("libs/chatchat-server/chatchat/webui_pages/mdt_teaching.py")
OUT_DIR = Path("data/knowledge_base/_cases")

# 病例 id → 影像（本地文件名, 说明）。影像来自 scripts/fetch_case_images.py，
# 许可与作者见 _cases/ATTRIBUTION.md。
CASE_IMAGES = {
    "bladder_001": [
        ("bladder_ct.jpg", "盆腔 CT 轴位：膀胱壁局限性增厚/肿块（示例影像，非本病例原始影像）"),
    ],
    "kidney_001": [
        ("rcc_ct_vhl.jpg", "肾细胞癌 CT：VHL 病相关肾癌（示例影像）"),
        ("rcc_bilateral_ct.jpg", "双肾多发肿瘤：术前增强 CT（示例影像）"),
    ],
    "utuc_001": [
        ("utuc_ct.jpg", "肾实质期 CT：肾盂内充盈缺损，提示上尿路尿路上皮癌（示例影像）"),
        ("ct_urography_3d.jpg", "CT 尿路造影三维重建：观察尿路走行与病变位置（对照）"),
        ("ct_urography_normal.jpg", "CT 尿路造影（对照）：肾盂旁囊肿，用于对比正常集合系统形态"),
    ],
}


def load_builtin() -> dict:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "MDT_CASE_STUDIES" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit("没找到 MDT_CASE_STUDIES")


def dump(case: dict, images: list) -> str:
    def q(value: str) -> str:
        return '"' + str(value).replace('"', '\\"') + '"'

    lines = ["---"]
    lines.append(f"id: {q(case.get('id', ''))}")
    lines.append(f"title: {q(case.get('title', ''))}")
    lines.append(f"disease: {q(case.get('disease', '未分类'))}")
    lines.append(f"difficulty: {q(case.get('difficulty', '未标注'))}")
    tags = case.get("tags") or []
    lines.append("tags: [" + ", ".join(q(t) for t in tags) + "]")
    lines.append(f"description: {q(case.get('description', ''))}")
    if images:
        lines.append("images:")
        for name, caption in images:
            lines.append(f"  - path: images/{name}")
            lines.append(f"    caption: {q(caption)}")
    lines.append("---")
    lines.append("")
    lines.append((case.get("content") or "").strip())
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = load_builtin()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = 0

    for disease, cases in data.items():
        for case in cases:
            case = dict(case)
            case["disease"] = disease
            target = OUT_DIR / f"{case['id']}.md"
            if target.exists() and not args.force:
                print(f"[跳过] {target.name}（已存在）")
                skipped += 1
                continue
            target.write_text(dump(case, CASE_IMAGES.get(case["id"], [])), encoding="utf-8")
            print(f"[写入] {target.name}  ({disease})")
            written += 1

    print(f"\n完成：写入 {written} 个，跳过 {skipped} 个 -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
