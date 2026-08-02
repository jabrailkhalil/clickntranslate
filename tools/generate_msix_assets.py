from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "icons" / "icon.png"
OUTPUT = ROOT / "installer" / "msix" / "Assets"
BACKGROUND = (17, 17, 17, 255)


ASSETS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
    "Square310x310Logo.png": (310, 310),
    "SplashScreen.png": (620, 300),
}


def render_asset(source, size):
    width, height = size
    canvas = Image.new("RGBA", size, BACKGROUND)
    icon_size = max(1, int(min(width, height) * 0.82))
    icon = source.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    canvas.alpha_composite(icon, ((width - icon_size) // 2, (height - icon_size) // 2))
    return canvas.convert("RGB")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    for name, size in ASSETS.items():
        render_asset(source, size).save(OUTPUT / name, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
