Love this stage 😄 — this is where your project starts to **look professional**.

Below is a **clean, modern, production-ready README.md** you can copy-paste directly.
It’s written to impress **clients, reviewers, and recruiters**.

---

# 📄 Universal Invoice Processing Engine

### AI-Powered PDF & Image → Structured JSON Converter

> A robust, production-ready system that converts **multi-page invoices (PDF/Image)** into a **clean, validated JSON schema** using OCR and modern AI models.

---

## ✨ Key Features

* 📑 **Multi-page PDF & Image support**
* 🔍 **High-accuracy OCR** (Tesseract + PDF parsing)
* 🧠 **AI-assisted JSON extraction** (Gemini / LLM-based)
* 🧾 **Strict invoice JSON schema validation**
* 🧠 **Handles messy, real-world invoices**
* 🧩 **Modular architecture (ERP-ready)**
* 🌐 **Web UI powered by Streamlit**
* ☁️ **Cloud deployable (Render / Railway / VPS)**

---

## 🏗️ Architecture Overview

```
image_pdf_to_json/
│
├── streamlit_app.py            # Web UI
│
├── invoice_engine/
│   ├── local_extraction.py     # OCR & text extraction
│   ├── multipage_parser.py     # Multi-page invoice logic
│   ├── barcode_extraction.py  # Barcode / QR (optional)
│   ├── validation.py           # JSON schema validation
│   └── schema.py               # Invoice JSON schema
│
├── requirements.txt
├── runtime.txt                 # Python version (3.11)
├── render.yaml                 # Render deployment config
└── README.md
```

---

## 📂 Supported Inputs

* ✅ PDF (single & multi-page)
* ✅ Scanned invoices
* ✅ Camera images
* ✅ Mixed text + image invoices

---

## 🧾 Output Format

The system produces a **structured JSON** including:

* Vendor details
* Invoice metadata
* Customer information
* Line items
* Taxes & totals
* Payment instructions
* Validation confidence

> Designed to plug directly into **ERP / Accounting systems**

---

## ⚙️ Tech Stack

| Layer            | Technology            |
| ---------------- | --------------------- |
| UI               | Streamlit             |
| OCR              | Tesseract, PDFPlumber |
| Image Processing | OpenCV                |
| AI / LLM         | Gemini API            |
| Validation       | Custom JSON schema    |
| Deployment       | Render / Railway      |
| Language         | Python 3.11           |

---

## 🚀 Getting Started (Local Setup)

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/image_pdf_to_json.git
cd image_pdf_to_json
```

### 2️⃣ Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ On Windows, install **Poppler** separately for PDF support.

---

### 4️⃣ Set environment variables

```bash
export GEMINI_API_KEY="your_api_key_here"
```

(Use Render / Railway dashboard for production)

---

### 5️⃣ Run the app

```bash
streamlit run streamlit_app.py
```

---

## ☁️ Deployment (Render)

This project includes a **ready-to-use `render.yaml`**.

System dependencies installed automatically:

* `libzbar0`
* `libgl1`
* `tesseract-ocr`
* `poppler-utils`

Deploy steps:

1. Push code to GitHub
2. Create a new Render Web Service
3. Select repository
4. Click **Deploy**

---

## 🧠 Design Decisions

* **LLM used only for intelligence**, not raw OCR
* **Defensive imports** for optional native dependencies
* Barcode detection is **optional**, not blocking
* Built for **real-world invoice noise**

---

## 🔐 Security Notes

* ❌ No API keys committed to repo
* ✅ Environment-based secrets
* ✅ Safe for production & demos

---

## 📈 Future Enhancements

* 🔄 Async batch processing
* 🧠 Auto-confidence scoring
* 🧾 Line-item reconciliation logic
* 📊 ERP / SAP / Tally integrations
* 🔍 Table structure detection

---

## 👨‍💻 Author
@Sri174 - VEERACHINNU M

---
