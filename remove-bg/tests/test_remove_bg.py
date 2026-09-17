import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parent.parent / "remove_bg.py"


@pytest.fixture
def photo_like_image(tmp_path):
    """A simple subject on a plain background -- enough for the
    lightweight u2netp model to produce a real, non-trivial alpha mask
    quickly, which is all these tests need to verify."""
    path = tmp_path / "subject.png"
    img = Image.new("RGB", (200, 200), color=(240, 240, 240))
    for x in range(60, 140):
        for y in range(60, 140):
            img.putpixel((x, y), (200, 30, 30))
    img.save(path)
    return path


def _run_cli(*args, timeout=120):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=timeout)


def test_cli_produces_transparent_png(photo_like_image):
    result = _run_cli("--path", str(photo_like_image))
    assert result.returncode == 0, result.stderr

    out_file = photo_like_image.with_name("subject.nobg.png")
    assert out_file.exists()

    with Image.open(out_file) as img:
        assert img.mode == "RGBA"
        alpha = img.getchannel("A")
        lo, hi = alpha.getextrema()
        # A real segmentation produces both fully transparent and
        # fully (or near) opaque pixels -- a no-op pass-through would
        # leave alpha uniformly 255.
        assert lo < 50
        assert hi > 200


def test_cli_original_file_untouched(photo_like_image):
    before = photo_like_image.read_bytes()
    _run_cli("--path", str(photo_like_image))
    assert photo_like_image.read_bytes() == before


def test_cli_custom_suffix(photo_like_image):
    result = _run_cli("--path", str(photo_like_image), "--suffix", ".cutout")
    assert result.returncode == 0
    assert photo_like_image.with_name("subject.cutout.png").exists()


def test_cli_output_dir(photo_like_image, tmp_path):
    out_dir = tmp_path / "out"
    result = _run_cli("--path", str(photo_like_image), "--output-dir", str(out_dir))
    assert result.returncode == 0
    assert (out_dir / "subject.nobg.png").exists()


def test_cli_nonexistent_path_errors():
    result = _run_cli("--path", "/definitely/does/not/exist")
    assert result.returncode == 2


def test_cli_invalid_model_errors(photo_like_image):
    result = _run_cli("--path", str(photo_like_image), "--model", "not-a-real-model")
    assert result.returncode == 2
