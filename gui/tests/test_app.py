"""Drives ToolApp's own methods directly rather than through real mouse
clicks (there is no display to click on in CI) -- this exercises the
GUI's own glue code (file list management and each tab's _do_* method)
against real image files, not just re-testing compress.py/resize.py/
blur.py in isolation, which the other modules' own suites already do.

Needs a display; CI runs this under xvfb-run (see
.github/workflows/test.yml). Locally on Linux with a desktop, it just
works. On Windows/macOS a real display is already present.
"""
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as gui_app  # noqa: E402


@pytest.fixture
def toolapp():
    application = gui_app.ToolApp()
    application.withdraw()
    yield application
    application.destroy()


@pytest.fixture
def test_image(tmp_path):
    def _make(name="test.png", size=(300, 300)):
        path = tmp_path / name
        img = Image.new("RGB", size, color=(20, 20, 30))
        d = ImageDraw.Draw(img)
        d.rectangle([50, 50, size[0] - 50, size[1] - 50], fill=(200, 40, 40))
        img.save(path, optimize=False, compress_level=1)
        return path
    return _make


def test_add_file_dedupes(toolapp, test_image):
    f = test_image()
    toolapp._add_file(f)
    toolapp._add_file(f)
    assert toolapp.files == [f]
    assert toolapp.file_listbox.size() == 1


def test_remove_selected(toolapp, test_image):
    f = test_image()
    toolapp._add_file(f)
    toolapp.file_listbox.selection_set(0)
    toolapp._remove_selected()
    assert toolapp.files == []
    assert toolapp.file_listbox.size() == 0


def test_clear_files(toolapp, test_image):
    toolapp._add_file(test_image("a.png"))
    toolapp._add_file(test_image("b.png"))
    toolapp._clear_files()
    assert toolapp.files == []
    assert toolapp.file_listbox.size() == 0


def test_notebook_has_four_tabs(toolapp):
    assert len(toolapp.notebook.tabs()) == 4


def test_do_compress_shrinks_file(toolapp, test_image):
    f = test_image()
    before = f.stat().st_size
    toolapp._add_file(f)
    toolapp._do_compress(level=4)
    after = f.stat().st_size
    assert after < before


def test_do_resize_writes_correct_dimensions(toolapp, test_image):
    f = test_image(size=(600, 300))
    toolapp._add_file(f)
    toolapp._do_resize(preset="discord-avatar", mode="cover")
    out = f.with_name(f"{f.stem}.discord-avatar.png")
    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (512, 512)


def test_do_resize_contain_mode(toolapp, test_image):
    f = test_image(size=(600, 300))
    toolapp._add_file(f)
    toolapp._do_resize(preset="linkedin-profile", mode="contain")
    out = f.with_name(f"{f.stem}.linkedin-profile.png")
    with Image.open(out) as img:
        assert img.size == (400, 400)


def test_do_blur_changes_file(toolapp, test_image):
    f = test_image()
    before = f.read_bytes()
    toolapp._add_file(f)
    toolapp._do_blur(radius=8.0)
    out = f.with_name(f"{f.stem}.blurred.png")
    assert out.exists()
    assert out.read_bytes() != before


def test_do_remove_bg_produces_transparency(toolapp, test_image):
    f = test_image()
    toolapp._add_file(f)
    toolapp._do_remove_bg(model="u2netp")
    out = f.with_name(f"{f.stem}.nobg.png")
    assert out.exists()
    with Image.open(out) as img:
        assert img.mode == "RGBA"
        lo, hi = img.getchannel("A").getextrema()
        assert lo < 250  # some real transparency was produced


def test_log_queue_receives_messages(toolapp, test_image):
    f = test_image()
    toolapp._add_file(f)
    toolapp._do_compress(level=4)
    assert not toolapp._log_queue.empty()


def test_run_in_background_warns_with_no_files(toolapp, monkeypatch):
    warned = []
    monkeypatch.setattr(gui_app.messagebox, "showinfo", lambda *a, **k: warned.append(a))
    toolapp._run_compress()
    assert warned
