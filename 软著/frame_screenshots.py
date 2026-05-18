from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/zed/all code/D 互影/steam-crawler/软著/screenshots")
RAW_DIR = ROOT / "raw"
FRAMED_DIR = ROOT / "framed"

SOFTWARE_NAME = "线上社区运营管理系统"

URLS = {
    "01-login-page": "http://127.0.0.1:5173/",
    "02-dashboard": "http://127.0.0.1:5173/",
    "03-games-list": "http://127.0.0.1:5173/games",
    "04-games-edit": "http://127.0.0.1:5173/games",
    "05-reviews-list": "http://127.0.0.1:5173/reviews",
    "06-reply-strategies": "http://127.0.0.1:5173/reply-strategies",
    "07-tasks": "http://127.0.0.1:5173/tasks",
    "08-task-queue": "http://127.0.0.1:5173/task-queue",
    "09-reply-records": "http://127.0.0.1:5173/reply-records",
    "10-users": "http://127.0.0.1:5173/users",
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def round_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def build_frame(raw_path: Path) -> None:
    base_name = raw_path.stem
    url = URLS.get(base_name, "http://127.0.0.1:5173/")

    raw = Image.open(raw_path).convert("RGB")
    raw = raw.crop((6, 6, raw.width - 6, raw.height - 6))
    header_height = 84
    outer_padding = 18
    corner_radius = 24
    frame_width = raw.width + outer_padding * 2
    frame_height = raw.height + outer_padding * 2 + header_height

    canvas = Image.new("RGB", (frame_width, frame_height), "#eef3fb")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (0, 0, frame_width - 1, frame_height - 1),
        radius=corner_radius,
        fill="#f7f9fc",
        outline="#d8e1ef",
        width=2,
    )
    draw.rounded_rectangle(
        (1, 1, frame_width - 2, header_height + outer_padding + 8),
        radius=corner_radius,
        fill="#eef3fb",
        outline="#d8e1ef",
        width=1,
    )

    dot_y = outer_padding + 24
    for idx, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        x = outer_padding + 18 + idx * 22
        draw.ellipse((x, dot_y, x + 12, dot_y + 12), fill=color)

    title_font = load_font(24)
    url_font = load_font(18)

    title = SOFTWARE_NAME
    title_box = (outer_padding + 110, outer_padding + 10, frame_width - outer_padding - 24, outer_padding + 36)
    draw.text((title_box[0], title_box[1]), title, font=title_font, fill="#1f2937")

    address_x1 = outer_padding + 110
    address_y1 = outer_padding + 38
    address_x2 = frame_width - outer_padding - 24
    address_y2 = outer_padding + 72
    draw.rounded_rectangle(
        (address_x1, address_y1, address_x2, address_y2),
        radius=16,
        fill="#ffffff",
        outline="#d5ddeb",
        width=1,
    )
    draw.text((address_x1 + 16, address_y1 + 7), url, font=url_font, fill="#64748b")

    shadow = Image.new("RGBA", (raw.width, raw.height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((6, 8, raw.width - 2, raw.height - 2), radius=18, fill=(15, 23, 42, 28))
    canvas.paste(shadow.convert("RGB"), (outer_padding, outer_padding + header_height))

    masked_raw = Image.new("RGB", raw.size, "#ffffff")
    masked_raw.paste(raw)
    raw_mask = round_rect_mask(raw.size, 18)
    canvas.paste(masked_raw, (outer_padding, outer_padding + header_height), raw_mask)

    FRAMED_DIR.mkdir(parents=True, exist_ok=True)
    canvas.save(FRAMED_DIR / f"{base_name}.png", quality=95)


def main() -> None:
    FRAMED_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(RAW_DIR.glob("*.png")):
        build_frame(path)


if __name__ == "__main__":
    main()
