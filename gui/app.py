#!/usr/bin/env python3
"""Desktop GUI for the four craigsimagetoolkit actions (compress, resize,
blur, remove background), built with Tkinter so it packages into a
single standalone .exe with PyInstaller (see app.spec) -- no browser,
no local server, just a window.

Reuses the exact same compress.py/resize.py/blur.py modules the GitHub
Actions run, imported directly from their sibling directories (see the
sys.path setup below in dev mode; PyInstaller's app.spec bundles them
in directly via pathex for the frozen .exe), so there is exactly one
implementation of each operation to keep correct and tested, not a
second copy that can drift from the Action.
"""
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image

if not getattr(sys, "frozen", False):
    _ROOT = Path(__file__).resolve().parent.parent
    for _dir in ("compress", "resize", "blur"):
        sys.path.insert(0, str(_ROOT / _dir))

import blur as blur_mod
import compress as compress_mod
import resize as resize_mod
from rembg import new_session
from rembg import remove as rembg_remove

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
REMBG_MODELS = ["u2netp", "u2net", "isnet-general-use"]


class ToolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("craigsimagetoolkit")
        self.geometry("760x620")
        self.minsize(640, 480)

        self.files: list[Path] = []
        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self._rembg_session = None
        self._rembg_session_model = None

        self._build_file_panel()
        self._build_notebook()
        self._build_log_panel()

        self.after(100, self._drain_log_queue)

    # -- Shared file list --------------------------------------------
    def _build_file_panel(self):
        frame = ttk.LabelFrame(self, text="Files")
        frame.pack(fill="x", padx=10, pady=(10, 5))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="x", padx=8, pady=8)

        self.file_listbox = tk.Listbox(list_frame, height=6, selectmode="extended")
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="Add Files...", command=self._add_files).pack(side="left")
        ttk.Button(btn_frame, text="Add Folder...", command=self._add_folder).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_selected).pack(side="left")
        ttk.Button(btn_frame, text="Clear", command=self._clear_files).pack(side="left", padx=6)

    def _add_files(self):
        pattern = " ".join(f"*{ext}" for ext in IMAGE_EXTENSIONS)
        paths = filedialog.askopenfilenames(title="Select images", filetypes=[("Images", pattern)])
        for p in paths:
            self._add_file(Path(p))

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select a folder of images")
        if not folder:
            return
        for p in sorted(Path(folder).iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                self._add_file(p)

    def _add_file(self, path: Path):
        if path not in self.files:
            self.files.append(path)
            self.file_listbox.insert("end", str(path))

    def _remove_selected(self):
        for idx in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(idx)
            del self.files[idx]

    def _clear_files(self):
        self.file_listbox.delete(0, "end")
        self.files.clear()

    # -- Tabs ----------------------------------------------------------
    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="x", padx=10, pady=5)
        self._build_compress_tab()
        self._build_resize_tab()
        self._build_blur_tab()
        self._build_remove_bg_tab()

    def _build_compress_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Compress")
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text="Optimization level (0 fastest, 6 smallest):").grid(row=0, column=0, sticky="w")
        self.compress_level = tk.IntVar(value=4)
        scale = ttk.Scale(tab, from_=0, to=6, orient="horizontal", variable=self.compress_level,
                           command=lambda v: self.compress_level.set(round(float(v))))
        scale.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(tab, textvariable=self.compress_level).grid(row=0, column=2)

        ttk.Button(tab, text="Compress Loaded Files", command=self._run_compress).grid(
            row=1, column=0, columnspan=3, pady=(12, 0), sticky="w")

    def _build_resize_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Resize")
        tab.columnconfigure(1, weight=1)

        self.resize_presets = resize_mod.load_presets()
        preset_names = sorted(self.resize_presets)

        ttk.Label(tab, text="Preset:").grid(row=0, column=0, sticky="w")
        self.resize_preset = tk.StringVar(value=preset_names[0])
        preset_menu = ttk.Combobox(tab, textvariable=self.resize_preset, values=preset_names, state="readonly")
        preset_menu.grid(row=0, column=1, sticky="ew", padx=8)

        self.resize_preset_desc = tk.StringVar()
        ttk.Label(tab, textvariable=self.resize_preset_desc, foreground="#666").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 8))

        def update_desc(*_args):
            spec = self.resize_presets[self.resize_preset.get()]
            self.resize_preset_desc.set(f"{spec['width']}x{spec['height']}, {spec.get('description', '')}")

        preset_menu.bind("<<ComboboxSelected>>", update_desc)
        update_desc()

        ttk.Label(tab, text="Fit mode:").grid(row=2, column=0, sticky="w")
        self.resize_mode = tk.StringVar(value="cover")
        ttk.Radiobutton(tab, text="Cover (fill and crop)", variable=self.resize_mode, value="cover").grid(
            row=2, column=1, sticky="w")
        ttk.Radiobutton(tab, text="Contain (fit and pad)", variable=self.resize_mode, value="contain").grid(
            row=3, column=1, sticky="w")

        ttk.Button(tab, text="Resize Loaded Files", command=self._run_resize).grid(
            row=4, column=0, columnspan=2, pady=(12, 0), sticky="w")

    def _build_blur_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Blur")
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text="Blur radius:").grid(row=0, column=0, sticky="w")
        self.blur_radius = tk.DoubleVar(value=8.0)
        ttk.Scale(tab, from_=1, to=40, orient="horizontal", variable=self.blur_radius).grid(
            row=0, column=1, sticky="ew", padx=8)
        ttk.Label(tab, textvariable=self.blur_radius).grid(row=0, column=2)

        ttk.Button(tab, text="Blur Loaded Files", command=self._run_blur).grid(
            row=1, column=0, columnspan=3, pady=(12, 0), sticky="w")

    def _build_remove_bg_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Remove Background")
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text="Model:").grid(row=0, column=0, sticky="w")
        self.rembg_model = tk.StringVar(value=REMBG_MODELS[0])
        ttk.Combobox(tab, textvariable=self.rembg_model, values=REMBG_MODELS, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=8)
        ttk.Label(
            tab,
            text="u2netp is small and fast. u2net and isnet-general-use are\n"
                 "slower but give better edges, and download a larger model\n"
                 "the first time they are used.",
            foreground="#666", justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))

        ttk.Button(tab, text="Remove Background from Loaded Files", command=self._run_remove_bg).grid(
            row=2, column=0, columnspan=2, pady=(12, 0), sticky="w")

    # -- Log panel -------------------------------------------------------
    def _build_log_panel(self):
        frame = ttk.LabelFrame(self, text="Log")
        frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.log_text = tk.Text(frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _log(self, message: str):
        self._log_queue.put(message)

    def _drain_log_queue(self):
        try:
            while True:
                message = self._log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    # -- Running operations, each on a background thread so the window
    # never freezes mid-batch (remove background especially can take a
    # real amount of time per image) -----------------------------------
    def _run_in_background(self, fn):
        if not self.files:
            messagebox.showinfo("No files", "Add some image files first.")
            return
        threading.Thread(target=fn, daemon=True).start()

    def _run_compress(self):
        level = self.compress_level.get()
        self._run_in_background(lambda: self._do_compress(level))

    def _do_compress(self, level: int):
        self._log(f"Compressing {len(self.files)} file(s) at level {level}...")
        rows, total_before, total_after, _ = compress_mod.compress_files(list(self.files), level=level, check=False)
        for path, before, after, pct in rows:
            self._log(f"  {path.name}: {compress_mod.format_bytes(before)} → "
                       f"{compress_mod.format_bytes(after)} ({pct:.1f}% saved)")
        self._log(f"Done. Saved {compress_mod.format_bytes(total_before - total_after)} total.\n")

    def _run_resize(self):
        preset = self.resize_preset.get()
        mode = self.resize_mode.get()
        self._run_in_background(lambda: self._do_resize(preset, mode))

    def _do_resize(self, preset: str, mode: str):
        spec = self.resize_presets[preset]
        width, height = spec["width"], spec["height"]
        self._log(f"Resizing {len(self.files)} file(s) to {width}x{height} ({preset}, {mode})...")
        for src in self.files:
            try:
                with Image.open(src) as img:
                    result = resize_mod.resize_image(img, width, height, mode, "white")
                dest = resize_mod.output_path_for(src, preset, None, in_place=False)
                result.save(dest)
                self._log(f"  {src.name} → {dest.name}")
            except Exception as e:
                self._log(f"  Could not resize {src.name}: {e}")
        self._log("Done.\n")

    def _run_blur(self):
        radius = self.blur_radius.get()
        self._run_in_background(lambda: self._do_blur(radius))

    def _do_blur(self, radius: float):
        self._log(f"Blurring {len(self.files)} file(s) at radius {radius:.1f}...")
        for src in self.files:
            try:
                with Image.open(src) as img:
                    result = blur_mod.blur_image(img, radius)
                dest = blur_mod.output_path_for(src, None, in_place=False, suffix=".blurred")
                if dest.suffix.lower() in (".jpg", ".jpeg") and result.mode == "RGBA":
                    result = result.convert("RGB")
                result.save(dest)
                self._log(f"  {src.name} → {dest.name}")
            except Exception as e:
                self._log(f"  Could not blur {src.name}: {e}")
        self._log("Done.\n")

    def _run_remove_bg(self):
        model = self.rembg_model.get()
        self._run_in_background(lambda: self._do_remove_bg(model))

    def _do_remove_bg(self, model: str):
        self._log(f"Removing backgrounds from {len(self.files)} file(s) using {model} "
                   f"(first use downloads the model)...")
        if self._rembg_session is None or self._rembg_session_model != model:
            try:
                self._rembg_session = new_session(model)
                self._rembg_session_model = model
            except Exception as e:
                self._log(f"Could not load model {model!r}: {e}\n")
                return
        for src in self.files:
            try:
                output_bytes = rembg_remove(src.read_bytes(), session=self._rembg_session)
                dest = src.with_name(f"{src.stem}.nobg.png")
                dest.write_bytes(output_bytes)
                self._log(f"  {src.name} → {dest.name}")
            except Exception as e:
                self._log(f"  Could not process {src.name}: {e}")
        self._log("Done.\n")


def main():
    app = ToolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
