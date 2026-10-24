import html
import codecs
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
    # RTF has its own byte encoding. Decoding the entire file as UTF-8/CP1251
    # first loses both \ansicpg and multibyte sequences represented by \'hh.
    with open(path, "rb") as stream:
        text = stream.read().decode("latin-1")
    tokens = re.compile(
        r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\([^a-zA-Z])|([{}])|([\r\n])|([^\\{}\r\n]+)"
    )
    destinations = {
        "fonttbl", "colortbl", "stylesheet", "info", "pict", "object",
        "header", "headerl", "headerr", "footer", "footerl", "footerr",
        "filetbl", "listtable", "listoverridetable", "rsidtbl", "generator",
        "xmlnstbl", "datastore", "themedata", "colorschememapping", "fldinst",
    }
    charsets = {
        128: "cp932", 129: "cp949", 130: "johab", 134: "gbk", 136: "big5",
        161: "cp1253", 162: "cp1254", 163: "cp1258", 177: "cp1255",
        178: "cp1256", 186: "cp1257", 204: "cp1251", 222: "cp874",
        238: "cp1250", 254: "cp437", 255: "cp850",
    }
    characters = {
        "par": "\n", "line": "\n", "tab": "\t", "cell": "\t", "row": "\n",
        "emdash": "—", "endash": "–", "bullet": "•", "lquote": "‘",
        "rquote": "’", "ldblquote": "“", "rdblquote": "”",
    }
    output, pending_bytes, stack = [], bytearray(), []
    encoding = default_encoding = "cp1252"
    unicode_fallback = 1
    skip_fallback = 0
    ignored = in_font_table = False
    font = None
    font_encodings = {}

    def flush_bytes():
        if pending_bytes:
            output.append(pending_bytes.decode(encoding, errors="replace"))
            pending_bytes.clear()

    def codepage(value):
        candidate = "cp" + str(value)
        try:
            return codecs.lookup(candidate).name
        except LookupError:
            return default_encoding

    position = 0
    while position < len(text):
        token = tokens.match(text, position)
        if token is None:
            position += 1
            continue
        position = token.end()
        word, parameter, hex_byte, symbol, brace, newline, literal = token.groups()
        if literal is not None or hex_byte is not None:
            value = bytes.fromhex(hex_byte) if hex_byte else literal.encode("latin-1")
            skip = min(skip_fallback, len(value))
            skip_fallback -= skip
            if not ignored:
                pending_bytes.extend(value[skip:])
            continue
        if newline:
            continue  # Physical source wrapping is not an RTF paragraph break.
        flush_bytes()
        if brace:
            skip_fallback = 0
            if brace == "{":
                stack.append((encoding, unicode_fallback, ignored, in_font_table, font))
            elif stack:
                encoding, unicode_fallback, ignored, in_font_table, font = stack.pop()
            continue
        if skip_fallback:
            skip_fallback -= 1
            continue
        if symbol:
            if symbol == "*":
                ignored = True
            elif not ignored:
                output.append({"~": "\u00a0", "_": "‑", "-": "\u00ad"}.get(symbol, symbol))
            continue
        number = int(parameter) if parameter is not None else None
        if word == "bin" and number is not None:
            position += max(0, number)  # Binary objects can contain braces/backslashes.
        elif word in destinations:
            ignored = True
            in_font_table = in_font_table or word == "fonttbl"
        elif word in {"ansicpg", "cpg"} and number is not None:
            encoding = codepage(number)
            if in_font_table and font is not None:
                font_encodings[font] = encoding
            elif word == "ansicpg":
                default_encoding = encoding
        elif word == "f" and number is not None:
            font = number
            if not in_font_table:
                encoding = font_encodings.get(font, default_encoding)
        elif word == "fcharset" and in_font_table and font is not None:
            font_encodings[font] = charsets.get(number, default_encoding)
        elif word == "uc" and number is not None:
            unicode_fallback = max(0, number)
        elif word == "u" and number is not None:
            if not ignored:
                output.append(chr(number & 0xFFFF))
            skip_fallback = unicode_fallback
        elif not ignored and word in characters:
            output.append(characters[word])
    flush_bytes()
    # RTF's signed \uN values are UTF-16 code units, including surrogate pairs.
    return "".join(output).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


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
