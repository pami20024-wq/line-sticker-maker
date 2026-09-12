from __future__ import annotations

import base64
import random
import time
from pathlib import Path

from PIL import Image


BASE_PROMPT = """Create one Japanese messaging sticker illustration. The exact same single character must be preserved across the set: a cute 2.5–3-head-tall chibi character, identical hair/fur, eye color, outfit, accessories, palette, bold clean outline, and polished vibrant style. Show a large instantly readable expression and gesture. No words, letters, captions, speech bubbles, scenery, extra characters, watermark, shadow, or cropped body. Center the entire character with generous clear padding. Place it on a perfectly uniform solid #00FF00 chroma-key background with no gradient, texture, or green on the character."""


def prompt_for(action: str, has_reference: bool) -> str:
    reference_instruction = (
        "Use the supplied reference image as the strict identity and design reference; change only expression and pose. "
        if has_reference else
        "Establish one distinctive reusable character design and keep it suitable as the identity master. "
    )
    return f"{BASE_PROMPT}\n{reference_instruction}Expression and pose: {action}."


def request_image(client, prompt: str, config: dict, references: list[Path]) -> bytes:
    api = config["openai"]
    attempts = int(api["retries"])
    for attempt in range(attempts):
        try:
            if references:
                streams = [path.open("rb") for path in references]
                try:
                    response = client.images.edit(
                        model=api["model"], image=streams, prompt=prompt,
                        size=api["size"], quality=api["quality"]
                    )
                finally:
                    for stream in streams:
                        stream.close()
            else:
                response = client.images.generate(
                    model=api["model"], prompt=prompt, size=api["size"], quality=api["quality"]
                )
            item = response.data[0]
            if getattr(item, "b64_json", None):
                return base64.b64decode(item.b64_json)
            raise RuntimeError("画像APIの応答に画像データがありません")
        except Exception as exc:
            if attempt + 1 == attempts:
                raise RuntimeError(f"画像APIは{attempts}回失敗しました: {exc}") from exc
            delay = float(api["retry_base_seconds"]) * (2 ** attempt) + random.random()
            print(f"  APIエラー。{delay:.1f}秒後に再試行します ({attempt + 1}/{attempts}): {exc}")
            time.sleep(delay)
    raise AssertionError("unreachable")


def save_api_image(data: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    with Image.open(path) as image:
        image.verify()

