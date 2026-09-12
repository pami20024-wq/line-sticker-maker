from pathlib import Path

from PIL import Image, ImageDraw

from sticker_maker.processing import create_zip, remove_chroma, trim_alpha
from validation import validate_file


def test_remove_chroma_and_trim():
    image = Image.new("RGB", (20, 20), (0, 255, 0))
    ImageDraw.Draw(image).rectangle((5, 5, 14, 14), fill=(100, 50, 150))
    result = remove_chroma(image, (0, 255, 0), 40)
    assert result.getpixel((0, 0))[3] == 0
    assert trim_alpha(result).size == (10, 10)


def test_validation_reports_missing(tmp_path: Path):
    errors = validate_file(tmp_path / "01.png", (370, 320), (370, 320), 1_048_576)
    assert errors == ["01.png: ファイルがありません"]


def test_create_zip_contains_only_submission_files(tmp_path: Path):
    for number in range(1, 25):
        Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(tmp_path / f"{number:02d}.png")
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(tmp_path / "main.png")
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(tmp_path / "tab.png")
    archive = create_zip(tmp_path, 62_914_560)
    import zipfile
    with zipfile.ZipFile(archive) as zf:
        assert len(zf.namelist()) == 26
        assert "preview.png" not in zf.namelist()

