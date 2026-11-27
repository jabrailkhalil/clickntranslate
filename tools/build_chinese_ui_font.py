"""Rebuild the bundled Simplified Chinese interface font from Noto Sans CJK SC 2.004."""
import argparse
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "src" / "icons" / "fonts"
SOURCE_SHA256 = {
    "Regular": "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b",
    "Bold": "b5f0d1a190a7f9b43c310a8850630af12553df32c4c050543f9059732d9b4c0a",
}
FAMILY = "ClicknTranslate Han"
# Ideographs, Kana, Hangul, East Asian punctuation and fullwidth forms used
# in Chinese labels or native language names. The normal UI font covers Latin.
SCRIPT_RANGES = (
    (0x2E80, 0x30FF), (0x3100, 0x31FF), (0x3400, 0x9FFF),
    (0xAC00, 0xD7A3), (0xF900, 0xFAFF), (0xFF01, 0xFFEF),
    (0x20000, 0x323AF),
)


def interface_codepoints():
    result = set()
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        # Language detection uses single characters as Unicode range limits;
        # those numeric bounds are not interface strings.
        range_arguments = set()
        for expression in ast.walk(tree):
            if isinstance(expression, ast.Compare):
                range_arguments.update([expression.left, *expression.comparators])
            elif (isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name)
                  and expression.func.id == "_count_range"):
                range_arguments.update(expression.args[1:])
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in range_arguments:
                result.update(ord(char) for char in set(node.value) if ord(char) >= 0x2E80)
    return {code for code in result if any(first <= code <= last for first, last in SCRIPT_RANGES)}


def write_subset(source_dir, weight, codepoints):
    from fontTools import subset
    from fontTools.ttLib import TTFont

    source = source_dir / f"NotoSansCJKsc-{weight}.otf"
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256[weight]:
        raise ValueError(f"Unexpected SHA-256 for {source.name}")
    with TTFont(source, recalcTimestamp=False) as font:
        missing = codepoints.difference(font.getBestCmap())
        if missing:
            raise ValueError(f"{source.name} is missing " + ", ".join(f"U+{n:04X}" for n in sorted(missing)))
        options = subset.Options()
        options.name_IDs = ["*"]
        options.name_languages = ["*"]
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=codepoints)
        subsetter.subset(font)
        # Use a distinct family and PostScript identity for the modified faces.
        postscript = f"ClicknTranslateHan-{weight}"
        full_name = f"{FAMILY} {weight}"
        names = {1: FAMILY, 3: postscript + "-2.004", 4: full_name, 6: postscript, 16: FAMILY}
        for record in font["name"].names:
            if record.nameID in names:
                record.string = names[record.nameID].encode(record.getEncoding())
        cff = font["CFF "].cff
        original = cff.fontNames[0]
        cff.fontNames[0] = postscript
        top = cff.topDictIndex[0]
        top.FamilyName = FAMILY
        top.FullName = full_name
        for subfont in top.FDArray:
            subfont.FontName = subfont.FontName.replace(original, postscript)
        # Report the intended writing system even in a minimal, non-Latin face.
        font["OS/2"].ulCodePageRange1 = 1 << 18  # Simplified Chinese (CP936)
        font["OS/2"].ulCodePageRange2 = 0
        output = FONT_DIR / (postscript + ".otf")
        font.save(output)
        print(output.name, output.stat().st_size, hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing both pinned upstream OTFs")
    args = parser.parse_args()
    codepoints = interface_codepoints()
    for weight in SOURCE_SHA256:
        write_subset(args.source_dir, weight, codepoints)
