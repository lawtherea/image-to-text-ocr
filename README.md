[![Download](https://img.shields.io/badge/Download-Latest%20Release-blue?style=for-the-badge)](https://github.com/lawtherea/image-to-text-ocr/releases/latest)

# OCRApp (Image → Text)

A simple desktop app to extract text from images using **Tesseract OCR**.
You can **drag & drop** an image or **paste (Ctrl+V)**, optionally select an area, and run OCR.

![OCRApp](https://github.com/user-attachments/assets/9b73c9c0-6197-41e4-9978-2526b20352a5)

---

## Requirements

### 1) Windows

- **Python is NOT required** if you are using the `.exe`.

### 2) Install Tesseract OCR (required)

1. Download and install Tesseract for Windows: https://tesseract-ocr.github.io/tessdoc/Installation.html
2. During installation, keep the default install path if possible:
   - `C:\Program Files\Tesseract-OCR\tesseract.exe`

Tip: If the app says it cannot find Tesseract, add Tesseract to your **PATH** or reinstall it in the default location.

---

## How to use

1. Open `OCRApp.exe`
2. Load an image
3. (Optional) Drag the mouse on the preview to select an area
4. Choose the language in the dropdown (default: **Portuguese + English**)
5. Click **Run OCR**
6. Use **Copy text** to copy the extracted text

---

## Running the code (from source)

If you want to run the project from source instead of using the `.exe`:

1. **Python**  
   Install Python 3 (3.10 or newer recommended).  
   Check in a terminal: `python --version` or `py --version`.

2. **Virtual environment (recommended)**  
   In the project folder:

   ```bash
   python -m venv venv
   ```

   Activate it:
   - **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
   - **Windows (CMD):** `venv\Scripts\activate.bat`

3. **Install dependencies**  
   With the environment activated:

   ```bash
   pip install -r requirements.txt
   ```

4. **Tesseract OCR**  
   Follow the [Install Tesseract OCR](#2-install-tesseract-ocr-required) section above (required).

5. **Run the app**  
   From the project root:
   ```bash
   python gui.py
   ```
   The app window will open.

---

## Notes / Troubleshooting

### “Tesseract not found”

- Make sure Tesseract is installed.
- Check if `tesseract.exe` exists at:
  - `C:\Program Files\Tesseract-OCR\tesseract.exe`
- If needed, add Tesseract to your system PATH.

### Drag & Drop not working

- Make sure you are using the provided build with `tkinterdnd2` included.
- Try running the app normally (not as Administrator). Some drag & drop hooks can fail with admin privileges.

### OCR quality

- OCR works best with:
  - high-resolution images
  - sharp text
  - good contrast
- If the image is blurry or heavily compressed, results may degrade.

---

## Credits

- OCR engine: Tesseract OCR
- Python wrapper: pytesseract
- GUI: Tkinter + sv-ttk + tkinterdnd2
