from pathlib import Path

from PIL import Image, ImageDraw

from sticker_maker.processing import (choose_chroma_key, create_zip, is_valid_resume_image,
                                      remove_chroma, trim_alpha)
from validation import validate_file


def test_remove_chroma_and_trim():
    image = Image.new("RGB", (20, 20), (0, 255, 0))
    ImageDraw.Draw(image).rectangle((5, 5, 14, 14), fill=(100, 50, 150))
    result = remove_chroma(image, (0, 255, 0))
    assert result.getpixel((0, 0))[3] == 0
    assert trim_alpha(result).size == (10, 10)


def test_chroma_clears_rgb_under_transparent_pixels():
    image = Image.new("RGB", (30, 30), (8, 180, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 24, 24), fill=(100, 50, 150))
    draw.rectangle((12, 12, 17, 17), fill=(0, 255, 0))
    result = remove_chroma(image, (0, 255, 0))
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((0, 0))[:3] == (0, 0, 0)
    assert result.getpixel((8, 8))[3] == 255


def test_resume_rejects_corrupt_and_edge_touching_files(tmp_path: Path):
    path = tmp_path / "01.png"
    path.write_bytes(b"not a png")
    assert not is_valid_resume_image(path, (20, 20), 2)
    Image.new("RGBA", (20, 20), (10, 10, 10, 255)).save(path)
    assert not is_valid_resume_image(path, (20, 20), 2)
    valid = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    ImageDraw.Draw(valid).rectangle((2, 2, 17, 17), fill=(10, 10, 10, 255))
    valid.save(path)
    assert is_valid_resume_image(path, (20, 20), 2)


def test_auto_chroma_avoids_reference_color(tmp_path: Path):
    reference = tmp_path / "reference.png"
    Image.new("RGBA", (10, 10), (20, 220, 30, 255)).save(reference)
    assert choose_chroma_key(reference, "auto", [[0, 255, 0], [255, 0, 255]]) == (255, 0, 255)


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
