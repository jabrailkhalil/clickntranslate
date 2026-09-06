"""Check the actual frozen Mac GUI and both helper executables, without network."""

import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile


def main():
    if sys.platform != "darwin":
        raise SystemExit("Run the native smoke check on macOS.")
    application = Path(sys.argv[1]).resolve()
    executables = application / "Contents" / "MacOS"
    report = Path("build/macos/smoke.json").resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    # Exercise Cocoa, not Qt's offscreen plugin. No screen capture/input requests.
    environment.pop("QT_QPA_PLATFORM", None)
    info = plistlib.loads((application / 'Contents/Info.plist').read_bytes())
    assert info['CFBundleExecutable'] == 'ClicknTranslate', info
    assert not info.get('LSBackgroundOnly') and not info.get('LSUIElement'), info
    # Exercise the same entry point as Finder and login startup. Running the
    # binary directly misses incorrect CFBundleExecutable/background metadata.
    report.unlink(missing_ok=True)
    # A checkout on Desktop/Documents is TCC-protected for a Finder-launched
    # app. Save its fixtures in a temporary directory so this noninteractive
    # smoke test never asks for access to the developer's personal folders.
    with tempfile.TemporaryDirectory(prefix='cnt-mac-render-') as temporary:
        native_report = Path(temporary) / report.name
        try:
            subprocess.run(['/usr/bin/open', '-n', '-W', '-a', str(application),
                            '--stdout', str(Path(temporary) / 'smoke-stdout.log'),
                            '--stderr', str(Path(temporary) / 'smoke-stderr.log'),
                            '--args', '--smoke-test', str(native_report)],
                           env=environment, check=True,
                           timeout=300 if environment.get('CLICKNTRANSLATE_EXTENDED_SMOKE') == '1' else 120)
        finally:
            for result in Path(temporary).iterdir():
                shutil.copy2(result, report.parent / result.name)
    if not report.exists():
        raise RuntimeError('The LaunchServices smoke did not finish; see build/macos/smoke-stderr.log')
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["vision"] == "ok", payload
    payload['launchservices'] = 'ok'
    with tempfile.TemporaryDirectory(prefix="cnt-mac-workers-") as temporary:
        root = Path(temporary)
        # Argos creates its cache/config folders during import. Keep this build
        # check independent of any language packages installed by the developer.
        for variable, directory in (('XDG_DATA_HOME', 'data'), ('XDG_CACHE_HOME', 'cache'),
                                    ('XDG_CONFIG_HOME', 'config')):
            environment[variable] = str(root / directory)
        from PIL import Image, ImageDraw, ImageFont
        image_path = root / 'ocr.png'
        image = Image.new('RGB', (900, 130), 'white')
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 54)
        ImageDraw.Draw(image).text((30, 25), 'CLICK TRANSLATE', font=font, fill='black')
        image.save(image_path)
        for executable, request in (
            ("OcrWorker", {"action": "recognize", "engine": "rapidocr", "root_dir": str(root),
                           "images": [{"label": "smoke", "path": str(image_path)}]}),
            ("ArgosWorker", {"action": "probe", "source_code": "en", "target_code": "ru"}),
        ):
            request_path = root / f"{executable}.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            result = subprocess.run([str(executables / executable), str(request_path)],
                                    capture_output=True, text=True, check=True, timeout=90, env=environment)
            response = json.loads(result.stdout)
            assert not response.get("error"), (executable, response, result.stderr)
            if executable == "OcrWorker":
                assert 'TRANSLATE' in ' '.join(item.get('text', '') for item in response.get('results', [])).upper(), response
            else:
                assert "pair_installed" in response, (executable, response)
            payload[executable] = 'ok'
    report.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print("Verified Cocoa GUI, settings, Vision recognition, Carbon registration, RapidOCR and Argos helpers.")


if __name__ == "__main__":
    main()
