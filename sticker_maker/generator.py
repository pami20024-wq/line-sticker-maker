from __future__ import annotations

import base64
import random
import tempfile
import time
from pathlib import Path

from PIL import Image


BASE_PROMPT = """Create one Japanese messaging sticker illustration. The exact same single character must be preserved across the set: a cute 2.5–3-head-tall chibi character, identical hair/fur, eye color, outfit, accessories, palette, bold clean outline, and polished vibrant style. Show a large instantly readable expression and gesture. No words, letters, captions, speech bubbles, scenery, extra characters, watermark, shadow, or cropped body. Center the entire character with generous clear padding."""


def prompt_for(action: str, has_reference: bool, chroma_key: tuple[int, int, int]) -> str:
    reference_instruction = (
        "Use the supplied reference image as the strict identity and design reference; change only expression and pose. "
        if has_reference else
        "Establish one distinctive reusable character design and keep it suitable as the identity master. "
    )
    hex_key = "#" + "".join(f"{channel:02X}" for channel in chroma_key)
    return (
        f"{BASE_PROMPT}\n{reference_instruction}Expression and pose: {action}. "
        f"Place it on a perfectly uniform solid {hex_key} chroma-key background with no gradient, "
        f"texture, lighting variation, or {hex_key} on the character."
    )


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
    with tempfile.NamedTemporaryFile(suffix=".png", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        with Image.open(temporary) as image:
            image.verify()
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
