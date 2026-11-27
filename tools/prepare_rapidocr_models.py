"""Fetch the exact verified PP-OCRv5 models used by all desktop builds."""
from pathlib import Path
import os
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from rapidocr_models import BASE_URL, MODEL_ASSETS, verify_model


def main():
    target = ROOT / 'assets' / 'rapidocr_models'
    target.mkdir(parents=True, exist_ok=True)
    for key, (relative, _size, _sha) in MODEL_ASSETS.items():
        final = target / Path(relative).name
        if final.is_file():
            try:
                verify_model(final, key)
                continue
            except RuntimeError:
                pass
        partial = final.with_suffix('.onnx.part')
        try:
            with urllib.request.urlopen(BASE_URL + relative, timeout=180) as response, partial.open('wb') as out:
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    out.write(chunk)
            verify_model(partial, key)
            os.replace(partial, final)
        finally:
            partial.unlink(missing_ok=True)
        print('Prepared', final.name, flush=True)


if __name__ == '__main__':
    main()
