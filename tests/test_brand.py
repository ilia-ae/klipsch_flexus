"""Brand images shipped with the integration (HA 2026.3+ serves them from ``brand/``).

Home Assistant reads ``custom_components/<domain>/brand/*.png`` before the brands
CDN. The dark-theme variants matter: the light icon is a black wordmark that is
invisible on a dark background.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

BRAND_DIR = Path(__file__).parent.parent / "custom_components" / "klipsch_flexus" / "brand"
# Names HA's brands view accepts (homeassistant/components/brands/const.py ALLOWED_IMAGES).
ALLOWED = {
    "icon.png",
    "logo.png",
    "icon@2x.png",
    "logo@2x.png",
    "dark_icon.png",
    "dark_logo.png",
    "dark_icon@2x.png",
    "dark_logo@2x.png",
}
EXPECTED = {"icon.png": 256, "icon@2x.png": 512, "dark_icon.png": 256, "dark_icon@2x.png": 512}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOR_TYPE_RGBA = 6


def _png_header(path: Path) -> tuple[int, int, int]:
    """Return (width, height, color type) from the PNG IHDR chunk."""
    data = path.read_bytes()[:33]
    assert data[:8] == PNG_SIGNATURE, f"{path.name} is not a PNG"
    assert data[12:16] == b"IHDR"
    width, height, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, color_type


def test_brand_dir_has_only_known_images() -> None:
    files = {p.name for p in BRAND_DIR.iterdir()}
    assert files <= ALLOWED, f"HA ignores {files - ALLOWED}"
    assert set(EXPECTED) <= files


@pytest.mark.parametrize(("name", "size"), sorted(EXPECTED.items()))
def test_brand_icon_is_square_transparent_png(name: str, size: int) -> None:
    assert _png_header(BRAND_DIR / name) == (size, size, COLOR_TYPE_RGBA)


@pytest.mark.parametrize("name", ["icon.png", "icon@2x.png"])
def test_dark_icon_is_the_light_icon_in_white(name: str) -> None:
    """Same shape (alpha), light = black ink, dark = white ink."""
    image = pytest.importorskip("PIL.Image")
    light = image.open(BRAND_DIR / name).convert("RGBA")
    dark = image.open(BRAND_DIR / f"dark_{name}").convert("RGBA")
    assert light.getchannel("A").tobytes() == dark.getchannel("A").tobytes()
    for img, ink in ((light, 0), (dark, 255)):
        alpha = img.getchannel("A").tobytes()
        for channel in "RGB":
            values = img.getchannel(channel).tobytes()
            assert all(v == ink for v, a in zip(values, alpha, strict=True) if a), f"{channel} ink of {img}"
