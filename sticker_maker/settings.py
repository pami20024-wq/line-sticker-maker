from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Sticker:
    id: str
    text: str
    action: str


def load_config(path: str | Path = ROOT / "config.yaml") -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    for group in ("openai", "paths", "image", "text"):
        if group not in config:
            raise ValueError(f"設定グループがありません: {group}")
    return config


def load_stickers(path: str | Path = ROOT / "stickers.yaml") -> list[Sticker]:
    with Path(path).open(encoding="utf-8") as stream:
        rows = yaml.safe_load(stream)
    stickers = [Sticker(str(row["id"]), str(row["text"]), str(row["action"])) for row in rows]
    expected = [f"{number:02d}" for number in range(1, 25)]
    if [item.id for item in stickers] != expected:
        raise ValueError("stickers.yaml の id は 01〜24 を順番に指定してください")
    return stickers

