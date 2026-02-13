import os
import cv2
import numpy as np
import pytesseract
import shutil

def configure_tesseract():
    exe = shutil.which("tesseract")
    if exe:
        pytesseract.pytesseract.tesseract_cmd = exe
        return

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            pytesseract.pytesseract.tesseract_cmd = c
            return

    raise RuntimeError(
        "Tesseract not found. Please install Tesseract OCR "
        "and make sure it is in PATH (or installed in Program Files)."
    )

configure_tesseract()

def _preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:

    # 1) Normalize resolution (standardize by the longest side)
    h, w = img_bgr.shape[:2]
    long_side = max(h, w)

    TARGET_LONG_SIDE = 1800
    if long_side < TARGET_LONG_SIDE:
        scale = TARGET_LONG_SIDE / long_side
        img_bgr = cv2.resize(
            img_bgr,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

    # 2) Convert to grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 3) Improve local contrast with CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 4) Light denoising (median filter)
    gray = cv2.medianBlur(gray, 3)

    # 5) Sharpen text edges (unsharp mask)
    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)

    # 6) Binarize using Otsu's thresholding
    thr = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    return thr


def ocr_bgr(img_bgr: np.ndarray, lang: str = "por") -> str:
    if img_bgr is None:
        raise ValueError("Empty image (None).")

    pre = _preprocess_for_ocr(img_bgr)

    # Tesseract settings:
    # --oem 3: use the default OCR engine mode
    # --psm 6: assume a uniform block of text
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(pre, lang=lang, config=config)


def ocr_image(image_path: str, lang: str = "por") -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File not found: {image_path}")

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not open the image. Check the file path/format.")

    return ocr_bgr(img, lang=lang)