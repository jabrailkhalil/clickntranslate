"""Check the active Android source boundary and optionally compare code with saved Git refs."""
import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = {".kt", ".kts", ".java", ".xml", ".cpp", ".cc", ".c", ".h", ".hpp", ".cmake"}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def check(references, allow_reuse=False):
    namespace = re.search(r'\bnamespace\s*=\s*"([^"]+)"', (ROOT / 'app/build.gradle.kts').read_text(encoding='utf-8-sig'))[1]
    paths = sorted({p for p in git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "app").decode().split("\0") if p})
    errors = []
    code = []
    for name in paths:
        path = ROOT / name
        if not path.is_file():
            continue  # A staged/working-tree deletion contributes no active build input.
        if path.suffix.lower() in {".jar", ".aar", ".so", ".apk"}:
            errors.append(f"Precompiled application artifact in source module: {name}")
        if (name.startswith("app/src/") or name == "app/build.gradle.kts") and (path.suffix.lower() in SOURCE or path.name == "CMakeLists.txt"):
            code.append(name)
            if path.suffix in {".kt", ".java"}:
                package = re.search(r"(?m)^package\s+([^\s;]+)", path.read_text(encoding="utf-8-sig"))
                if not package or not (package[1] == namespace or package[1].startswith(namespace + ".")):
                    errors.append(f"Unexpected application source namespace: {name}")
    hashes = {git("hash-object", f"--path={name}", name).decode().strip(): name for name in code}
    comparisons = []
    for reference in references:
        matches = []
        for entry in git("ls-tree", "-r", "-z", reference, "--", "app").decode().split("\0"):
            if not entry:
                continue
            metadata, name = entry.split("\t", 1)
            kind, object_id = metadata.split()[1:]
            if kind == "blob" and (Path(name).suffix.lower() in SOURCE or Path(name).name == "CMakeLists.txt") and object_id in hashes:
                matches.append({"active": hashes[object_id], "reference_path": name})
        comparisons.append({"reference": reference, "matching_source_files": matches})
        if not allow_reuse:
            errors.extend(f"Source duplicated from {reference}: {item['active']}" for item in matches)
    return {"module": "app", "source_files_checked": len(code), "namespace": namespace,
            "project_source_reuse_authorized": allow_reuse,
            "comparisons": comparisons, "errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-project-reuse", action="store_true", help="Report expected archive matches without treating owner-authorized reuse as an error")
    arguments = parser.parse_args()
    result = check(arguments.reference, arguments.allow_project_reuse)
    report = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(report, encoding="utf-8")
    print(report, end="")
    raise SystemExit(1 if result["errors"] else 0)
