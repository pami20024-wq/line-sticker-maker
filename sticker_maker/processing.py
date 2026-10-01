from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sprite_gen.frames.cutout import cutout as sprite_gen_cutout


FONT_CANDIDATES = (
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def choose_chroma_key(reference: Path, setting: object, candidates: list[list[int]]) -> tuple[int, int, int]:
    """Choose the candidate furthest from reference colors, following sprite-gen's key-selection rule."""
    if setting != "auto":
        values = tuple(int(value) for value in setting)  # type: ignore[union-attr]
        if len(values) != 3 or any(value < 0 or value > 255 for value in values):
            raise ValueError("image.chroma_key は auto または0〜255のRGB 3値にしてください")
        return values
    choices = [tuple(map(int, candidate)) for candidate in candidates]
    if not reference.is_file():
        return choices[0]
    with Image.open(reference) as opened:
        sample = opened.convert("RGBA")
        sample.thumbnail((256, 256), Image.Resampling.LANCZOS)
        sample_pixels = sample.load()
        colors = [sample_pixels[x, y][:3] for y in range(sample.height) for x in range(sample.width)
                  if sample_pixels[x, y][3] >= 128]
    if not colors:
        return choices[0]
    # A low percentile catches small but important features better than average distance.
    def safety(key: tuple[int, int, int]) -> float:
        distances = sorted(sum((color[i] - key[i]) ** 2 for i in range(3)) for color in colors)
        return distances[max(0, len(distances) // 100)]
    return max(choices, key=safety)


def resolve_font(configured: str | None) -> str:
    candidates = ([configured] if configured else []) + list(FONT_CANDIDATES)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("日本語フォントが見つかりません。config.yaml の text.font_path を設定してください")


def remove_chroma(image: Image.Image, key: tuple[int, int, int]) -> Image.Image:
    """Use sprite-gen's production cutout engine for soft-alpha unmix and despill."""
    key_name = {(0, 255, 0): "green", (255, 0, 255): "magenta"}.get(tuple(key))
    if key_name is None:
        raise ValueError("sprite-genで使用できるクロマキーは緑またはマゼンタです")
    with tempfile.TemporaryDirectory(prefix="line-sticker-cutout-") as directory:
        source = Path(directory) / "source.png"
        destination = Path(directory) / "cutout.png"
        image.convert("RGBA").save(source)
        try:
            sprite_gen_cutout(
                source,
                destination,
                key=key_name,
                decontam="auto",
            )
        except SystemExit as exc:
            raise ValueError(f"sprite-genによる背景透過に失敗しました: {exc}") from exc
        with Image.open(destination) as result:
            return result.convert("RGBA")


def trim_alpha(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("画像に不透明な内容がありません")
    return image.crop(bbox)


def is_valid_resume_image(path: Path, size: tuple[int, int], margin: int) -> bool:
    """Never treat a partial/corrupt file left by an interrupted run as complete."""
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.size != size:
                return False
            bbox = image.getchannel("A").getbbox()
            return bool(
                bbox
                and bbox[0] >= margin and bbox[1] >= margin
                and size[0] - bbox[2] >= margin and size[1] - bbox[3] >= margin
            )
    except (OSError, ValueError):
        return False


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    result = image.copy()
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def _font_for(text: str, font_path: str, max_width: int, max_size: int, min_size: int, stroke: int) -> ImageFont.FreeTypeFont:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size)
        box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font, stroke_width=stroke)
        if box[2] - box[0] <= max_width:
            return font
    return ImageFont.truetype(font_path, min_size)


def compose_sticker(source: Image.Image, text: str, config: dict, font_path: str) -> Image.Image:
    width, height = map(int, config["image"]["sticker_size"])
    margin = int(config["image"]["safe_margin"])
    text_cfg = config["text"]
    stroke = int(text_cfg["stroke_width"])
    font = _font_for(text, font_path, width - 2 * margin, int(text_cfg["max_font_size"]), int(text_cfg["min_font_size"]), stroke)
    draw_probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    box = draw_probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    text_height = box[3] - box[1]
    available = (width - 2 * margin, height - text_height - 3 * margin)
    character = _fit(trim_alpha(source.convert("RGBA")), available)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - character.width) // 2
    y = margin + max(0, (available[1] - character.height) // 2)
    canvas.alpha_composite(character, (x, y))
    draw = ImageDraw.Draw(canvas)
    text_box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    tx = (width - (text_box[2] - text_box[0])) // 2
    ty = height - margin - text_height - text_box[1]
    draw.text((tx, ty), text, font=font, fill=tuple(text_cfg["fill"]), stroke_width=stroke, stroke_fill=tuple(text_cfg["stroke_fill"]))
    return canvas


def save_optimized(image: Image.Image, path: Path, max_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".png", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
    image.save(temporary, "PNG", optimize=True, compress_level=9)
    if temporary.stat().st_size <= max_bytes:
        temporary.replace(path)
        return
    # Palette PNG keeps alpha and sharply reduces cartoon artwork size.
    # Reduce color entropy but convert back to RGBA because LINE accepts RGB/RGBA, not mode P.
    quantized = image.quantize(
        colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
    ).convert("RGBA")
    quantized.save(temporary, "PNG", optimize=True, compress_level=9)
    if temporary.stat().st_size > max_bytes:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"PNGを1MB未満へ最適化できません: {path}")
    temporary.replace(path)


def derived_icon(sticker: Image.Image, size: tuple[int, int], margin: int) -> Image.Image:
    subject = trim_alpha(sticker.convert("RGBA"))
    subject = _fit(subject, (size[0] - 2 * margin, size[1] - 2 * margin))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(subject, ((size[0] - subject.width) // 2, (size[1] - subject.height) // 2))
    return canvas


def create_preview(output: Path, stickers: list[Path], font_path: str) -> Path:
    cell_w, cell_h, columns = 200, 190, 6
    rows = 4
    sheet = Image.new("RGBA", (cell_w * columns, cell_h * rows), (240, 237, 246, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(font_path, 22)
    for index, path in enumerate(stickers):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((180, 150), Image.Resampling.LANCZOS)
        col, row = index % columns, index // columns
        x = col * cell_w + (cell_w - image.width) // 2
        y = row * cell_h + 4
        sheet.alpha_composite(image, (x, y))
        label = path.stem
        box = draw.textbbox((0, 0), label, font=font)
        draw.text((col * cell_w + (cell_w - box[2]) // 2, row * cell_h + 160), label, font=font, fill=(55, 35, 70, 255))
    preview = output / "preview.png"
    sheet.convert("RGB").save(preview, optimize=True)
    return preview


def create_zip(output: Path, max_bytes: int) -> Path:
    destination = output / "line_stickers.zip"
    temporary = destination.with_suffix(".zip.tmp")
    expected = [output / f"{n:02d}.png" for n in range(1, 25)] + [output / "main.png", output / "tab.png"]
    missing = [path.name for path in expected if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"ZIP対象が不足しています: {', '.join(missing)}")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in expected:
            archive.write(path, path.name)
    if temporary.stat().st_size > max_bytes:
        temporary.unlink()
        raise ValueError("ZIPが60MBを超えました")
    temporary.replace(destination)
    return destination
