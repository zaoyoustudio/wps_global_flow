#!/usr/bin/env python3
"""Extract WPS flow screenshots and emit data.js."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DATA_JS = ROOT / "data.js"

WORD_EXTRACT = Path("/Users/wps/Downloads/未注册用户使用PDF提取文字.docx")
WORD_OPEN = Path("/Users/wps/Downloads/未注册用户打开PDF.docx")
WORD_TRIAL = Path("/Users/wps/Downloads/开始试用.docx")
EXCEL = Path("/Users/wps/Downloads/海外付费体验-走查记录&竞品分析(1).xlsx")

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "etc": "http://www.wps.cn/officeDocument/2017/etCustomData",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

WORD_FLOWS = [
    {
        "id": "win-open-pdf",
        "platform": "Windows",
        "title": "未注册用户打开 PDF",
        "docx": WORD_OPEN,
        "dir": "windows/open-pdf",
        "steps": [
            "打开即见推销",
            "引导 OCR",
            "付费墙",
            "智能推荐",
            "推荐 PDF 转 Word",
            "再次付费墙",
        ],
    },
    {
        "id": "win-start-trial",
        "platform": "Windows",
        "title": "开始试用",
        "docx": WORD_TRIAL,
        "dir": "windows/start-trial",
        "steps": [
            "安装成功，开始试用",
            "登录注册",
            "收银台",
            "Stripe 付款",
            "支付成功",
            "回到桌面首页",
            "打开账户菜单",
            "个人中心",
            "路径1：点管理或取消",
            "订阅管理页",
            "点击取消续订",
            "取消挽留弹窗",
            "填写取消原因",
            "自动续费已关闭",
            "路径2：点权益说明",
            "跳到支付页",
        ],
    },
    {
        "id": "win-extract-text",
        "platform": "Windows",
        "title": "未注册用户提取 PDF 文字",
        "docx": WORD_EXTRACT,
        "dir": "windows/extract-text",
        "steps": [
            "发现入口",
            "功能加载中",
            "弹出登录注册",
            "继续加载",
            "复制时发现需付费",
            "付费墙",
        ],
    },
]

EXCEL_FLOW_META = {
    ("WPS_Windows", "初次使用产品"): {
        "id": "win-first-open",
        "platform": "Windows",
        "title": "初次使用产品",
        "dir": "windows/first-open",
    },
    ("WPS_Windows", "从文件导入页面"): {
        "id": "win-import-pages",
        "platform": "Windows",
        "title": "从文件导入页面",
        "dir": "windows/import-pages",
    },
    ("WPS_Windows", "使用AI伴写论文"): {
        "id": "win-ai-write",
        "platform": "Windows",
        "title": "使用 AI 伴写论文",
        "dir": "windows/ai-write",
    },
    ("WPS_Windows", "使用AI朗读文档"): {
        "id": "win-ai-read",
        "platform": "Windows",
        "title": "使用 AI 朗读文档",
        "dir": "windows/ai-read",
    },
    ("WPS_Windows", "使用AI排版论文"): {
        "id": "win-ai-layout",
        "platform": "Windows",
        "title": "使用 AI 排版论文",
        "dir": "windows/ai-layout",
    },
    ("WPS_Windows", "使用DOC导出为PDF"): {
        "id": "win-doc-to-pdf",
        "platform": "Windows",
        "title": "使用 DOC 导出为 PDF",
        "dir": "windows/doc-to-pdf",
    },
    ("WPS_Windows", "图片转PDF"): {
        "id": "win-image-to-pdf",
        "platform": "Windows",
        "title": "图片转 PDF",
        "dir": "windows/image-to-pdf",
    },
    ("WPS_Windows", "用AI生成PPT"): {
        "id": "win-ai-ppt",
        "platform": "Windows",
        "title": "用 AI 生成 PPT",
        "dir": "windows/ai-ppt",
    },
    ("WPS_Android", "初次使用产品"): {
        "id": "and-first-open",
        "platform": "Android",
        "title": "初次使用产品",
        "dir": "android/first-open",
    },
    ("WPS_Android", "打开并编辑PDF"): {
        "id": "and-edit-pdf",
        "platform": "Android",
        "title": "打开并编辑 PDF",
        "dir": "android/edit-pdf",
    },
    ("WPS_Android", "使用DOC转PDF"): {
        "id": "and-doc-to-pdf",
        "platform": "Android",
        "title": "使用 DOC 转 PDF",
        "dir": "android/doc-to-pdf",
    },
    ("WPS_Android", "提取PDF文字内容"): {
        "id": "and-extract-text",
        "platform": "Android",
        "title": "提取 PDF 文字内容",
        "dir": "android/extract-text",
    },
}

SIDEBAR_ORDER = [
    "win-first-open",
    "win-open-pdf",
    "win-extract-text",
    "win-start-trial",
    "win-import-pages",
    "win-ai-write",
    "win-ai-read",
    "win-ai-layout",
    "win-doc-to-pdf",
    "win-image-to-pdf",
    "win-ai-ppt",
    "and-first-open",
    "and-edit-pdf",
    "and-doc-to-pdf",
    "and-extract-text",
]

# Typical problems aligned to 问题识别 / 走查建议, not every shared paywall complaint.
FLOW_ISSUES = {
    "win-first-open": ["价值感知缺失", "打开即弹付费"],
    "win-open-pdf": ["打开即弹付费", "无功能承接"],
    "win-extract-text": ["后置付费", "登录打断"],
    "win-start-trial": ["权益入口跳支付", "会员权益感弱"],
    "win-import-pages": ["付费标识弱", "无功能承接"],
    "win-ai-write": ["误耗试用"],
    "win-ai-read": ["标识不一致", "使用额度未知"],
    "win-ai-layout": ["打开即弹付费"],
    "win-doc-to-pdf": ["付费标过多", "规则不一致"],
    "win-image-to-pdf": ["默认付费项", "未反映付费状态"],
    "win-ai-ppt": ["有 Bug"],
    "and-first-open": ["价值感知缺失"],
    "and-edit-pdf": ["打开即弹付费", "试用无感知"],
    "and-doc-to-pdf": ["默认付费项", "试用无感知"],
    "and-extract-text": ["后置付费", "未反映付费状态"],
}

DISPIMG_RE = re.compile(r'DISPIMG\("([^"]+)"')


def colrow(ref: str) -> tuple[str, int]:
    col = ""
    row = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            row += ch
    return col, int(row)


def shared_strings(z: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
        texts = [
            t.text or ""
            for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        out.append("".join(texts))
    return out


def cell_text(cell: ET.Element, strings: list[str]) -> str:
    t = cell.attrib.get("t")
    v = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    f = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f")
    if t == "s" and v is not None and v.text:
        return strings[int(v.text)]
    if t == "str" and v is not None and v.text:
        return v.text
    if f is not None and (f.text or ""):
        return f.text
    if v is not None and v.text:
        return v.text
    return ""


def load_id_to_media(z: zipfile.ZipFile) -> dict[str, str]:
    rels_root = ET.fromstring(z.read("xl/_rels/cellimages.xml.rels"))
    rid_to_target = {}
    for rel in rels_root:
        rid_to_target[rel.attrib["Id"]] = rel.attrib["Target"]

    images_root = ET.fromstring(z.read("xl/cellimages.xml"))
    id_to_media = {}
    for pic in images_root.iter("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}pic"):
        name_el = pic.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}nvPicPr/{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}cNvPr")
        blip = pic.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}blipFill/{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
        if name_el is None or blip is None:
            continue
        rid = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
        target = rid_to_target[rid]
        media_name = "xl/" + target.lstrip("/")
        if target.startswith("media/"):
            media_name = "xl/" + target
        id_to_media[name_el.attrib["name"]] = media_name
    return id_to_media


def extract_word_images(docx: Path, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with zipfile.ZipFile(docx) as z:
        media = sorted(
            [n for n in z.namelist() if n.startswith("word/media/") and not n.endswith("/")],
            key=lambda n: int(re.search(r"(\d+)", Path(n).stem).group(1)),
        )
        for i, name in enumerate(media, start=1):
            ext = Path(name).suffix.lower() or ".png"
            out = dest / f"{i:02d}{ext}"
            out.write_bytes(z.read(name))
            written.append(out)
    return written


def clean_step_title(raw: str, fallback_index: int) -> str:
    title = (raw or "").strip()
    title = re.sub(r"\s+", " ", title)
    if not title:
        return f"步骤 {fallback_index}"
    return title


def extract_excel_flows() -> list[dict]:
    flows_out: dict[str, dict] = {}
    with zipfile.ZipFile(EXCEL) as z:
        strings = shared_strings(z)
        id_to_media = load_id_to_media(z)
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows: dict[int, dict[str, str]] = defaultdict(dict)
        for cell in sheet.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
            ref = cell.attrib.get("r")
            if not ref:
                continue
            col, row = colrow(ref)
            rows[row][col] = cell_text(cell, strings)

        grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
        for r in sorted(rows):
            product = (rows[r].get("P") or "").strip()
            scene = (rows[r].get("Q") or "").strip()
            if not product.startswith("WPS_"):
                continue
            key = (product, scene)
            if key not in EXCEL_FLOW_META:
                continue
            grouped[key].append(r)

        for key, row_ids in grouped.items():
            meta = EXCEL_FLOW_META[key]
            dest = ASSETS / meta["dir"]
            dest.mkdir(parents=True, exist_ok=True)
            frames = []
            img_index = 0
            unnamed = 0
            for row_i, r in enumerate(row_ids, start=1):
                step_raw = rows[r].get("A") or ""
                unnamed += 1
                step_title = clean_step_title(step_raw, unnamed)
                ids = []
                for col in "BCDE":
                    val = rows[r].get(col) or ""
                    m = DISPIMG_RE.search(val)
                    if m:
                        ids.append(m.group(1))
                total = len(ids)
                for shot_i, img_id in enumerate(ids, start=1):
                    media_name = id_to_media[img_id]
                    ext = Path(media_name).suffix.lower() or ".png"
                    img_index += 1
                    out = dest / f"{img_index:02d}{ext}"
                    out.write_bytes(z.read(media_name))
                    title = step_title if total == 1 else f"{step_title} {shot_i}/{total}"
                    frames.append(
                        {
                            "title": title,
                            "src": str(out.relative_to(ROOT)).replace("\\", "/"),
                            "fileName": f"{title}{ext}",
                        }
                    )
            if not frames:
                continue
            flows_out[meta["id"]] = {
                "id": meta["id"],
                "platform": meta["platform"],
                "title": meta["title"],
                "issues": FLOW_ISSUES.get(meta["id"], []),
                "frames": frames,
            }
    return [flows_out[fid] for fid in SIDEBAR_ORDER if fid in flows_out]


def main() -> None:
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    ASSETS.mkdir(parents=True)

    flows: list[dict] = []

    word_by_id = {}
    for spec in WORD_FLOWS:
        dest = ASSETS / spec["dir"]
        files = extract_word_images(spec["docx"], dest)
        frames = []
        for i, path in enumerate(files):
            title = spec["steps"][i] if i < len(spec["steps"]) else f"步骤 {i + 1}"
            frames.append(
                {
                    "title": title,
                    "src": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "fileName": f"{title}{path.suffix.lower()}",
                }
            )
        word_by_id[spec["id"]] = {
            "id": spec["id"],
            "platform": spec["platform"],
            "title": spec["title"],
            "issues": FLOW_ISSUES.get(spec["id"], []),
            "frames": frames,
        }

    excel_flows = extract_excel_flows()
    excel_by_id = {f["id"]: f for f in excel_flows}

    for fid in SIDEBAR_ORDER:
        flow = word_by_id.get(fid) or excel_by_id.get(fid)
        if not flow:
            continue
        flow["issues"] = FLOW_ISSUES.get(fid, [])
        flows.append(flow)

    payload = json.dumps(flows, ensure_ascii=False, indent=2)
    DATA_JS.write_text(f"window.FLOWS = {payload};\n", encoding="utf-8")

    total_frames = sum(len(f["frames"]) for f in flows)
    print(f"flows={len(flows)} frames={total_frames}")
    for f in flows:
        print(f"  {f['platform']:8s} {f['title']:24s} {len(f['frames']):3d} frames")


if __name__ == "__main__":
    main()
