# 🛡️ Project Protector – Intelligent PII Detection, Masking & Restoration System

## 🧩 Chosen Problem Statement

In sensitive industries like finance, healthcare, and government, the need to handle Personally Identifiable Information (PII) securely is paramount. Manual data redaction processes are time-consuming, error-prone, and non-scalable. Rule-based systems (e.g., regex, keyword matching) suffer from low precision/recall trade-offs and lack adaptability to domain-specific or novel sensitive terms, leading to compliance and operational risks. The challenge is to build a system that can automatically detect, mask, and restore sensitive data, even from scanned documents and domain-specific formats, while allowing users to customize and improve the model over time.

## 🧠 Explanation of the Solution

Our solution — Project Protector — is an AI-powered PII processing pipeline that combines the robustness of Named Entity Recognition (NER), the adaptability of OpenAI’s ChatGPT, and the compliance-ready architecture of Microsoft Presidio. It supports both structured (CSV, TXT) and unstructured formats (PDF, images) through integrated OCR.

### Key Components:
1. Multi-Layered PII Detection:

	- NER Engine (SpaCy/Huggingface) for baseline entity recognition.

	- Domain Dictionary Filter for organization-specific terms (e.g., “Loan ID”, “Medical Record #”).

	- ChatGPT API for fuzzy candidate mining and novel sensitive pattern discovery (e.g., obfuscated names, nicknames).

2. Presidio Integration:

	- All results from above layers are passed to Presidio Analyzer for standardized detection and validation.

	- Presidio Anonymizer applies irreversible masking or reversible encryption.

3. OCR for Scanned Documents:

	- Using EasyOCR to extract multilingual text (English + Malay) from PDF/image files before PII processing.

4. Restoration Mode:

	- Encrypted sensitive info is stored with metadata (bounding box, type, encryption key).

	- Users can later decrypt and restore the data for authorized recovery.

5. Continuous Improvement:

	- Detected new terms by ChatGPT are added to the domain dictionary.

	- A background script can re-train the NER model periodically with accumulated data to improve detection accuracy.

### Supported Features:
- 🔐 End-to-end encryption for PII

- 🧾 Supports .csv, .txt, .pdf, .jpg, .png, .docx, xlsx, .xls formats

- 🌐 Web frontend with drag-drop upload

- 🔍 Real-time OCR-based PII scanning

- 🔄 Masked image restoration (optional)

- 🧠 Auto-learning mechanism from ChatGPT feedback

### 🛠️ Tech Stack Used

| Category             | Library / Framework                                                 | Purpose / Description                                |
| -------------------- | ------------------------------------------------------------------- | ---------------------------------------------------- |
| **Web Backend**      | `FastAPI`, `Uvicorn`, `Starlette`                                   | REST API Framework with ASGI support                 |
| **Frontend UI**      | `Font Awesome`, `HTML`, `CSS`                                       | Icons, static content rendering                      |
| **Data Base**        | `SQLAlchemy`, `SQLite`                                              | Data storage and querying for audit logs     	    |
| **OCR**              | `EasyOCR`, `pytesseract`, `pdf2image`                               | Optical Character Recognition from images/PDFs       |
| **PII / NER**        | `spacy`, `presidio`, `transformers`                                 | Named Entity Recognition and PII detection           |
| **LLM Integration**  | `openai`, `tiktoken`                                                | GPT model integration & token counting               |
| **NLP Support**      | `nltk`, `sentencepiece`, `regex`                                    | Language preprocessing and tokenization              |
| **Computer Vision**  | `opencv`, `imutils`, `deskew`                                       | Image preprocessing, alignment                       |
| **Data Handling**    | `pandas`, `numpy`, `scikit-image`                                   | Tabular & image data handling                        |
| **Security**         | `cryptography`, `pycryptodome`                                      | Data encryption / decryption                         |
| **Document Parsing** | `docx2txt`, `python-docx`, `python-pptx`							 | MS Office and email file parsing                     |
| **Deep Learning**    | `tensorflow`, `torch`, `keras`                                      | Model training/inference (NER / OCR post-processing) |
| **Logging/UI**       | `rich`, `colorama`                                                  | Colored logging and CLI visuals                      |
| **Utilities**        | `python-multipart`, `requests`, `httpx`, `click`                    | Web and CLI helpers                                  |

## How to Install:

### Requirement 
Pyhton 3.11.6

poppler-24.08.0 and change decrypt_pdf.py poppler_path into your poppler path just install
https://github.com/oschwartz10612/poppler-windows/releases/tag/v24.08.0-0

<pre>
python -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
</pre>


## Presentation Deck:

[Project Protector Presentation Deck](https://www.canva.com/design/DAGub40Ie78/bGUAwjYC5osyRcr6vmW8Og/edit?utm_content=DAGub40Ie78&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)

[User Munual](https://www.canva.com/design/DAGwCao0VeY/57P8u3J6Q6zVJcSqZAS9aw/edit?utm_content=DAGwCao0VeY&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)
