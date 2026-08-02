"""Non-Qt companion process for packaged Argos translation on Windows."""

import contextlib
import json
import os
import sys
import traceback

# Prevent translater.py from dispatching back into this executable.
os.environ["CLICKNTRANSLATE_ARGOS_WORKER"] = "1"

import translater


def run_request(request, event_callback=None):
    statuses = []

    def emit_event(event):
        if not event_callback:
            return
        try:
            event_callback(event)
        except Exception:
            pass

    def status_callback(message):
        message = str(message)
        statuses.append(message)
        emit_event({"type": "status", "message": message})

    def progress_callback(message, downloaded_bytes, total_bytes):
        emit_event(
            {
                "type": "progress",
                "message": str(message),
                "downloaded_bytes": int(downloaded_bytes),
                "total_bytes": int(total_bytes),
            }
        )

    cancel_path = str(request.get("cancel_path") or "")

    def cancel_callback():
        return bool(cancel_path and os.path.exists(cancel_path))

    try:
        if not translater._ensure_argos_available():
            raise RuntimeError(translater.argos_unavailable_reason())
        action = str(request.get("action") or "translate").lower()
        if action == "probe":
            pair_installed = translater._get_translation_object(
                request.get("source_code", ""),
                request.get("target_code", ""),
            ) is not None
            return {
                "result": None,
                "pair_installed": pair_installed,
                "statuses": statuses,
                "error": "",
            }
        if action == "catalog":
            return {
                "packages": translater._argos_package_catalog_local(
                    refresh=bool(request.get("refresh", False))
                ),
                "statuses": statuses,
                "error": "",
            }
        if action == "install_packages":
            installed = translater._install_argos_packages_local(
                request.get("pairs") or [],
                status_callback=status_callback,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
            return {
                "installed": [list(pair) for pair in installed],
                "statuses": statuses,
                "error": "",
            }
        if action == "uninstall_packages":
            removed = translater._uninstall_argos_packages_local(
                request.get("pairs") or [],
                status_callback=status_callback,
            )
            return {
                "removed": [list(pair) for pair in removed],
                "statuses": statuses,
                "error": "",
            }
        if action != "translate":
            raise ValueError(f"Unknown Argos worker action: {action}")
        result = translater._try_argos_translate_local(
            request.get("text", ""),
            request.get("source_code", ""),
            request.get("target_code", ""),
            status_callback=status_callback,
            allow_install=bool(request.get("allow_install", False)),
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )
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

        event_path = str(request.get("event_path") or "")

        def write_event(event):
            if not event_path:
                return
            with open(event_path, "a", encoding="utf-8") as event_file:
                event_file.write(json.dumps(event, ensure_ascii=False) + "\n")

        # Existing diagnostic prints must not corrupt the JSON protocol.
        with contextlib.redirect_stdout(sys.stderr):
            payload = run_request(request, event_callback=write_event)
        print(json.dumps(payload, ensure_ascii=False))
        # A valid JSON error payload is still a successful protocol exchange;
        # the GUI will surface payload["error"] to the user.
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
