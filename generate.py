#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw

from sticker_maker.generator import prompt_for, request_image, save_api_image
from sticker_maker.processing import (compose_sticker, create_preview, create_zip, derived_icon,
                                      choose_chroma_key, is_valid_resume_image, remove_chroma,
                                      resolve_font, save_optimized)
from sticker_maker.settings import ROOT, load_config, load_stickers


def demo_character(index: int) -> Image.Image:
    """Offline smoke-test art; deliberately simple and never used unless --demo is requested."""
    image = Image.new("RGBA", (720, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    bounce = (index % 3 - 1) * 8
    draw.ellipse((190, 190 + bounce, 530, 570 + bounce), fill=(67, 48, 76, 255), outline=(30, 18, 37, 255), width=18)
    draw.polygon(((220, 250), (245, 90), (335, 230)), fill=(67, 48, 76, 255), outline=(30, 18, 37, 255))
    draw.polygon(((385, 230), (475, 90), (500, 250)), fill=(67, 48, 76, 255), outline=(30, 18, 37, 255))
    draw.ellipse((260, 290, 325, 370), fill=(166, 99, 225, 255))
    draw.ellipse((395, 290, 460, 370), fill=(166, 99, 225, 255))
    draw.arc((310, 360, 410, 440), 10 if index % 4 else 180, 170 if index % 4 else 350, fill=(255, 210, 225, 255), width=14)
    draw.ellipse((240, 500, 330, 660), fill=(67, 48, 76, 255), outline=(30, 18, 37, 255), width=14)
    draw.ellipse((390, 500, 480, 660), fill=(67, 48, 76, 255), outline=(30, 18, 37, 255), width=14)
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIで24個のLINEスタンプを生成・加工・梱包します")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--force", action="store_true", help="完成済み画像も再生成します")
    parser.add_argument("--demo", action="store_true", help="APIを使わず処理と検証用サンプルを生成します")
    parser.add_argument("--zip-only", action="store_true", help="既存画像からZIPとpreviewだけを再作成します")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    config = load_config(args.config)
    stickers = load_stickers()
    output = ROOT / config["paths"]["output"]
    raw = ROOT / config["paths"]["raw"]
    reference = ROOT / config["paths"]["reference"]
    chroma_key = choose_chroma_key(reference, config["image"]["chroma_key"], config["image"]["chroma_candidates"])
    output.mkdir(parents=True, exist_ok=True)
    font_path = resolve_font(config["text"]["font_path"])
    max_bytes = int(config["image"]["max_file_bytes"])
    sticker_size = tuple(config["image"]["sticker_size"])
    safe_margin = int(config["image"]["safe_margin"])

    client = None
    if not args.demo and not args.zip_only:
        if not os.getenv("OPENAI_API_KEY"):
            print("エラー: OPENAI_API_KEY が未設定です。.env.example を参考に設定してください。", file=sys.stderr)
            return 2
        from openai import OpenAI
        client = OpenAI()

    if not args.zip_only:
        identity = reference if reference.is_file() else raw / "identity.png"
        for number, sticker in enumerate(stickers, 1):
            destination = output / f"{sticker.id}.png"
            if not args.force and is_valid_resume_image(destination, sticker_size, safe_margin):
                print(f"[{sticker.id}/24] 完成済みのためスキップ")
                continue
            if not args.force and destination.exists():
                print(f"[{sticker.id}/24] 不完全な既存画像を再生成")
            print(f"[{sticker.id}/24] {sticker.text} を生成")
            raw_path = raw / f"{sticker.id}.png"
            if args.demo:
                source = demo_character(number)
            else:
                refs = [identity] if identity.is_file() else []
                save_api_image(request_image(client, prompt_for(sticker.action, bool(refs), chroma_key), config, refs), raw_path)
                source = Image.open(raw_path).convert("RGBA")
                source = remove_chroma(source, chroma_key)
                if number == 1 and not reference.is_file():
                    raw.mkdir(parents=True, exist_ok=True)
                    source.save(identity)
            result = compose_sticker(source, sticker.text, config, font_path)
            save_optimized(result, destination, max_bytes)

        first = Image.open(output / "01.png").convert("RGBA")
        margin = safe_margin
        main = derived_icon(first, tuple(config["image"]["main_size"]), margin)
        tab = derived_icon(first, tuple(config["image"]["tab_size"]), max(10, margin))
        save_optimized(main, output / "main.png", max_bytes)
        save_optimized(tab, output / "tab.png", max_bytes)

    sticker_paths = [output / f"{number:02d}.png" for number in range(1, 25)]
    create_preview(output, sticker_paths, font_path)
    archive = create_zip(output, int(config["image"]["max_zip_bytes"]))
    print(f"完了: {output}\nZIP: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
