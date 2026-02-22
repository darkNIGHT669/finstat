# FinStat Extractor — Internal Research Portal

**Option A: Financial Statement Extraction Tool**

Upload a financial statement PDF → get a structured, analyst-ready Excel workbook with all Income Statement line items extracted, validated, and color-coded.

---

## ⚡ Deploy in 15 Minutes

### 1. Deploy Backend to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set **Root Directory** to `backend`
5. Set **Build Command**: `pip install -r requirements.txt`
6. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Add Environment Variable:
   - Key: `ANTHROPIC_API_KEY`
   - Value: `sk-ant-...` (your Anthropic key)
8. Deploy → copy the URL (e.g., `https://finstat-backend.onrender.com`)

### 2. Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → New Project
2. Import the same GitHub repo
3. Set **Root Directory** to `frontend`
4. Add Environment Variable:
   - Key: `VITE_API_URL`
   - Value: `https://finstat-backend.onrender.com` (your Render URL from step 1)
5. Deploy → you'll get a public URL

---

## Architecture

```
User Browser (Vercel)
       │  PDF upload
       ▼
FastAPI Backend (Render)
  ├── pdfplumber  → extract text + tables from PDF
  ├── Section detector → find income statement pages
  ├── Claude claude-sonnet-4-6 → extract line items as structured JSON
  ├── Rule engine → arithmetic cross-checks
  └── openpyxl   → generate formatted Excel workbook
       │
       ▼  
  .xlsx file download
```

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + Tailwind (Vercel) |
| Backend | FastAPI + Python 3.11 (Render) |
| PDF Parsing | pdfplumber |
| LLM | Anthropic claude-sonnet-4-6 |
| Output | openpyxl |

## Output Excel Workbook

- **Income Statement tab** — 20 canonical line items × N years, color-coded by confidence, with source labels and page references
- **Extraction Metadata tab** — full audit trail
- **How to Read This tab** — legend and guide

## Free Tier Limitations

- Cold start: First request ~15–30s after idle
- Max PDF: ~10MB recommended (20MB hard limit)
- 1 concurrent request
- Results not persisted — download immediately

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-ant-... uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```
