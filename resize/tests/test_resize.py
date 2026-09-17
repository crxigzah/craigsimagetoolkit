import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import resize  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "resize.py"


@pytest.fixture
def rgb_image(tmp_path):
    path = tmp_path / "photo.png"
    img = Image.new("RGB", (600, 300), color=(10, 20, 30))
    img.save(path)
    return path


@pytest.fixture
def transparent_image(tmp_path):
    path = tmp_path / "logo.png"
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    for x in range(150, 250):
        for y in range(150, 250):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.save(path)
    return path


def test_load_presets_has_expected_entries():
    presets = resize.load_presets()
    for name in ["instagram-post", "instagram-profile", "linkedin-post",
                 "linkedin-profile", "discord-avatar", "discord-server-icon"]:
        assert name in presets
        assert presets[name]["width"] > 0
        assert presets[name]["height"] > 0


def test_resize_cover_produces_exact_dimensions(rgb_image):
    with Image.open(rgb_image) as img:
        result = resize.resize_cover(img, 100, 100)
    assert result.size == (100, 100)


def test_resize_cover_on_square_target_from_wide_source_crops_sides(rgb_image):
    # 600x300 source into a 100x100 (square) box: cover must scale by
    # height (the limiting dimension) then crop the left/right overflow,
    # never squash the image out of its original aspect ratio.
    with Image.open(rgb_image) as img:
        result = resize.resize_cover(img, 100, 100)
    assert result.size == (100, 100)
    # Center pixel should match the source's center pixel color (10,20,30)
    assert result.getpixel((50, 50))[:3] == (10, 20, 30)


def test_resize_contain_produces_exact_dimensions_with_padding(rgb_image):
    with Image.open(rgb_image) as img:
        result = resize.resize_contain(img, 100, 100, "white")
    assert result.size == (100, 100)
    # Top-left corner should be padding (white), since a 600x300 image
    # fit into a 100x100 box leaves bars above/below, not edge-to-edge.
    corner = result.getpixel((2, 2))
    assert corner[:3] == (255, 255, 255)


def test_resize_contain_preserves_transparency(transparent_image):
    with Image.open(transparent_image) as img:
        result = resize.resize_contain(img, 200, 100, "white")
    assert result.mode == "RGBA"
    # Somewhere in the result the red square should still be opaque
    alpha_values = [result.getpixel((x, 50))[3] for x in range(200)]
    assert max(alpha_values) == 255


def test_output_path_for_default_adds_label_suffix(tmp_path):
    src = tmp_path / "photo.png"
    result = resize.output_path_for(src, "instagram-post", None, in_place=False)
    assert result.name == "photo.instagram-post.png"
    assert result.parent == tmp_path


def test_output_path_for_in_place_returns_source(tmp_path):
    src = tmp_path / "photo.png"
    result = resize.output_path_for(src, "instagram-post", None, in_place=True)
    assert result == src


def test_output_path_for_output_dir(tmp_path):
    src = tmp_path / "in" / "photo.png"
    out_dir = tmp_path / "out"
    result = resize.output_path_for(src, "square", out_dir, in_place=False)
    assert result == out_dir / "photo.square.png"


def test_parse_size_valid():
    assert resize.parse_size("800x600") == (800, 600)
    assert resize.parse_size("1080X1080") == (1080, 1080)


def test_parse_size_invalid():
    with pytest.raises(ValueError):
        resize.parse_size("not-a-size")


def _run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_cli_list_presets():
    result = _run_cli("--list-presets")
    assert result.returncode == 0
    assert "instagram-post" in result.stdout
    assert "discord-avatar" in result.stdout


def test_cli_resize_with_preset_writes_new_file(rgb_image):
    result = _run_cli("--path", str(rgb_image), "--preset", "discord-avatar")
    assert result.returncode == 0
    out_file = rgb_image.with_name("photo.discord-avatar.png")
    assert out_file.exists()
    with Image.open(out_file) as img:
        assert img.size == (512, 512)
    # Original untouched
    with Image.open(rgb_image) as img:
        assert img.size == (600, 300)


def test_cli_resize_with_custom_size(rgb_image):
    result = _run_cli("--path", str(rgb_image), "--size", "150x150")
    assert result.returncode == 0
    out_file = rgb_image.with_name("photo.150x150.png")
    with Image.open(out_file) as img:
        assert img.size == (150, 150)


def test_cli_requires_preset_or_size(rgb_image):
    result = _run_cli("--path", str(rgb_image))
    assert result.returncode != 0


def test_cli_nonexistent_path_errors():
    result = _run_cli("--path", "/definitely/does/not/exist", "--preset", "discord-avatar")
    assert result.returncode == 2


def test_cli_output_dir(rgb_image, tmp_path):
    out_dir = tmp_path / "resized"
    result = _run_cli("--path", str(rgb_image), "--preset", "linkedin-profile", "--output-dir", str(out_dir))
    assert result.returncode == 0
    assert (out_dir / "photo.linkedin-profile.png").exists()
