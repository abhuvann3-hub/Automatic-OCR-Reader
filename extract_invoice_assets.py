import sys
import os
import re
import logging
import time
from datetime import datetime
from multiprocessing import Pool, cpu_count

import cv2
import numpy as np
import pandas as pd
import pytesseract
from pdf2image import convert_from_path

# ===== PATHS =====

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")
LOG_DIR    = os.path.join(BASE_DIR, "logs")

for d in [INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# ===== LOGGING =====

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "ocr.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ===== TESSERACT SETUP =====

def find_tesseract() -> str:
    """Locate the Tesseract executable across platforms."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",   # Windows
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",                               # Linux
        "/usr/local/bin/tesseract",                         # macOS (Homebrew)
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # If none found, assume it's on PATH (Linux/macOS installs often are)
    return "tesseract"


pytesseract.pytesseract.tesseract_cmd = find_tesseract()


# ===== OCR =====

def ocr_single_page(image) -> str:
    """Convert a PIL image to grayscale and extract text via Tesseract."""
    try:
        # PIL images from pdf2image are RGB — use RGB→GRAY, not BGR→GRAY
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        # Apply light thresholding to improve OCR accuracy on scanned docs
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return pytesseract.image_to_string(img)
    except Exception as e:
        logging.exception(f"OCR worker failed: {e}")
        return ""


# ===== EXTRACTION HELPERS =====

def extract_invoice_number(text: str) -> str:
    match = re.search(r'FSE/\d{2}-\d{2}/\d+', text)
    return match.group(0) if match else ""


def extract_invoice_date(text: str) -> str:
    matches = re.findall(r'\b\d{2}-[A-Za-z]{3}-\d{2}\b', text)
    return matches[0] if matches else ""


def valid_serial(sn: str) -> bool:
    return len(sn) >= 5 and bool(re.search(r'\d', sn))


def valid_username(name: str) -> bool:
    if re.search(r'\d', name):
        return False
    if len(name.split()) < 2:
        return False
    invalid_words = ["Courier", "Charges", "Goods"]
    return not any(w.lower() in name.lower() for w in invalid_words)


def parse_laptops(text: str, invoice_no: str, invoice_date: str) -> list:
    rows = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    laptop_qty = ""

    for line in lines:
        if re.search(r'\b[A-Za-z]+\s+Laptop\b', line):
            q = re.search(r'(\d+)\s*pcs', line)
            if q:
                laptop_qty = q.group(1)
            break

    for i, line in enumerate(lines):
        sn = re.search(r'S\.?N\.?\s*[:\-]?\s*([A-Z0-9]+)', line)
        if sn:
            serial = sn.group(1)
            if not valid_serial(serial):
                continue
            username = ""
            before = line.split("S")[0].strip()
            if valid_username(before):
                username = before
            elif i > 0 and valid_username(lines[i - 1]):
                username = lines[i - 1]
            rows.append([invoice_no, invoice_date, "Laptop", "Laptop", username, serial, laptop_qty, ""])

    return rows


def parse_accessories(text: str, invoice_no: str, invoice_date: str) -> list:
    rows = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    keys = ["Keyboard", "Mouse", "EPOS", "Laptop Bag"]

    for line in lines:
        for k in keys:
            if k.lower() in line.lower():
                q = re.search(r'(\d+)\s*pcs', line)
                qty = q.group(1) if q else ""
                rows.append([invoice_no, invoice_date, "Accessory", k, "", "", qty, ""])
                break

    return rows


# ===== MAIN ENTRY POINT =====

def run_ocr(pdf_file: str) -> None:
    """
    Process a single PDF invoice file:
      1. Convert pages to images
      2. Run parallel OCR
      3. Extract structured data
      4. Write CSVs
      5. Archive the original PDF
    """
    pdf_path = os.path.join(INPUT_DIR, pdf_file)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logging.info(f"===== OCR STARTED: {pdf_file} =====")
    total_start = time.time()

    # 1 — PDF → images
    t = time.time()
    images = convert_from_path(pdf_path, dpi=200)
    logging.info(f"PDF→images: {time.time()-t:.2f}s | pages={len(images)}")

    # 2 — Parallel OCR
    t = time.time()
    workers = max(1, cpu_count() - 1)
    logging.info(f"OCR workers: {workers}")
    with Pool(workers) as pool:
        results = pool.map(ocr_single_page, images)
    full_text = "\n".join(results)
    logging.info(f"OCR: {time.time()-t:.2f}s")

    # 3 — Extract structured data
    t = time.time()
    invoice_no   = extract_invoice_number(full_text)
    invoice_date = extract_invoice_date(full_text)
    laptop_rows    = parse_laptops(full_text, invoice_no, invoice_date)
    accessory_rows = parse_accessories(full_text, invoice_no, invoice_date)
    logging.info(f"Extraction: {time.time()-t:.2f}s | laptops={len(laptop_rows)} accessories={len(accessory_rows)}")

    # 4 — Write CSVs
    t = time.time()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    columns = ["Invoice No", "Invoice Date", "Category", "Item", "User", "Serial", "Qty", "Notes"]
    pd.DataFrame(laptop_rows, columns=columns).to_csv(
        os.path.join(OUTPUT_DIR, f"laptops_{ts}.csv"), index=False
    )
    pd.DataFrame(accessory_rows, columns=columns).to_csv(
        os.path.join(OUTPUT_DIR, f"accessories_{ts}.csv"), index=False
    )
    logging.info(f"CSV write: {time.time()-t:.2f}s")

    # 5 — Archive original PDF
    archive_path = os.path.join(ARCHIVE_DIR, pdf_file)
    if os.path.exists(archive_path):
        name, ext = os.path.splitext(pdf_file)
        archive_path = os.path.join(ARCHIVE_DIR, f"{name}_{ts}{ext}")
    os.rename(pdf_path, archive_path)

    logging.info(f"Total time: {time.time()-total_start:.2f}s")
    logging.info(f"===== OCR FINISHED: {pdf_file} =====\n")


# ===== CLI USAGE =====

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_invoice_assets.py <filename.pdf>")
        sys.exit(1)
    run_ocr(sys.argv[1])
