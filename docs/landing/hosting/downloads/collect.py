#!/usr/bin/env python3
"""Publish download totals from public GitHub release assets, without tokens."""

import argparse
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


PROJECTS = (
    ("clickntranslate", "Click’n’Translate"),
    ("xynapse", "Xynapse IDE"),
)
PACKAGE = re.compile(r"\.(exe|msi|msix|msixbundle|zip|dmg|pkg|appimage|deb|rpm|tar\.gz|tar\.xz|vsix)$", re.I)
SUPPORT = re.compile(r"verification|checksums?|sha256|signature|source|symbols|tesseract|debug", re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def github_pages(path):
    rows = []
    for page in range(1, 101):
        url = f"https://api.github.com/{path}?per_page=100&page={page}"
        request = Request(url, headers={
            "User-Agent": "Xynapse-Public-Download-Stats",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urlopen(request, timeout=25) as response:
            part = json.load(response)
        if not isinstance(part, list):
            raise ValueError("Unexpected GitHub response")
        rows.extend(part)
        if len(part) < 100:
            return rows
    raise ValueError("Pagination limit reached; refusing to publish a partial total")


def is_application(project, name):
    prefix = r"^(Click-n-Translate|ClicknTranslate)(?:[-.]|$)" if project == "clickntranslate" else r"^Xynapse(?:[-.]|Setup)"
    return bool(re.search(prefix, name, re.I) and PACKAGE.search(name) and not SUPPORT.search(name))


def platform(name):
    name = name.lower()
    if "macos" in name or name.endswith((".dmg", ".pkg")):
        return "macos"
    if "linux" in name or name.endswith((".appimage", ".deb", ".rpm")):
        return "linux"
    if "win" in name or name.endswith((".exe", ".msi", ".msix", ".msixbundle")):
        return "windows"
    return "other"


def collect(project, name):
    releases = github_pages(f"repos/jabrailkhalil/{project}/releases")
    counts = {key: 0 for key in ("windows", "macos", "linux", "other")}
    seen = set()
    release_count = 0
    for release in releases:
        if release.get("draft") or not release.get("published_at"):
            continue
        assets = release["assets"]
        if len(assets) >= 100:
            assets = github_pages(f"repos/jabrailkhalil/{project}/releases/{int(release['id'])}/assets")
        included = False
        for asset in assets:
            if not is_application(project, asset["name"]) or asset["id"] in seen:
                continue
            count = asset["download_count"]
            if type(count) is not int or count < 0:
                raise ValueError("Invalid download counter")
            seen.add(asset["id"])
            counts[platform(asset["name"])] += count
            included = True
        release_count += int(included)
    return {"id": project, "name": name, "kind": "download", "status": "ok",
            "total": sum(counts.values()), "platforms": counts, "releases": release_count,
            "checkedAt": now()}


def atomic_json(path, payload, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".downloads-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path("/var/lib/xynapse-downloads/state.json"))
    parser.add_argument("--output", type=Path, default=Path("/var/www/xynapse.online/statistics/downloads.json"))
    args = parser.parse_args()
    previous = {}
    if args.state.exists():
        previous = {p["id"]: p for p in json.loads(args.state.read_text(encoding="utf-8"))["projects"]}
    projects = []
    failures = 0
    for project, name in PROJECTS:
        try:
            entry = collect(project, name)
        except Exception:
            logging.exception("Download statistics unavailable for %s", project)
            failures += 1
            entry = dict(previous.get(project, {"id": project, "name": name, "kind": "download",
                                               "total": None, "platforms": {}, "checkedAt": None}))
            entry["status"] = "stale" if entry["total"] is not None else "unavailable"
        projects.append(entry)
    projects.append({"id": "goallog", "name": "goallog", "kind": "web", "status": "not_tracked",
                     "total": None, "platforms": {}, "checkedAt": None})
    payload = {"schemaVersion": 1, "generatedAt": now(), "refreshMinutes": 30,
               "projects": projects}
    atomic_json(args.state, payload, 0o600)
    atomic_json(args.output, payload, 0o644)
    print(json.dumps({"projects": [{"id": p["id"], "total": p["total"], "status": p["status"]}
                                  for p in projects], "output": str(args.output)}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
