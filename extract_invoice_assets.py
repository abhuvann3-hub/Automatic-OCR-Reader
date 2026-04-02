import sys
import os
import re
import json
import pytesseract
import pandas as pd
from pdf2image import convert_from_path
from datetime import datetime
import logging
import time

# ⭐ NEW IMPORTS (STEP 1)
from multiprocessing import Pool, cpu_count
import cv2
import numpy as np

# ===== LOGGING SETUP =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "ocr.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.info("===== OCR SCRIPT STARTED =====")
total_start = time.time()

INPUT_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if not os.path.exists(tesseract_path):
    logging.error("Tesseract not installed")
    sys.exit(1)

pytesseract.pytesseract.tesseract_cmd = tesseract_path


# ⭐ STEP 2 — OCR WORKER FUNCTION
def ocr_single_page(image):
    try:
        img = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
        img = cv2.resize(img, None, fx=0.8, fy=0.8)  # faster OCR
        return pytesseract.image_to_string(img)
    except Exception as e:
        logging.exception(f"OCR worker failed: {e}")
        return ""


# ================= EXTRACTION FUNCTIONS (UNCHANGED) =================
def extract_invoice_number(text):
    match = re.search(r'FSE/\d{2}-\d{2}/\d+', text)
    return match.group(0) if match else ""

def extract_invoice_date(text):
    matches = re.findall(r'\b\d{2}-[A-Za-z]{3}-\d{2}\b', text)
    return matches[0] if matches else ""

def valid_serial(sn):
    return len(sn) >= 5 and re.search(r'\d', sn)

def valid_username(name):
    if re.search(r'\d', name): return False
    if len(name.split()) < 2: return False
    invalid_words=["Courier","Charges","Goods"]
    return not any(w.lower() in name.lower() for w in invalid_words)

def parse_laptops(text, invoice_no, invoice_date):
    rows=[]
    lines=[l.strip() for l in text.split("\n") if l.strip()]
    laptop_qty=""

    for line in lines:
        if re.search(r'\b[A-Za-z]+\s+Laptop\b', line):
            q=re.search(r'(\d+)\s*pcs', line)
            if q: laptop_qty=q.group(1)
            break

    for i,line in enumerate(lines):
        sn=re.search(r'S\.?N\.?\s*[:\-]?\s*([A-Z0-9]+)', line)
        if sn:
            serial=sn.group(1)
            if not valid_serial(serial): continue

            username=""
            before=line.split("S")[0].strip()
            if valid_username(before): username=before
            elif i>0 and valid_username(lines[i-1]): username=lines[i-1]

            rows.append([invoice_no,invoice_date,"Laptop","Laptop",username,serial,laptop_qty,""])
    return rows

def parse_accessories(text, invoice_no, invoice_date):
    rows=[]
    lines=[l.strip() for l in text.split("\n") if l.strip()]
    keys=["Keyboard","Mouse","EPOS","Laptop Bag"]

    for line in lines:
        for k in keys:
            if k.lower() in line.lower():
                q=re.search(r'(\d+)\s*pcs', line)
                qty=q.group(1) if q else ""
                rows.append([invoice_no,invoice_date,"Accessory",k,"","",qty,""])
                break
    return rows


# ================= MAIN FUNCTION =================
def main():

    if len(sys.argv) < 2:
        logging.error("No PDF file passed")
        sys.exit(1)

    pdf_file = sys.argv[1]
    pdf_path = os.path.join(INPUT_DIR, pdf_file)

    logging.info(f"Processing file: {pdf_file}")
    file_start = time.time()

    # ---------- PDF → IMAGE ----------
    step=time.time()
    images=convert_from_path(pdf_path,dpi=150)
    logging.info(f"PDF conversion time: {time.time()-step:.2f}s | Pages: {len(images)}")

    # ⭐ STEP 3 — PARALLEL OCR
    step=time.time()
    workers=max(1,cpu_count()-1)

    logging.info(f"Starting Parallel OCR with {workers} workers")
    with Pool(workers) as pool:
        results=pool.map(ocr_single_page,images)

    full_text="\n".join(results)
    logging.info(f"OCR time: {time.time()-step:.2f}s")

    # ---------- Extraction ----------
    step=time.time()

    invoice_no=extract_invoice_number(full_text)
    invoice_date=extract_invoice_date(full_text)

    laptop_rows=parse_laptops(full_text,invoice_no,invoice_date)
    accessory_rows=parse_accessories(full_text,invoice_no,invoice_date)

    logging.info(f"Extraction time: {time.time()-step:.2f}s")
    logging.info(f"Laptops: {len(laptop_rows)} | Accessories: {len(accessory_rows)}")

    # ---------- CSV ----------
    step=time.time()
    logging.info("Progress 90% - Writing CSV")

    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")

    laptop_csv=os.path.join(OUTPUT_DIR,f"asset_inventory_laptops_{timestamp}.csv")
    accessory_csv=os.path.join(OUTPUT_DIR,f"asset_inventory_accessories_{timestamp}.csv")

    pd.DataFrame(laptop_rows).to_csv(laptop_csv,index=False)
    pd.DataFrame(accessory_rows).to_csv(accessory_csv,index=False)

    logging.info(f"CSV writing time: {time.time()-step:.2f}s")

    # ---------- Archive ----------
    step=time.time()
    archive_path=os.path.join(ARCHIVE_DIR,pdf_file)
    if os.path.exists(archive_path):
        name,ext=os.path.splitext(pdf_file)
        archive_path=os.path.join(ARCHIVE_DIR,f"{name}_{datetime.now().strftime('%H%M%S')}{ext}")

    os.rename(pdf_path,archive_path)

    logging.info(f"Archive move time: {time.time()-step:.2f}s")
    logging.info(f"File completed in {time.time()-file_start:.2f}s")
    logging.info(f"TOTAL TIME: {time.time()-total_start:.2f}s")
    logging.info("===== OCR SCRIPT FINISHED =====\n")


# ⭐ CRITICAL FIX — prevents Flask crash
if __name__ == "__main__":
    main()