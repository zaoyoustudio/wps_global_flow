#!/usr/bin/env python3
"""Add supplemental DOCX flows without replacing existing flows or assets.

Usage: python scripts/import_supplemental_flows.py --source-dir /path/to/补充页面
Run after extract_flows.py when rebuilding the original collection.
"""

import argparse
import io
import json
import posixpath
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
SPECS = [
    ("AI伴写_Win", "ai-write-payment", "AI 伴写与付费", ["付费后需手动开启"]),
    ("AI续写_Win", "ai-continue-payment", "AI 续写与付费", ["无法跳回 WPS", "任务上下文丢失"]),
    ("PDF编辑_Win", "pdf-edit-payment", "PDF 编辑与付费", ["无法跳回 WPS", "会员状态未同步"]),
    ("PDF转PPT_Win", "pdf-to-ppt-payment", "PDF 转 PPT 与付费", ["无法跳回 WPS", "会员权益感弱"]),
    ("PDF扫描件_Win", "pdf-ocr-payment", "PDF 扫描件 OCR 与付费", ["回跳误触发下载", "弹窗持续置顶"]),
    ("PDF扫描件报错_Win", "pdf-ocr-payment-error", "PDF 扫描件付费报错", ["支付报错无兜底", "支付状态未同步"]),
    ("公共入口付费_Win", "common-payment", "公共入口付费", ["会员权益感弱", "付费后仍显示促销"]),
]


def extract_frames(source, slug):
    """Use document order and relationship IDs, rather than media filenames."""
    entries = []
    with ZipFile(source) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        relationships = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in relationships
                   if r.attrib.get("TargetMode") != "External"}
        caption = ""
        supplemental = False
        for paragraph in document.findall(".//w:body//w:p", NS):
            text = "".join(t.text or "" for t in paragraph.findall(".//w:t", NS)).strip()
            if text and text != source.stem:
                if text in ("另外的界面（不在链路里）", "其他"):
                    supplemental = True
                caption = text
            for blip in paragraph.findall(".//a:blip", NS):
                target = targets[blip.attrib[f"{{{NS['r']}}}embed"]]
                member = posixpath.normpath(posixpath.join("word", target)) if not target.startswith("/") else target.lstrip("/")
                title = caption or f"步骤 {len(entries) + 1}"
                if supplemental:
                    title = "补充界面：" + title
                entries.append((title, archive.read(member)))

    counts = Counter(title for title, _ in entries)
    seen = Counter()
    dest = ROOT / "assets" / "windows" / slug
    dest.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, (title, content) in enumerate(entries, 1):
        seen[title] += 1
        if counts[title] > 1:
            title += f" {seen[title]}/{counts[title]}"
        path = dest / f"{index:02d}.webp"
        with Image.open(io.BytesIO(content)) as image:
            image = image.convert("RGB")
            image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            image.save(path, "WEBP", quality=78, method=6)
        frames.append({"title": title, "src": path.relative_to(ROOT).as_posix(),
                       "fileName": title + ".webp"})
    if not frames:
        raise ValueError(f"No screenshots found: {source}")
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    args = parser.parse_args()
    sources = [args.source_dir / (stem + ".docx") for stem, *_ in SPECS]
    for source in sources:
        if not source.is_file():
            parser.error(f"Missing source: {source}")
    data_path = ROOT / "data.js"
    raw = data_path.read_text(encoding="utf-8")
    flows = json.loads(raw.removeprefix("window.FLOWS = ").strip().removesuffix(";"))
    additions = []
    for source, (_, slug, title, issues) in zip(sources, SPECS):
        additions.append({"id": "win-" + slug, "platform": "Windows", "title": title,
                          "issues": issues, "sourceDocument": source.name,
                          "frames": extract_frames(source, slug)})
    ids = {flow["id"] for flow in additions}
    flows = [flow for flow in flows if flow["id"] not in ids]
    insertion = next((i for i, flow in enumerate(flows) if flow["platform"] != "Windows"), len(flows))
    flows[insertion:insertion] = additions
    data_path.write_text("window.FLOWS = " + json.dumps(flows, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Added {len(additions)} flows, {sum(len(f['frames']) for f in additions)} screenshots")
    for flow in additions:
        print(f"  {flow['title']}: {len(flow['frames'])}")


if __name__ == "__main__":
    main()
