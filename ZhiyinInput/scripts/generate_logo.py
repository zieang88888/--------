# -*- coding: utf-8 -*-
"""Generate raster and Windows icon assets for the Zhiyin logo."""

from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "assets" / "branding"
BASE_SIZE = 1024
RENDER_SCALE = 4
PNG_SIZES = (1024, 512, 256, 128, 64, 32, 16)
ICO_SIZES = ((256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16))

VERMILION = "#C94F45"
INK = "#242424"
WARM_WHITE = "#FFF8F2"


def scaled(value):
    return round(value * RENDER_SCALE)


def scaled_box(left, top, right, bottom):
    return tuple(scaled(value) for value in (left, top, right, bottom))


def render_master():
    canvas_size = scaled(BASE_SIZE)
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        scaled_box(64, 64, 960, 960),
        radius=scaled(196),
        fill=VERMILION,
    )

    key_origins = (244, 436, 628)
    for row, top in enumerate(key_origins):
        for column, left in enumerate(key_origins):
            color = INK if row == 1 and column == 1 else WARM_WHITE
            draw.rounded_rectangle(
                scaled_box(left, top, left + 152, top + 152),
                radius=scaled(38),
                fill=color,
            )

    sound_bars = (
        (466, 494, 478, 530),
        (486, 478, 498, 546),
        (506, 464, 518, 560),
        (526, 478, 538, 546),
        (546, 494, 558, 530),
    )
    for box in sound_bars:
        draw.rounded_rectangle(
            scaled_box(*box),
            radius=scaled(6),
            fill=WARM_WHITE,
        )

    return image


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    master = render_master()

    for size in PNG_SIZES:
        output = OUTPUT_DIR / f"zhiyin-logo-{size}.png"
        image = master.resize((size, size), Image.Resampling.LANCZOS)
        image.save(output, format="PNG", optimize=True)

    master.resize((1024, 1024), Image.Resampling.LANCZOS).save(
        OUTPUT_DIR / "zhiyin.ico",
        format="ICO",
        sizes=ICO_SIZES,
    )

    print(f"Generated {len(PNG_SIZES)} PNG files and zhiyin.ico in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
