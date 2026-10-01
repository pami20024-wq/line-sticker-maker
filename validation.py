#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from PIL import Image

from sticker_maker.settings import ROOT, load_config


def validate_file(path: Path, expected_size: tuple[int, int] | None, maximum: tuple[int, int], max_bytes: int,
                  safe_margin: int = 0) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"{path.name}: ファイルがありません"]
    if path.stat().st_size > max_bytes:
        errors.append(f"{path.name}: {path.stat().st_size} bytes（1MB超過）")
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                errors.append(f"{path.name}: PNGではありません ({image.format})")
            if image.mode not in ("RGB", "RGBA"):
                errors.append(f"{path.name}: モードがRGB/RGBAではありません ({image.mode})")
            width, height = image.size
            if expected_size and image.size != expected_size:
                errors.append(f"{path.name}: サイズは{expected_size}必須です（実際: {image.size}）")
            if width > maximum[0] or height > maximum[1]:
                errors.append(f"{path.name}: 最大サイズ{maximum}を超えています（実際: {image.size}）")
            if width % 2 or height % 2:
                errors.append(f"{path.name}: 縦横は偶数必須です（実際: {image.size}）")
            if image.mode != "RGBA" or image.getchannel("A").getextrema()[0] != 0:
                errors.append(f"{path.name}: 完全透明ピクセルを持つRGBA画像ではありません")
            elif safe_margin:
                bbox = image.getchannel("A").getbbox()
                if not bbox:
                    errors.append(f"{path.name}: 表示内容がありません")
                elif min(bbox[0], bbox[1], width - bbox[2], height - bbox[3]) < safe_margin:
                    errors.append(f"{path.name}: 内容の周囲に{safe_margin}px以上の安全余白がありません (bbox={bbox})")
        # Pillow requires verify() immediately after open(), before pixel access.
        with Image.open(path) as verification_image:
            verification_image.verify()
    except Exception as exc:
        errors.append(f"{path.name}: 画像を読み込めません ({exc})")
    return errors


def validate(output: Path, config: dict) -> list[str]:
    errors: list[str] = []
    expected_stickers = {f"{number:02d}.png" for number in range(1, 25)}
    actual_stickers = {path.name for path in output.glob("[0-9][0-9].png")}
    if actual_stickers != expected_stickers:
        missing = sorted(expected_stickers - actual_stickers)
        extra = sorted(actual_stickers - expected_stickers)
        if missing: errors.append(f"スタンプ不足: {', '.join(missing)}")
        if extra: errors.append(f"不正なスタンプ名: {', '.join(extra)}")
    max_bytes = int(config["image"]["max_file_bytes"])
    sticker_max = tuple(config["image"]["sticker_size"])
    safe_margin = int(config["image"]["safe_margin"])
    for name in sorted(expected_stickers):
        errors.extend(validate_file(output / name, None, sticker_max, max_bytes, safe_margin))
    for name, size in (("main.png", tuple(config["image"]["main_size"])), ("tab.png", tuple(config["image"]["tab_size"]))):
        errors.extend(validate_file(output / name, size, size, max_bytes, min(10, safe_margin)))
    archive = output / "line_stickers.zip"
    if not archive.is_file():
        errors.append("line_stickers.zip: ファイルがありません")
    elif archive.stat().st_size > int(config["image"]["max_zip_bytes"]):
        errors.append("line_stickers.zip: 60MBを超えています")
    else:
        with zipfile.ZipFile(archive) as zf:
            expected_zip = expected_stickers | {"main.png", "tab.png"}
            if set(zf.namelist()) != expected_zip:
                errors.append("line_stickers.zip: 内容またはファイル名が不正です")
            if zf.testzip() is not None:
                errors.append("line_stickers.zip: 破損したファイルがあります")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="LINEスタンプ画像の仕様を検証します")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    output = Path(args.output) if args.output else ROOT / config["paths"]["output"]
    errors = validate(output, config)
    if errors:
        print("LINE STICKER VALIDATION: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("LINE STICKER VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
