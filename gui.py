import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from tkinter import font as tkfont

import cv2
import numpy as np
from PIL import Image, ImageTk, ImageGrab

import sv_ttk
from tkinterdnd2 import TkinterDnD, DND_FILES

from ocr_engine import ocr_bgr


def _first_path_from_drop(data: str):
    if not data:
        return None

    data = data.strip()

    if data.startswith("{") and data.endswith("}"):
        return data[1:-1]

    parts = []
    current = ""
    in_braces = False

    for ch in data:
        if ch == "{":
            in_braces = True
            current = ""
        elif ch == "}":
            in_braces = False
            parts.append(current)
            current = ""
        elif ch == " " and not in_braces:
            if current:
                parts.append(current)
                current = ""
        else:
            current += ch

    if current:
        parts.append(current)

    return parts[0] if parts else None


class OCRApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        self.title("OCR - Paste or Drag Image (area selection)")
        self.geometry("1200x720")
        self.minsize(980, 620)

        self._apply_style()

        # ===== Languages =====
        self.LANG_OPTIONS = [
            ("Portuguese + English (por+eng)", "por+eng"),
            ("Portuguese (por)", "por"),
            ("English (eng)", "eng"),
            ("Spanish (spa)", "spa"),
            ("French (fra)", "fra"),
            ("Italian (ita)", "ita"),
            ("German (deu)", "deu"),
        ]
        self._lang_map = {label: code for (label, code) in self.LANG_OPTIONS}
        self._lang_labels = [label for (label, _) in self.LANG_OPTIONS]
        self.lang_choice = tk.StringVar(value="Portuguese + English (por+eng)")

        self.image_label = tk.StringVar(value="No image loaded")
        self._image_label_full = "No image loaded"

        self.cv_img_bgr = None
        self.orig_w = 0
        self.orig_h = 0

        self.tk_img = None
        self.disp_w = 0
        self.disp_h = 0
        self.offset_x = 0
        self.offset_y = 0

        self.roi = None

        self.sel_rect_id = None
        self.drag_start = None

        self._build_ui()
        self._bind_shortcuts()
        self._setup_dnd()
        self._draw_empty_hint()

    def _apply_style(self):
        self.option_add("*Font", "SegoeUI 10")

        style = ttk.Style(self)
        style.theme_use("clam")

        sv_ttk.set_theme("light")  # change to "dark" if you want

        style.configure("Toolbar.TFrame", padding=10)
        style.configure("Card.TFrame", padding=10)
        style.configure("Status.TLabel", padding=(10, 6))
        style.configure("TButton", padding=(10, 6))
        style.configure("TCombobox", padding=(6, 4))

    def _build_ui(self):
        # ===== Toolbar =====
        toolbar = ttk.Frame(self, style="Toolbar.TFrame")
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="Choose image…", command=self.pick_image).pack(side="left", padx=(8, 0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Label(toolbar, text="Language:").pack(side="left")
        self.lang_combo = ttk.Combobox(
            toolbar,
            textvariable=self.lang_choice,
            values=self._lang_labels,
            state="readonly",
            width=30,
        )
        self.lang_combo.pack(side="left", padx=(6, 0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=12)

        self.btn_run = ttk.Button(
            toolbar,
            text="Run OCR",
            command=self.run_ocr,
            state="disabled",
            style="Accent.TButton",
        )
        self.btn_run.pack(side="left")

        ttk.Button(toolbar, text="Clear selection", command=self.clear_selection).pack(side="left", padx=(10, 0))

        right_box = ttk.Frame(toolbar)
        right_box.pack(side="right", padx=(12, 8), fill="x", expand=True)

        self.image_label_widget = ttk.Label(right_box, textvariable=self.image_label, anchor="e")
        self.image_label_widget.pack(fill="x", expand=True)

        right_box.bind("<Configure>", self._refresh_image_label)

        # ===== Body =====
        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(body, style="Card.TFrame")
        body.add(left, weight=3)

        self.canvas = tk.Canvas(
            left,
            bg="#111111",
            highlightthickness=1,
            highlightbackground="#444",
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Configure>", lambda e: self.redraw_image())

        bottom_left = ttk.Frame(left)
        bottom_left.pack(fill="x", pady=(10, 0))

        self.btn_deselect = ttk.Button(
            bottom_left,
            text="Deselect image",
            command=self.clear_image,
            state="disabled",
        )
        self.btn_deselect.pack(side="left")

        right = ttk.Frame(body, style="Card.TFrame")
        body.add(right, weight=2)

        top_right = ttk.Frame(right)
        top_right.pack(fill="x")

        ttk.Label(top_right, text="Extracted text:").pack(side="left")
        self.selection_info = tk.StringVar(value="Selection: full image")
        ttk.Label(top_right, textvariable=self.selection_info).pack(side="right")

        self.text = scrolledtext.ScrolledText(right, wrap="word", font=("Segoe UI", 10))
        self.text.pack(fill="both", expand=True, pady=(10, 0))

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=10)

        ttk.Button(btns, text="Copy text", command=self.copy_text).pack(side="left",  padx=(10, 0))
        ttk.Button(btns, text="Clear text", command=self.clear_text).pack(side="left", padx=(10, 0))

        self.status = tk.StringVar(value="Ready. Paste (Ctrl+V) or drag an image.")
        ttk.Label(self, textvariable=self.status, style="Status.TLabel", relief="sunken", anchor="w").pack(fill="x")

    def _bind_shortcuts(self):
        self.bind_all("<Control-v>", lambda e: self.paste_image())
        self.bind_all("<Control-V>", lambda e: self.paste_image())
        self.bind_all("<Command-v>", lambda e: self.paste_image())
        self.bind_all("<Command-V>", lambda e: self.paste_image())

    def _setup_dnd(self):
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.on_drop)

        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind("<<Drop>>", self.on_drop)

    def _ellipsize_keep_end(self, text: str, max_px: int) -> str:
        """Shows '…' + end of the text, ensuring it fits within max_px."""
        if max_px <= 0:
            return ""

        font_spec = self.image_label_widget.cget("font")
        try:
            f = tkfont.nametofont(font_spec)
        except tk.TclError:
            f = tkfont.Font(font=font_spec)

        if f.measure(text) <= max_px:
            return text

        ell = "…"
        if f.measure(ell) >= max_px:
            return ell

        lo, hi = 0, len(text)
        best = ell
        while lo <= hi:
            mid = (lo + hi) // 2
            cand = ell + text[-mid:] if mid > 0 else ell
            if f.measure(cand) <= max_px:
                best = cand
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def _refresh_image_label(self, event=None):
        max_px = self.image_label_widget.winfo_width()
        if max_px <= 1:
            self.after(50, self._refresh_image_label)
            return
        self.image_label.set(self._ellipsize_keep_end(self._image_label_full, max_px))

    # =========================
    # Helpers
    # =========================
    def _get_lang_code(self) -> str:
        label = (self.lang_choice.get() or "").strip()
        return self._lang_map.get(label, "por+eng")

    def _draw_empty_hint(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 10 or h <= 10:
            return

        msg = "Drag an image here\nor press Ctrl+V\n\n(Then drag to select the area)"
        self.canvas.create_text(
            w // 2,
            h // 2,
            text=msg,
            fill="#cfcfcf",
            font=("Segoe UI", 12),
            justify="center",
        )

    def clear_image(self):
        """Unloads the current image and returns the UI to the empty state."""
        self.cv_img_bgr = None
        self.orig_w = 0
        self.orig_h = 0
        self.tk_img = None

        self.clear_selection(silent=True)

        self._image_label_full = "No image loaded"
        self._refresh_image_label()

        self.btn_run.config(state="disabled")
        self.btn_deselect.config(state="disabled")

        self.text.delete("1.0", "end")
        self.status.set("Ready. Paste (Ctrl+V) or drag an image.")

        self._draw_empty_hint()

    # =========================
    # Image input (Drop / File / Clipboard)
    # =========================
    def on_drop(self, event):
        path = _first_path_from_drop(getattr(event, "data", ""))
        if path:
            self._load_image_from_path(path)

    def pick_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._load_image_from_path(path)

    def paste_image(self):
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Error", f"Could not access clipboard: {e}")
            return

        if data is None:
            messagebox.showinfo("Paste image", "The clipboard does not contain an image (or an image file).")
            return

        if isinstance(data, Image.Image):
            pil_img = data.convert("RGB")
            np_img = np.array(pil_img)  # RGB
            cv_img_bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
            self._set_cv_image(cv_img_bgr, "<image from clipboard>")
            return

        if isinstance(data, list) and len(data) > 0:
            self._load_image_from_path(data[0])
            return

        messagebox.showinfo("Paste image", "The clipboard does not contain a usable image.")

    def _load_image_from_path(self, path: str):
        self.status.set("Loading image...")
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", "Could not open this file as an image.")
            self.status.set("Error.")
            return
        self._set_cv_image(img, os.path.basename(path))

    def _set_cv_image(self, cv_img_bgr, label: str):
        self.cv_img_bgr = cv_img_bgr
        self.orig_h, self.orig_w = cv_img_bgr.shape[:2]

        self._image_label_full = label
        self._refresh_image_label()

        self.clear_selection(silent=True)
        self.btn_run.config(state="normal")
        self.btn_deselect.config(state="normal")
        self.status.set("Image loaded. Drag to select an area (or use the full image).")
        self.redraw_image()

    # =========================
    # Render / coordinates
    # =========================
    def redraw_image(self):
        if self.cv_img_bgr is None:
            self._draw_empty_hint()
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 20 or ch <= 20:
            return

        rgb = cv2.cvtColor(self.cv_img_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)

        scale = min(cw / self.orig_w, ch / self.orig_h)
        self.disp_w = max(1, int(self.orig_w * scale))
        self.disp_h = max(1, int(self.orig_h * scale))

        pil_resized = pil.resize((self.disp_w, self.disp_h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(pil_resized)

        self.canvas.delete("all")

        self.offset_x = (cw - self.disp_w) // 2
        self.offset_y = (ch - self.disp_h) // 2

        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_img)

        if self.roi is not None:
            x1, y1, x2, y2 = self.roi
            dx1, dy1 = self._orig_to_disp(x1, y1)
            dx2, dy2 = self._orig_to_disp(x2, y2)
            self.sel_rect_id = self.canvas.create_rectangle(
                dx1,
                dy1,
                dx2,
                dy2,
                outline="#ffcc00",
                width=2,
                fill="#ffcc00",
                stipple="gray25",
            )

    def _point_inside_image(self, cx, cy):
        return (
            self.offset_x <= cx <= self.offset_x + self.disp_w
            and self.offset_y <= cy <= self.offset_y + self.disp_h
        )

    def _disp_to_orig(self, cx, cy):
        x = cx - self.offset_x
        y = cy - self.offset_y

        x = max(0, min(self.disp_w, x))
        y = max(0, min(self.disp_h, y))

        ox = int(x * (self.orig_w / self.disp_w))
        oy = int(y * (self.orig_h / self.disp_h))
        return ox, oy

    def _orig_to_disp(self, ox, oy):
        x = (ox * (self.disp_w / self.orig_w)) + self.offset_x
        y = (oy * (self.disp_h / self.orig_h)) + self.offset_y
        return x, y

    # =========================
    # Area selection (ROI)
    # =========================
    def on_mouse_down(self, event):
        if self.cv_img_bgr is None:
            return
        if not self._point_inside_image(event.x, event.y):
            return

        self.drag_start = (event.x, event.y)

        if self.sel_rect_id is not None:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None

    def on_mouse_drag(self, event):
        if self.drag_start is None or self.cv_img_bgr is None:
            return

        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y

        x1 = max(self.offset_x, min(self.offset_x + self.disp_w, x1))
        y1 = max(self.offset_y, min(self.offset_y + self.disp_h, y1))

        if self.sel_rect_id is not None:
            self.canvas.delete(self.sel_rect_id)

        self.sel_rect_id = self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline="#ffcc00",
            width=2,
            fill="#ffcc00",
            stipple="gray25",
        )

    def on_mouse_up(self, event):
        if self.drag_start is None or self.cv_img_bgr is None:
            self.drag_start = None
            return

        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        self.drag_start = None

        x0 = max(self.offset_x, min(self.offset_x + self.disp_w, x0))
        y0 = max(self.offset_y, min(self.offset_y + self.disp_h, y0))
        x1 = max(self.offset_x, min(self.offset_x + self.disp_w, x1))
        y1 = max(self.offset_y, min(self.offset_y + self.disp_h, y1))

        left, right = sorted([x0, x1])
        top, bottom = sorted([y0, y1])

        if (right - left) < 6 or (bottom - top) < 6:
            self.clear_selection()
            return

        ox1, oy1 = self._disp_to_orig(left, top)
        ox2, oy2 = self._disp_to_orig(right, bottom)

        ox1, ox2 = sorted([max(0, min(self.orig_w, ox1)), max(0, min(self.orig_w, ox2))])
        oy1, oy2 = sorted([max(0, min(self.orig_h, oy1)), max(0, min(self.orig_h, oy2))])

        self.roi = (ox1, oy1, ox2, oy2)
        self.selection_info.set(f"Selection: x={ox1}:{ox2}, y={oy1}:{oy2}")
        self.status.set("Area selected. Click 'Run OCR'.")
        self.redraw_image()

    def clear_selection(self, silent: bool = False):
        self.roi = None
        self.selection_info.set("Selection: full image")

        if self.sel_rect_id is not None:
            try:
                self.canvas.delete(self.sel_rect_id)
            except Exception:
                pass
            self.sel_rect_id = None

        if not silent:
            self.status.set("Selection cleared (full image).")

    # =========================
    # OCR
    # =========================
    def run_ocr(self):
        if self.cv_img_bgr is None:
            messagebox.showwarning("Warning", "Load an image (drag & drop, Ctrl+V, or the button).")
            return

        self.btn_run.config(state="disabled")
        self.status.set("Running OCR...")

        lang_code = self._get_lang_code()

        def worker():
            try:
                img = self.cv_img_bgr
                if self.roi is not None:
                    x1, y1, x2, y2 = self.roi
                    img = img[y1:y2, x1:x2].copy()

                result = ocr_bgr(img, lang=lang_code)
            except Exception as e:
                self.after(0, lambda: self._on_error(e))
                return

            self.after(0, lambda: self._on_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, text):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.status.set("Done.")
        self.btn_run.config(state="normal")

    def _on_error(self, err):
        messagebox.showerror("OCR Error", str(err))
        self.status.set("Error.")
        self.btn_run.config(state="normal")

    # =========================
    # Text
    # =========================
    def clear_text(self):
        self.text.delete("1.0", "end")
        self.status.set("Text cleared.")

    def copy_text(self):
        content = self.text.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Copy", "There is no text to copy.")
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status.set("Text copied.")


if __name__ == "__main__":
    OCRApp().mainloop()