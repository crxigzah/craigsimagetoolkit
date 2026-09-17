# craigsimagetoolkit

Four small, independent GitHub Actions for common image tasks. Each lives in its own directory with its own `action.yml`, so you can use any one of them on its own without pulling in the others.

| Action | What it does |
|---|---|
| [`compress`](compress) | Losslessly compress PNGs with oxipng, in place or as a PR check |
| [`resize`](resize) | Resize images to common social platform sizes or a custom width/height |
| [`blur`](blur) | Apply a Gaussian blur to whole images |
| [`remove-bg`](remove-bg) | Remove the background from photos, leaving a transparent PNG |

## compress

```yaml
- uses: crxigzah/craigsimagetoolkit/compress@v1
  with:
    path: assets/
```

Set `check: true` to fail the step instead of modifying files, useful as a PR gate that reminds contributors to compress their images rather than doing it for them:

```yaml
- uses: crxigzah/craigsimagetoolkit/compress@v1
  with:
    path: assets/
    check: true
```

Inputs: `path` (default `.`), `level` (0 to 6, default `4`), `recursive` (default `true`), `check` (default `false`).
Outputs: `files-processed`, `bytes-saved`.

## resize

```yaml
- uses: crxigzah/craigsimagetoolkit/resize@v1
  with:
    path: uploads/avatar.png
    preset: discord-avatar
```

Built in presets (see [`resize/presets.json`](resize/presets.json), add your own there): `instagram-post`, `instagram-profile`, `linkedin-post`, `linkedin-profile`, `discord-avatar`, `discord-server-icon`, `twitter-post`, `twitter-profile`, `facebook-profile`, `youtube-thumbnail`.

Or skip presets entirely with a custom size:

```yaml
- uses: crxigzah/craigsimagetoolkit/resize@v1
  with:
    path: uploads/banner.png
    size: 1600x400
    mode: contain
    background: '#0d0d18'
```

`mode: cover` (default) fills the target box and crops whatever overflows, the same behavior every platform's own upload cropper uses. `mode: contain` fits the whole image inside the box and pads with `background` instead, so nothing is ever cropped out.

Inputs: `path` (default `.`), `preset`, `size`, `mode` (`cover` or `contain`, default `cover`), `background` (default `white`), `output-dir`, `in-place` (default `false`), `recursive` (default `true`).
Outputs: `files-processed`.

Platform sizes in `presets.json` are commonly recommended values at time of writing. Platforms change these occasionally, so double check current guidelines if exact pixel accuracy matters for your use case.

## blur

```yaml
- uses: crxigzah/craigsimagetoolkit/blur@v1
  with:
    path: previews/
    radius: 12
```

Blurs the entire image uniformly, for a placeholder/preview effect, a privacy blur, or a soft background behind text. It does not detect faces or blur only part of an image.

Inputs: `path` (default `.`), `radius` (default `8`), `suffix` (default `.blurred`), `output-dir`, `in-place` (default `false`), `recursive` (default `true`).
Outputs: `files-processed`.

## remove-bg

```yaml
- uses: crxigzah/craigsimagetoolkit/remove-bg@v1
  with:
    path: uploads/
```

Uses [rembg](https://github.com/danielgatis/rembg), a real background-segmentation model, not a color/chroma-key trick, so it works on ordinary photo backgrounds. Defaults to the `u2netp` model (about 5MB, fast) so it stays quick in CI; pass `model: u2net` or `model: isnet-general-use` for noticeably better edge quality at the cost of a slower, larger one time download.

Output is always a PNG regardless of the input format, since only PNG can store the transparency this adds.

Inputs: `path` (default `.`), `model` (default `u2netp`), `output-dir`, `suffix` (default `.nobg`), `recursive` (default `true`).
Outputs: `files-processed`.

Model downloads are cached automatically by rembg inside `~/.rembg`. Cache that directory with `actions/cache` between runs so repeat workflow runs do not re-download the model every time:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.rembg
    key: rembg-models
- uses: crxigzah/craigsimagetoolkit/remove-bg@v1
```

## Auto-committing changes

None of these actions commit anything themselves, on purpose, they only touch files on the runner's checkout. Pair one with [`stefanzweifel/git-auto-commit-action`](https://github.com/stefanzweifel/git-auto-commit-action) to persist the result back to the repository:

```yaml
name: Optimize images
on:
  pull_request:
    paths:
      - '**.png'
      - '**.jpg'

jobs:
  optimize:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: crxigzah/craigsimagetoolkit/compress@v1
        with:
          path: assets/
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'Compress images'
```

## Development

Each module is independent: its own `requirements.txt`, its own `tests/`. From inside any module directory:

```bash
pip install -r requirements.txt
pip install pytest
python -m pytest tests/ -v
```

CI (`.github/workflows/test.yml`) runs all four test suites on every push and pull request.
