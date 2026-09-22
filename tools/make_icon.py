"""Render the app icon (u785/assets/icon.ico + icon.png) with Pillow.

A dark rounded tile with an amber six-bar signal meter, matching the in-app S-meter.
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "u785", "assets")
S = 1024  # draw large, downscale for crisp small sizes


def render() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=200, fill=(20, 23, 28, 255),
                        outline=(58, 42, 16, 255), width=18)
    bars, gap = 6, 34
    left, right, bottom = 170, S - 170, S - 210
    w = (right - left - gap * (bars - 1)) / bars
    for i in range(bars):
        h = 120 + (i + 1) * 88
        x = left + i * (w + gap)
        color = (255, 179, 71, 255) if i < 4 else (255, 138, 61, 255)
        d.rounded_rectangle((x, bottom - h, x + w, bottom), radius=22, fill=color)
    d.rounded_rectangle((170, S - 170, S - 170, S - 150), radius=10, fill=(107, 74, 28, 255))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = render()
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "icon.png"))
    img.save(os.path.join(OUT, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("written", OUT)


if __name__ == "__main__":
    main()
