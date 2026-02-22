import os
import uuid
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import shutil
from pathlib import Path

from extractor import extract_financials
from excel_writer import write_excel

app = FastAPI(title="Financial Statement Extraction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store
jobs: dict[str, dict] = {}

OUTPUT_DIR = Path(tempfile.gettempdir()) / "finstat_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing", "step": "Uploading PDF...", "progress": 5}

    # Save upload to temp file
    tmp_path = OUTPUT_DIR / f"{job_id}_input.pdf"
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    background_tasks.add_task(run_extraction, job_id, str(tmp_path))
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/download/{job_id}")
def download(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not complete")
    output_path = OUTPUT_DIR / f"{job_id}_output.xlsx"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(
        path=str(output_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="financial_extraction.xlsx",
    )


def run_extraction(job_id: str, pdf_path: str):
    try:
        jobs[job_id]["step"] = "Parsing PDF structure..."
        jobs[job_id]["progress"] = 15

        result = extract_financials(pdf_path, progress_callback=lambda step, pct: update_job(job_id, step, pct))

        jobs[job_id]["step"] = "Generating Excel workbook..."
        jobs[job_id]["progress"] = 90

        output_path = OUTPUT_DIR / f"{job_id}_output.xlsx"
        write_excel(result, str(output_path))

        jobs[job_id]["status"] = "done"
        jobs[job_id]["step"] = "Complete"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["summary"] = {
            "years": result.get("years_detected", []),
            "currency": result.get("extraction_metadata", {}).get("currency", "?"),
            "unit": result.get("extraction_metadata", {}).get("unit", "?"),
            "line_items_found": len([li for li in result.get("line_items", []) if any(v is not None for v in li.get("values", {}).values())]),
            "validation_status": result.get("extraction_metadata", {}).get("validation_status", "UNKNOWN"),
            "warnings": result.get("extraction_metadata", {}).get("warnings", []),
        }

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["step"] = f"Error: {str(e)}"
        jobs[job_id]["progress"] = 0
    finally:
        # Clean up input file
        try:
            os.remove(pdf_path)
        except Exception:
            pass


def update_job(job_id: str, step: str, pct: int):
    if job_id in jobs:
        jobs[job_id]["step"] = step
        jobs[job_id]["progress"] = pct
