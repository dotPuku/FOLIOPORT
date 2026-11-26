from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}
MAX_EXTRACTED_CHARS = 45000
MAX_DOCX_UNCOMPRESSED_BYTES = 50000000


class DocumentParseError(ValueError):
    pass


def _read_upload(file_storage):
    filename = (file_storage.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise DocumentParseError("Unsupported file type. Upload a .txt, .pdf, or .docx document.")
    raw = file_storage.read()
    if not raw:
        raise DocumentParseError("The uploaded file is empty.")
    return suffix, raw


def _valid_link(text, url):
    text = str(text or "").strip()[:300]
    url = str(url or "").strip()[:1000]
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return {"text": text, "url": url}


def _extract_pdf(raw):
    try:
        reader = PdfReader(BytesIO(raw))
        if getattr(reader, "is_encrypted", False):
            raise DocumentParseError("Password-protected PDFs are not supported. Upload an unlocked copy.")
        pages = []
        links = []
        for page in reader.pages[:80]:
            if len(links) >= 200:
                break
            text_fragments = []

            def collect_text(text, matrix, text_matrix, font, font_size):
                if text and text.strip():
                    try:
                        text_fragments.append((text, text_matrix[4], text_matrix[5]))
                    except (IndexError, TypeError):
                        return

            pages.append(page.extract_text(visitor_text=collect_text) or "")
            for annotation_ref in page.get("/Annots", []):
                annotation = annotation_ref.get_object()
                action = annotation.get("/A") or {}
                label = annotation.get("/Contents")
                if not label and annotation.get("/Rect"):
                    try:
                        x0, y0, x1, y1 = map(float, annotation.get("/Rect"))
                        matching_fragments = [
                            text for text, x, y in text_fragments
                            if x0 - 2 <= x <= x1 + 2 and y0 - 2 <= y <= y1 + 2
                        ]
                        label = " ".join(part.strip() for part in matching_fragments if part.strip())
                    except (TypeError, ValueError):
                        label = ""
                link = _valid_link(label, action.get("/URI"))
                if link:
                    links.append(link)
                    if len(links) >= 200:
                        break
        return "\n".join(pages), links
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("Could not read this PDF. Try exporting it again or upload a DOCX file.") from exc


def _extract_docx(raw):
    try:
        with ZipFile(BytesIO(raw)) as archive:
            if len(archive.infolist()) > 2000 or sum(item.file_size for item in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise DocumentParseError("This DOCX file is too large to safely process.")
        doc = Document(BytesIO(raw))
        blocks = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                blocks.append(" | ".join(cell.text.strip() for cell in row.cells))

        links = []
        for hyperlink in doc._element.iter(qn("w:hyperlink")):
            rel_id = hyperlink.get(qn("r:id"))
            relation = doc.part.rels.get(rel_id) if rel_id else None
            if not relation or not relation.is_external:
                continue
            label = "".join(node.text or "" for node in hyperlink.iter(qn("w:t")))
            link = _valid_link(label, relation.target_ref)
            if link:
                links.append(link)
                if len(links) >= 200:
                    break
        return "\n".join(blocks), links
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("Could not read this DOCX file. Please save it again as a valid Word document.") from exc


def _extract_contents(raw, suffix, min_chars=80):
    if suffix == ".pdf":
        text, links = _extract_pdf(raw)
    elif suffix == ".docx":
        text, links = _extract_docx(raw)
    else:
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        links = []
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if len(text) < min_chars:
        raise DocumentParseError("Very little text could be extracted. Scanned/image-only PDFs need OCR before upload; paste the text instead.")
    return text[:MAX_EXTRACTED_CHARS], links[:200]


def parse_uploaded_file(file_storage):
    suffix, raw = _read_upload(file_storage)
    text, _ = _extract_contents(raw, suffix)
    return text


def parse_uploaded_resume(file_storage):
    suffix, raw = _read_upload(file_storage)
    if suffix not in {".pdf", ".docx"}:
        raise DocumentParseError("Unsupported file type. Upload a .pdf or .docx resume.")
    text, links = _extract_contents(raw, suffix, min_chars=20)
    return {"text": text, "links": links}
