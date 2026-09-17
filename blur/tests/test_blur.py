import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import blur  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "blur.py"


@pytest.fixture
def sharp_image(tmp_path):
    """A hard black/white edge -- blurring it must soften that edge,
    which is the one property that actually distinguishes a real blur
    from a no-op copy."""
    path = tmp_path / "edge.png"
    img = Image.new("RGB", (100, 100), color=(0, 0, 0))
    for x in range(50, 100):
        for y in range(100):
            img.putpixel((x, y), (255, 255, 255))
    img.save(path)
    return path


def test_blur_image_changes_pixels(sharp_image):
    with Image.open(sharp_image) as original:
        blurred = blur.blur_image(original, radius=8)
        diff = ImageChops.difference(original.convert("RGB"), blurred.convert("RGB"))
        assert diff.getbbox() is not None  # something actually changed


def test_blur_softens_a_hard_edge(sharp_image):
    with Image.open(sharp_image) as img:
        blurred = blur.blur_image(img, radius=10)
    # Right at the edge (x=50), a real blur should produce a mid gray,
    # not the original hard black/white transition.
    pixel = blurred.getpixel((50, 50))
    assert 20 < pixel[0] < 235


def test_blur_preserves_dimensions(sharp_image):
    with Image.open(sharp_image) as img:
        blurred = blur.blur_image(img, radius=5)
    assert blurred.size == img.size


def test_output_path_for_default_suffix(tmp_path):
    src = tmp_path / "photo.jpg"
    result = blur.output_path_for(src, None, in_place=False, suffix=".blurred")
    assert result.name == "photo.blurred.jpg"


def test_output_path_for_in_place(tmp_path):
    src = tmp_path / "photo.jpg"
    result = blur.output_path_for(src, None, in_place=True, suffix=".blurred")
    assert result == src


def _run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_cli_blurs_and_writes_new_file(sharp_image):
    result = _run_cli("--path", str(sharp_image), "--radius", "6")
    assert result.returncode == 0
    out_file = sharp_image.with_name("edge.blurred.png")
    assert out_file.exists()
    with Image.open(sharp_image) as original, Image.open(out_file) as blurred:
        assert ImageChops.difference(original, blurred).getbbox() is not None


def test_cli_in_place_overwrites_source(sharp_image):
    before = sharp_image.read_bytes()
    result = _run_cli("--path", str(sharp_image), "--radius", "6", "--in-place")
    assert result.returncode == 0
    after = sharp_image.read_bytes()
    assert before != after


def test_cli_rejects_zero_radius(sharp_image):
    result = _run_cli("--path", str(sharp_image), "--radius", "0")
    assert result.returncode == 2


def test_cli_nonexistent_path_errors():
    result = _run_cli("--path", "/definitely/does/not/exist")
    assert result.returncode == 2
