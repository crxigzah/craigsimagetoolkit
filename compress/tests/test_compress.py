import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import compress  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_copy(tmp_path):
    """Fresh copy of the checked-in fixtures per test, so tests never
    mutate the committed originals and can't leak state between runs."""
    dest = tmp_path / "fixtures"
    shutil.copytree(FIXTURES_DIR, dest)
    return dest


def test_find_png_files_recursive(fixtures_copy):
    files = compress.find_png_files(fixtures_copy, recursive=True)
    names = {f.name for f in files}
    assert "compressible.png" in names
    assert "uppercase.PNG" in names
    assert "nested.png" in names  # lives in fixtures/sub/


def test_find_png_files_non_recursive(fixtures_copy):
    files = compress.find_png_files(fixtures_copy, recursive=False)
    names = {f.name for f in files}
    assert "nested.png" not in names
    assert "compressible.png" in names


def test_find_png_files_single_file(fixtures_copy):
    target = fixtures_copy / "compressible.png"
    files = compress.find_png_files(target, recursive=True)
    assert files == [target]


def test_find_png_files_single_non_png_file(fixtures_copy):
    not_a_png = fixtures_copy / "not_a_png.txt"
    not_a_png.write_text("hello")
    assert compress.find_png_files(not_a_png, recursive=True) == []


def test_check_mode_does_not_modify_files(fixtures_copy):
    target = fixtures_copy / "compressible.png"
    before = target.read_bytes()

    rows, total_before, total_after, needs_work = compress.compress_files(
        [target], level=4, check=True
    )

    assert target.read_bytes() == before  # untouched on disk
    assert total_after < total_before  # but a real saving was found
    assert target in needs_work


def test_compress_writes_smaller_file(fixtures_copy):
    target = fixtures_copy / "compressible.png"
    before_size = target.stat().st_size

    rows, total_before, total_after, needs_work = compress.compress_files(
        [target], level=4, check=False
    )

    after_size = target.stat().st_size
    assert after_size < before_size
    assert after_size == total_after


def test_compress_is_idempotent(fixtures_copy):
    target = fixtures_copy / "compressible.png"
    compress.compress_files([target], level=4, check=False)
    once_compressed = target.read_bytes()

    _, _, _, needs_work = compress.compress_files([target], level=4, check=True)

    assert needs_work == []
    assert target.read_bytes() == once_compressed


@pytest.mark.parametrize(
    "n,expected_prefix",
    [(0, "0B"), (500, "500B"), (2048, "2.0KB"), (5 * 1024 * 1024, "5.0MB")],
)
def test_format_bytes(n, expected_prefix):
    assert compress.format_bytes(n) == expected_prefix


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "compress.py"), *args],
        capture_output=True,
        text=True,
    )


def test_cli_check_mode_exits_nonzero_when_savings_available(fixtures_copy):
    result = _run_cli("--path", str(fixtures_copy), "--check")
    assert result.returncode == 1
    assert "can be compressed further" in result.stdout


def test_cli_compresses_and_then_check_passes(fixtures_copy):
    compress_result = _run_cli("--path", str(fixtures_copy))
    assert compress_result.returncode == 0

    check_result = _run_cli("--path", str(fixtures_copy), "--check")
    assert check_result.returncode == 0


def test_cli_nonexistent_path_errors():
    result = _run_cli("--path", "/definitely/does/not/exist")
    assert result.returncode == 2


def test_cli_writes_github_output(fixtures_copy, tmp_path, monkeypatch):
    output_file = tmp_path / "gh_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "compress.py"),
         "--path", str(fixtures_copy / "compressible.png")],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "GITHUB_OUTPUT": str(output_file)},
    )
    assert result.returncode == 0
    content = output_file.read_text()
    assert "files-processed=1" in content
    assert "bytes-saved=" in content
