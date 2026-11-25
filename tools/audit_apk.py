"""Audit the actual packaged artifact without executing or trusting old application binaries."""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path


def audit(path: Path) -> dict:
    native = []
    legacy = []
    fixture = False
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for name in archive.namelist():
            if name.startswith("lib/") and name.endswith(".so"):
                data = archive.read(name)
                if data[:5] != b"\x7fELF\x02":
                    raise ValueError(f"Expected ELF64: {name}")
                header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
                if header[2] != 183 or not name.startswith("lib/arm64-v8a/"):
                    raise ValueError(f"Expected ARM64: {name}")
                load_alignments = []
                for index in range(header[10]):
                    segment = struct.unpack_from("<IIQQQQQQ", data, header[5] + index * header[9])
                    if segment[0] == 1:
                        load_alignments.append(segment[7])
                native.append({"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                               "load_alignments": load_alignments, "page16k": all(value >= 16384 for value in load_alignments)})
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
            "debug_fixture": fixture, "all_native_16k": all(lib["page16k"] for lib in native), "native_libraries": native}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = json.dumps(audit(arguments.apk), indent=2)
    if arguments.output:
        arguments.output.write_text(result + "\n", encoding="utf-8")
    else:
        print(result)
