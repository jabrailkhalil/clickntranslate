"""Audit the actual packaged artifact without executing or trusting old application binaries."""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path


def native_libraries(archive: zipfile.ZipFile) -> list[dict]:
    native = []
    for name in archive.namelist():
        if not (name.startswith("lib/") and name.endswith(".so")):
            continue
        data = archive.read(name)
        if data[:6] != b"\x7fELF\x02\x01":
            raise ValueError(f"Expected little-endian ELF64: {name}")
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
        if header[2] != 183 or not name.startswith("lib/arm64-v8a/"):
            raise ValueError(f"Expected ARM64: {name}")
        load_alignments = []
        congruent = True
        for index in range(header[10]):
            segment = struct.unpack_from("<IIQQQQQQ", data, header[5] + index * header[9])
            if segment[0] == 1:  # PT_LOAD
                load_alignments.append(segment[7])
                if (segment[2] - segment[3]) % 16384:
                    congruent = False
        native.append({"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                       "load_alignments": load_alignments,
                       "page16k": bool(load_alignments) and congruent and min(load_alignments) >= 16384})
    return native


def check_native_pages(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        native = native_libraries(archive)
    if not native:
        raise ValueError("APK has no native libraries")
    incompatible = [lib["file"] for lib in native if not lib["page16k"]]
    if incompatible:
        raise ValueError("Incompatible with 16 KiB memory pages: " + ", ".join(incompatible))
    return {"apk": path.name, "all_native_16k": True, "native_libraries": native}


def audit(path: Path) -> dict:
    legacy = []
    fixture = False
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        native = native_libraries(archive)
        for name in archive.namelist():
            if name.endswith(".dex"):
                data = archive.read(name)
                fixture |= any(marker in data for marker in (
                    b"CaptureFixtureActivity", b"ImageFixtureProvider", b"ButtonArtFixtureProvider",
                    b"LocalModelFixtureProvider", b"MutableImageFixtureProvider",
                    b"ProjectionReplacementActivity",
                    b"EditingFixtureActivity",
                    b"OtherUidTouchActivity",
                    b"PhotoJobDocumentsProvider",
                ))
                legacy.extend(match.decode() for match in
                              re.findall(rb"Ldev/clickn/translate/(?!next/)[A-Za-z0-9_/$]+;", data))
    legacy = sorted(set(legacy))
    if legacy or fixture:
        raise ValueError("Unexpected legacy application reference or debug fixture in optimized artifact")
    return {"apk": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "zip_crc": "passed", "architecture": "arm64-v8a", "legacy_references": legacy,
            "legacy_reference_scope": "Unobfuscated DEX descriptors under the former application namespace",
            "debug_fixture": fixture, "all_native_16k": bool(native) and all(lib["page16k"] for lib in native), "native_libraries": native}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-native-pages", action="store_true",
                        help="Check every packaged ARM64 library for 16 KiB pages, including in debug APKs")
    arguments = parser.parse_args()
    report = check_native_pages(arguments.apk) if arguments.check_native_pages else audit(arguments.apk)
    result = json.dumps(report, indent=2)
    if arguments.output:
        arguments.output.write_text(result + "\n", encoding="utf-8")
    else:
        print(result)
