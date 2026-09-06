"""Windows resources for our frozen executables; this is not a code signature."""

import re


def make_version_info(version, filename, description):
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable,
        VarFileInfo, VarStruct, VSVersionInfo,
    )

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", version):
        raise ValueError("Expected a three- or four-part numeric version")
    parts = tuple(int(part) for part in version.split("."))
    parts += (0,) * (4 - len(parts))
    if any(part > 65535 for part in parts):
        raise ValueError("Windows version components must not exceed 65535")
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=parts, prodvers=parts, mask=0x3F, flags=0,
            OS=0x40004, fileType=0x1, subtype=0, date=(0, 0),
        ),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "Jabrail Digital"),
                StringStruct("FileDescription", description),
                StringStruct("FileVersion", ".".join(map(str, parts))),
                StringStruct("InternalName", filename.removesuffix(".exe")),
                StringStruct("OriginalFilename", filename),
                StringStruct("ProductName", "Click'n'Translate"),
                StringStruct("ProductVersion", version),
                StringStruct("LegalCopyright", "Jabrail Digital. GPL-3.0-only."),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
