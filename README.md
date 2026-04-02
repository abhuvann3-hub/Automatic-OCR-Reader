# 📄 Automatic OCR Reader

A Flask web application that automatically extracts structured asset data (laptops, accessories) from PDF invoices using Tesseract OCR.

---

## ✨ Features

- Upload PDF invoices via a drag-and-drop interface
- Parallel OCR processing using Python multiprocessing
- Extracts invoice number, date, laptop serial numbers, usernames, and accessories
- Exports results as two clean CSV files (`laptops_*.csv`, `accessories_*.csv`)
- User authentication with hashed passwords
- Archives processed PDFs automatically

---

## 🖥️ System Requirements

Before installing Python packages, install these system-level dependencies:

### Tesseract OCR

| OS | Command |
|---|---|
| **Windows** | Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Ubuntu/Debian** | `sudo apt install tesseract-ocr` |
| **macOS** | `brew install tesseract` |

### Poppler (required by `pdf2image`)

| OS | Command |
|---|---|
| **Windows** | Download from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) and add `bin/` to PATH |
| **Ubuntu/Debian** | `sudo apt install poppler-utils` |
| **macOS** | `brew install poppler` |

---

## 🚀 Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/Automatic-OCR-Reader.git
cd Automatic-OCR-Reader
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment variables (recommended)

Create a `.env` file in the project root:

```
SECRET_KEY=your-random-secret-key-here
FLASK_DEBUG=false
```

> You can generate a secure key with: `python -c "import secrets; print(secrets.token_hex(32))"`

### 5. Run the app

```bash
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 📁 Project Structure

```
Automatic-OCR-Reader/
│
├── app.py                      # Flask application
├── extract_invoice_assets.py   # OCR + data extraction logic
├── requirements.txt            # Python dependencies
├── .gitignore
│
├── templates/                  # HTML templates
│   ├── login.html
│   ├── register.html
│   └── index.html
│
├── uploads/                    # Uploaded PDFs (auto-created, git-ignored)
├── output/                     # Generated CSVs (auto-created, git-ignored)
├── archive/                    # Processed PDFs (auto-created, git-ignored)
└── logs/                       # OCR logs (auto-created, git-ignored)
```

---

## 📊 Output Format

After processing, two CSV files are created in the `output/` folder:

**`laptops_<timestamp>.csv`**

| Invoice No | Invoice Date | Category | Item | User | Serial | Qty | Notes |
|---|---|---|---|---|---|---|---|

**`accessories_<timestamp>.csv`**

| Invoice No | Invoice Date | Category | Item | User | Serial | Qty | Notes |
|---|---|---|---|---|---|---|---|

---

## 🔒 Security Notes

- Passwords are hashed using `werkzeug.security` (PBKDF2-SHA256)
- `users.db` is excluded from version control via `.gitignore`
- Set a strong `SECRET_KEY` via environment variable in production
- Never run with `FLASK_DEBUG=true` in production

---

## 🐛 Troubleshooting

**`TesseractNotFoundError`** — Tesseract is not installed or not on PATH. See system requirements above.

**`PDFInfoNotInstalledError`** — Poppler is not installed. See system requirements above.

**Blank OCR output** — Try increasing the DPI in `extract_invoice_assets.py` (`dpi=200` → `dpi=300`).

---

## 📝 License

MIT
