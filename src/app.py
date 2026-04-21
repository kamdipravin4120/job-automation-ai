import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.utils.config import load_config
from src.orchestrator.pipeline import JobApplicationPipeline
from src.models import CandidateProfile, ApplicationRecord
from src.tracking.sqlite_repository import SqliteTrackingRepository

app = FastAPI(title="Job Automation AI Dashboard")
CONFIG_PATH = Path("config.yaml")
config = load_config(CONFIG_PATH)

# Serve all artifacts statically so they can be downloaded
Path("artifacts").mkdir(exist_ok=True)
app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

class StatusUpdate(BaseModel):
    status: str

@app.get("/api/v1/applications/{source}/{job_id}")
async def get_application(source: str, job_id: str):
    repo = SqliteTrackingRepository(Path(config.tracking.sqlite_path))
    record = repo.get_record(source, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    return record

@app.post("/api/v1/applications/{source}/{job_id}/status")
async def update_application_status(source: str, job_id: str, update: StatusUpdate):
    repo = SqliteTrackingRepository(Path(config.tracking.sqlite_path))
    record = repo.get_record(source, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    
    record.status = update.status
    record.last_updated_at = datetime.now()
    if update.status == "Applied":
        record.applied_at = datetime.now()
    
    repo.upsert(record)
    return {"status": "updated", "record": record}

@app.post("/api/v1/applications/{source}/{job_id}/tailor")
async def tailor_application(source: str, job_id: str):
    repo = SqliteTrackingRepository(Path(config.tracking.sqlite_path))
    record = repo.get_record(source, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    
    from src.models import JobPosting, CandidateProfile
    from src.resume.engine import ResumeService
    
    # Load profile
    profile_path = Path(config.app.profile_path)
    if not profile_path.exists():
         raise HTTPException(status_code=400, detail="Profile not found. Please upload resume first.")
    
    with profile_path.open() as f:
        profile = CandidateProfile.model_validate(json.load(f))
        
    # Convert Record to JobPosting for ResumeService
    job = JobPosting(
        job_id=record.job_id,
        source=record.source,
        title=record.job_title,
        company=record.company,
        location=record.location,
        url=record.job_url,
        description=record.notes or "No description available", # Notes usually stores JD text in this pipeline
        posted_at=None
    )
    
    service = ResumeService(config.resume, Path("."), logging.getLogger("dashboard"))
    bundle, artifacts = service.build_assets(profile=profile, job=job)
    
    # Update record with new asset paths
    record.resume_docx_path = str(artifacts.resume_docx)
    record.resume_text_path = str(artifacts.resume_text)
    record.cover_letter_path = str(artifacts.cover_letter)
    record.recruiter_pitch_path = str(artifacts.recruiter_pitch)
    record.status = "Tailored"
    record.last_updated_at = datetime.now()
    
    repo.upsert(record)
    return {"status": "tailored", "record": record}

@app.get("/api/v1/profile")
async def get_profile():
    config = load_config(CONFIG_PATH)
    profile_path = Path(config.app.profile_path)
    if not profile_path.exists():
        return {"error": "Profile not found"}
    with profile_path.open("r") as f:
        import json
        return json.load(f)

@app.get("/api/v1/applications", response_model=List[ApplicationRecord])
async def get_applications():
    config = load_config(CONFIG_PATH)
    # Using the existing SQLite tracker logic
    from src.tracking.sqlite_repository import SqliteTrackingRepository
    tracker = SqliteTrackingRepository(Path(config.tracking.sqlite_path))
    return tracker.list_records()

@app.post("/api/v1/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    # Save file
    upload_dir = Path("artifacts/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    content = await file.read()
    with file_path.open("wb") as f:
        f.write(content)
    
    # AI Parsing
    config = load_config(CONFIG_PATH)
    from src.resume.engine import ResumeService
    import logging
    from pypdf import PdfReader
    import io
    
    # Handle PDF to text conversion
    try:
        reader = PdfReader(io.BytesIO(content))
        raw_text = ""
        for page in reader.pages:
            raw_text += page.extract_text() + "\n"
        
        if not raw_text.strip():
            raw_text = content.decode("utf-8", errors="ignore")
    except Exception:
        raw_text = content.decode("utf-8", errors="ignore") 
    
    try:
        service = ResumeService(config.resume, Path("."), logging.getLogger("dashboard"))
        profile = service.analyze_resume_text(raw_text)
        
        # Save the new profile
        profile_path = Path(config.app.profile_path)
        with profile_path.open("w") as f:
            f.write(profile.model_dump_json(indent=2))
            
        return {
            "message": "Resume analyzed successfully. Profile updated.",
            "profile": profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")

@app.post("/api/v1/pipeline/sync")
async def trigger_sync():
    # Trigger matching and notion sync
    try:
        pipeline = JobApplicationPipeline(CONFIG_PATH)
        pipeline.sync_all()
        return {"message": "Sync completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
