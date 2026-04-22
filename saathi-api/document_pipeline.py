import asyncio
import io
from typing import Any

import PyPDF2
import docx
from deep_translator import GoogleTranslator


def _chunk_text(text: str, max_chunk_size: int = 3200) -> list[str]:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if len(cleaned) <= max_chunk_size:
        return [cleaned]

    chunks: list[str] = []
    current = ""
    for paragraph in cleaned.split("\n"):
        separator = "" if not current else "\n"
        candidate = f"{current}{separator}{paragraph}"
        if len(candidate) <= max_chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_chunk_size:
            chunks.append(paragraph[:max_chunk_size])
            paragraph = paragraph[max_chunk_size:]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks or [cleaned]


async def translate_text_content(text: str, target_lang: str) -> str:
    translator = GoogleTranslator(source="auto", target=target_lang)
    translated_parts: list[str] = []
    for chunk in _chunk_text(text):
        translated_parts.append(await asyncio.to_thread(translator.translate, chunk))
    return "\n".join(part for part in translated_parts if part is not None)


def _named_style_from_docx(style_name: str) -> str:
    style_key = (style_name or "").strip().lower()
    if style_key.startswith("title"):
        return "TITLE"
    if style_key.startswith("subtitle"):
        return "SUBTITLE"
    if "heading 1" in style_key:
        return "HEADING_1"
    if "heading 2" in style_key:
        return "HEADING_2"
    if "heading 3" in style_key:
        return "HEADING_3"
    if "heading 4" in style_key:
        return "HEADING_4"
    if "heading 5" in style_key:
        return "HEADING_5"
    if "heading 6" in style_key:
        return "HEADING_6"
    return "NORMAL_TEXT"


def _alignment_from_docx(paragraph: Any) -> str | None:
    alignment = getattr(paragraph, "alignment", None)
    if alignment is None:
        return None
    alignment_value = int(alignment)
    mapping = {
        0: "START",
        1: "CENTER",
        2: "END",
        3: "JUSTIFIED",
        4: "JUSTIFIED",
    }
    return mapping.get(alignment_value)


def _bullet_preset_for_paragraph(paragraph: Any) -> str | None:
    style_name = getattr(getattr(paragraph, "style", None), "name", "") or ""
    style_key = style_name.lower()
    if "list bullet" in style_key:
        return "BULLET_DISC_CIRCLE_SQUARE"
    if "list number" in style_key:
        return "NUMBERED_DECIMAL_ALPHA_ROMAN"
    num_pr = None
    try:
        num_pr = paragraph._p.pPr.numPr  # type: ignore[attr-defined]
    except Exception:
        num_pr = None
    if num_pr is not None:
        return "NUMBERED_DECIMAL_ALPHA_ROMAN"
    return None


def _blocks_from_text(text: str) -> list[dict[str, Any]]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    blocks = []
    for line in lines:
        stripped = line.strip()
        bullet_preset = None
        if stripped.startswith(("- ", "* ")):
            stripped = stripped[2:].strip()
            bullet_preset = "BULLET_DISC_CIRCLE_SQUARE"
        blocks.append(
            {
                "text": stripped,
                "paragraphStyle": "NORMAL_TEXT",
                "alignment": None,
                "bulletPreset": bullet_preset,
            }
        )
    return blocks


def extract_document_payload(filename: str, file_bytes: bytes) -> dict[str, Any]:
    file_name = (filename or "document.txt").lower()

    if file_name.endswith(".docx"):
        document = docx.Document(io.BytesIO(file_bytes))
        blocks: list[dict[str, Any]] = []
        for paragraph in document.paragraphs:
            text = "".join(run.text for run in paragraph.runs)
            if text is None:
                text = ""
            blocks.append(
                {
                    "text": text.strip(),
                    "paragraphStyle": _named_style_from_docx(getattr(getattr(paragraph, "style", None), "name", "")),
                    "alignment": _alignment_from_docx(paragraph),
                    "bulletPreset": _bullet_preset_for_paragraph(paragraph),
                }
            )
        plain_text = "\n".join(block["text"] for block in blocks).strip()
        return {"plain_text": plain_text, "blocks": blocks, "preserve_styles": True}

    if file_name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        paragraphs: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            paragraphs.extend(extracted.splitlines())
        plain_text = "\n".join(paragraphs).strip()
        return {"plain_text": plain_text, "blocks": _blocks_from_text(plain_text), "preserve_styles": False}

    plain_text = file_bytes.decode("utf-8", errors="ignore")
    return {"plain_text": plain_text, "blocks": _blocks_from_text(plain_text), "preserve_styles": False}


async def translate_document_blocks(blocks: list[dict[str, Any]], target_lang: str) -> list[dict[str, Any]]:
    translator = GoogleTranslator(source="auto", target=target_lang)
    translated: list[dict[str, Any]] = []
    for block in blocks:
        text = block.get("text") or ""
        if not text.strip():
            translated.append({**block, "text": ""})
            continue
        translated_text_parts: list[str] = []
        for chunk in _chunk_text(text):
            translated_text_parts.append(await asyncio.to_thread(translator.translate, chunk))
        translated.append({**block, "text": "\n".join(part for part in translated_text_parts if part is not None)})
    return translated
