#!/usr/bin/env python3
"""从 Wikimedia Commons 抓取「宽松许可」的医学影像，作为病例示教图。

只用 PD / CC0 / CC BY（排除 CC BY-SA、NC、ND），并把作者、许可、原始页面写进
ATTRIBUTION.md，便于合规署名与日后替换。

要加图：在 IMAGES 里加一条 Commons 文件名 + 目标文件名 + 说明即可，然后重跑本脚本。
已有的文件默认跳过（--force 覆盖）。

用法:
    python scripts/fetch_case_images.py [--out DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

PROXY = "http://127.0.0.1:7897"  # 本机 Clash；直连可设 --no-proxy
API = "https://commons.wikimedia.org/w/api.php"

# Commons 文件名 → (本地文件名, 中文说明)
IMAGES = [
    ("File:CT of bladder cancer.jpg", "bladder_ct.jpg", "膀胱癌：盆腔 CT 轴位，膀胱壁局限性增厚/肿块"),
    ("File:Renal parenchymal phase CT of transitional cell carcinoma.jpg",
     "utuc_ct.jpg", "上尿路尿路上皮癌：肾实质期 CT，肾盂内充盈缺损"),
    ("File:CT VHL renal.jpg", "rcc_ct_vhl.jpg", "肾细胞癌：VHL 病相关肾癌 CT"),
    ("File:Preoperative-contrasted-CT-scans-of-the-patient-showing-multiple-bilateral-kidney-tumors-with-diameters-ranging-between.jpg",
     "rcc_bilateral_ct.jpg", "双肾多发肿瘤：术前增强 CT"),
    ("File:CT urography of peripelvic cysts.jpg", "ct_urography_normal.jpg",
     "CT 尿路造影（对照）：肾盂旁囊肿，用于对比正常集合系统形态"),
    ("File:Volume rendered CT urography.jpg", "ct_urography_3d.jpg",
     "CT 尿路造影三维重建（对照）：了解解剖与尿路走行"),
]

ALLOWED_LICENSE = ("public domain", "cc0", "cc by 2.0", "cc by 3.0", "cc by 4.0",
                   "cc-by-2.0", "cc-by-3.0", "cc-by-4.0")


def curl(url: str, use_proxy: bool = True, binary: bool = False):
    cmd = ["curl", "-sSL", "-m", "120", "-A", "MDT-case-image-fetcher/1.0 (teaching use)"]
    if use_proxy:
        cmd += ["-x", PROXY]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"下载失败: {url} :: {out.stderr.decode()[:200]}")
    return out.stdout if binary else out.stdout.decode("utf-8", "replace")


def fetch_meta(titles, use_proxy=True):
    url = (
        f"{API}?action=query&format=json&prop=imageinfo&iiprop=url|extmetadata|size"
        "&titles=" + urllib.parse.quote("|".join(titles))
    )
    data = json.loads(curl(url, use_proxy))
    pages = (data.get("query") or {}).get("pages") or {}
    return {p.get("title"): (p.get("imageinfo") or [{}])[0] for p in pages.values()}


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/knowledge_base/_cases/images")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-proxy", action="store_true")
    args = parser.parse_args()

    use_proxy = not args.no_proxy
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = fetch_meta([t for t, _, _ in IMAGES], use_proxy)
    lines = [
        "# 病例示教影像来源与许可",
        "",
        "本目录影像全部来自 Wikimedia Commons，均为公有领域（PD）/ CC0 / CC BY 授权，",
        "已由原始上传者脱敏。使用时保留出处；如需替换，改 `scripts/fetch_case_images.py`",
        "里的 IMAGES 列表后重跑即可。",
        "",
        "| 本地文件 | 说明 | 许可 | 作者 | 原始页面 |",
        "|---|---|---|---|---|",
    ]

    for title, local_name, caption in IMAGES:
        info = meta.get(title)
        if not info:
            print(f"[跳过] 取不到元数据: {title}")
            continue
        md = info.get("extmetadata") or {}
        license_name = strip_html((md.get("LicenseShortName") or {}).get("value", ""))
        if not any(a in license_name.lower() for a in ALLOWED_LICENSE):
            print(f"[跳过] 许可不允许: {title} -> {license_name}")
            continue

        url = (info.get("url") or "").split("?")[0]
        thumb = (info.get("thumburl") or "").split("?")[0]
        src = thumb or url
        target = out_dir / local_name
        if target.exists() and not args.force:
            print(f"[已有] {local_name}")
        else:
            target.write_bytes(curl(src, use_proxy, binary=True))
            print(f"[下载] {local_name}  <- {src}")

        artist = strip_html((md.get("Artist") or {}).get("value", "")) or "见原始页面"
        page = info.get("descriptionurl", "")
        lines.append(f"| `{local_name}` | {caption} | {license_name} | {artist} | {page} |")

    (out_dir.parent / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n署名文件: {(out_dir.parent / 'ATTRIBUTION.md').as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
