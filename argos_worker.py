"""Non-Qt companion process for packaged Argos translation on Windows."""

import contextlib
import json
import os
import sys
import traceback

# Prevent translater.py from dispatching back into this executable.
os.environ["CLICKNTRANSLATE_ARGOS_WORKER"] = "1"

import translater


def run_request(request):
    statuses = []
    try:
        result = translater._try_argos_translate_local(
            request.get("text", ""),
            request.get("source_code", ""),
            request.get("target_code", ""),
            status_callback=lambda message: statuses.append(str(message)),
            allow_install=bool(request.get("allow_install", False)),
        )
        if not translater._ensure_argos_available():
            raise RuntimeError(translater.argos_unavailable_reason())
        return {"result": result, "statuses": statuses, "error": ""}
    except Exception as exc:
        return {
            "result": None,
            "statuses": statuses,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(json.dumps({"error": "Argos worker request file is required."}))
        return 2
    try:
        with open(argv[0], "r", encoding="utf-8") as request_file:
            request = json.load(request_file)
        # Existing diagnostic prints must not corrupt the JSON protocol.
        with contextlib.redirect_stdout(sys.stderr):
            payload = run_request(request)
        print(json.dumps(payload, ensure_ascii=False))
        # A valid JSON error payload is still a successful protocol exchange;
        # the GUI will surface payload["error"] to the user.
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
