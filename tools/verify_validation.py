"""Verify saved QA evidence bytes and the referenced application Git tree without running tests."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def local_file(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"Evidence must exist inside this checkout: {name}")
    return path


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            result.update(chunk)
    return result.hexdigest()


def verify(path):
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    commit = report["implementation_commit"]
    if not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", commit):
        raise ValueError("Report must identify a full Git commit")
    actual = subprocess.check_output(["git", "rev-parse", f"{commit}:app"], cwd=ROOT, text=True).strip()
    if actual != report["application_tree"]:
        raise ValueError(f"Application tree does not match its source commit: {path}")
    checks = [(item["log"], item["sha256"]) for item in report["builds"]]
    checks += [(item["log"], item["sha256"]) for item in report["android"].values()]
    for item in report["android"].values():
        source = item.get("source")
        if source is None:
            continue
        checks.append((source["manifest"], source["sha256"]))
        manifest = json.loads(local_file(source["manifest"]).read_text(encoding="utf-8-sig"))
        source_commit = source["implementation_commit"]
        if not re.fullmatch(r"[a-f0-9]{40}", source_commit) or manifest["implementation_commit"] != source_commit:
            raise ValueError("Android run must identify its actual APK source commit")
        tree = subprocess.check_output(["git", "rev-parse", f"{source_commit}:app"], cwd=ROOT, text=True).strip()
        if tree != source["application_tree"] or tree != manifest["application_tree"]:
            raise ValueError("Android source tree does not match its saved manifest")
        changed = subprocess.check_output(["git", "diff", "--name-only", source_commit, commit, "--", "app",
            "build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradle", "gradlew", "gradlew.bat"],
            cwd=ROOT, text=True).splitlines()
        if any(not name.startswith("app/src/androidTest/") for name in changed) or not source["target_inputs_unchanged"]:
            raise ValueError("Android runs use different target application inputs")
        hashes = {re.split(r"[/\\]", value["Path"])[-1]: value["Hash"].lower() for value in manifest["artifacts"]}
        if hashes != source["artifact_hashes"] or any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes.values()):
            raise ValueError("Android artifact identities differ from the saved source manifest")
    checks += [(f'{group["directory"]}/TEST-{suite["name"]}.xml', suite["sha256"])
               for group in report["unit"] for suite in group["suites"]]
    for name, expected in checks:
        if not re.fullmatch(r"[a-f0-9]{64}", expected) or digest(local_file(name)) != expected:
            raise ValueError(f"Evidence digest mismatch: {name}")
    return {"report": path.relative_to(ROOT).as_posix(), "implementation_commit": commit,
            "application_tree": actual, "verified_files": len(checks), "result": "passed",
            "scope": "Source identity and saved evidence integrity; does not rerun tests"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([verify(local_file(path)) for path in args.reports], indent=2))
