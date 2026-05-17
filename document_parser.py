import html
import os
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from xml.etree import ElementTree

from languages import detect_language_code


SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".pdf", ".html", ".htm", ".rtf"}


class DocumentParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedDocument:
    path: str
    file_name: str
    extension: str
    size_bytes: int
    text: str
    detected_language: str


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "div", "dl", "fieldset",
        "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
        "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
        "table", "tr", "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth and data:
            self._parts.append(data)

    def text(self):
        return _normalize_text("".join(self._parts))


def parse_document(path):
    if not path:
        raise DocumentParseError("No file selected.")
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise DocumentParseError("File not found.")

    extension = os.path.splitext(abs_path)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DocumentParseError(f"Unsupported file type: {extension or 'unknown'}. Supported: {supported}.")

    try:
        if extension in {".txt", ".md"}:
            text = _read_text_file(abs_path)
        elif extension in {".html", ".htm"}:
            text = _read_html_file(abs_path)
        elif extension == ".rtf":
            text = _read_rtf_file(abs_path)
        elif extension == ".docx":
            text = _read_docx_file(abs_path)
        elif extension == ".pdf":
            text = _read_pdf_file(abs_path)
        else:
            raise DocumentParseError(f"Unsupported file type: {extension}.")
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(f"Failed to read {os.path.basename(abs_path)}: {exc}") from exc

    text = _normalize_text(text)
    if not text:
        raise DocumentParseError("No readable text was found in this file.")

    return ParsedDocument(
        path=abs_path,
        file_name=os.path.basename(abs_path),
        extension=extension,
        size_bytes=os.path.getsize(abs_path),
        text=text,
        detected_language=detect_language_code(text[:5000]),
    )


def format_file_size(size_bytes):
    size = float(size_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def _read_text_file(path):
    raw = open(path, "rb").read()
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise DocumentParseError(f"Could not decode text file: {last_error}")


def _read_html_file(path):
    parser = _HTMLTextExtractor()
    parser.feed(_read_text_file(path))
    return parser.text()


def _read_rtf_file(path):
    text = _read_text_file(path)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", lambda m: bytes.fromhex(m.group(0)[2:]).decode("latin-1", "ignore"), text)
    text = re.sub(r"\\par[d]?", "\n", text)
    text = re.sub(r"\\tab", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    return text


def _read_docx_file(path):
    try:
        with zipfile.ZipFile(path) as archive:
            xml_data = archive.read("word/document.xml")
    except KeyError as exc:
        raise DocumentParseError("DOCX document.xml is missing.") from exc
    except zipfile.BadZipFile as exc:
        raise DocumentParseError("Invalid DOCX file.") from exc

    root = ElementTree.fromstring(xml_data)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(namespace + "p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == namespace + "t" and node.text:
                parts.append(node.text)
            elif node.tag == namespace + "tab":
                parts.append("\t")
            elif node.tag == namespace + "br":
                parts.append("\n")
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def _read_pdf_file(path):
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise DocumentParseError("PDF support requires the pypdf package.") from exc

    reader = PdfReader(path)
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = _normalize_text(text)
        if text:
            pages.append(f"--- Page {index} ---\n{text}")
    if not pages:
        raise DocumentParseError("No selectable text was found in this PDF. Scanned PDFs require OCR.")
    return "\n\n".join(pages)


def _normalize_text(value):
    value = html.unescape(str(value or ""))
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip()
