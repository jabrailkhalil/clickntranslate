"""Pack supplied, generated static mascots without repainting their artwork.

Input JSON lists source PNGs, preserved masters and packaged Android destinations.
Only transparent-margin cropping, uniform downscaling and centering are applied.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def workspace_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Destination outside project: {relative}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def pack(manifest):
    records = []
    for asset in manifest["assets"]:
        master = workspace_path(asset["master"])
        source = Path(asset.get("generatedSource", master))
        reference = workspace_path(asset["reference"])
        reference_source = Path(asset.get("referenceSource", reference))
        if source.resolve() != master:
            shutil.copyfile(source, master)
        if reference_source.resolve() != reference:
            shutil.copyfile(reference_source, reference)
        with Image.open(master) as opened:
            image = opened.convert("RGBA")
        alpha = image.getchannel("A")
        minimum, maximum = alpha.getextrema()
        if minimum != 0 or maximum < 128:
            raise ValueError(f"Expected transparent PNG: {master}")
        bounds = alpha.getbbox()
        if bounds is None:
            raise ValueError(f"Empty mascot: {master}")
        cropped = image.crop(bounds)
        cropped.thumbnail((464, 464), Image.Resampling.LANCZOS)
        final = Image.new("RGBA", (512, 512))
        final.alpha_composite(cropped, ((512-cropped.width)//2, (512-cropped.height)//2))
        packaged = workspace_path(asset["packaged"])
        final.save(packaged, optimize=True)
        records.append({key: asset[key] for key in ("id", "master", "packaged", "reference", "referenceDesktopPath", "prompt")} | {
            "masterSha256": hashlib.sha256(master.read_bytes()).hexdigest(),
            "packagedSha256": hashlib.sha256(packaged.read_bytes()).hexdigest(),
            "referenceSha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
            "crop": bounds,
            "packedSize": [512, 512],
        })
        print(asset["id"], image.size, "->", packaged.relative_to(ROOT))
    return {key: manifest[key] for key in ("date", "mode", "sourceCommit")} | {"assets": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = pack(json.loads(args.manifest.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
