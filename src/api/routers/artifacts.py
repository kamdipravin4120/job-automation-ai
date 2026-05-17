from __future__ import annotations

import os
import pathlib
import shutil
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.core.deps import get_current_device

router = APIRouter()

_ARTIFACTS_DIR = pathlib.Path("artifacts")
_RESUMES_DIR  = _ARTIFACTS_DIR / "resumes"
_COVERS_DIR   = _ARTIFACTS_DIR / "covers"
_UPLOADS_DIR  = _ARTIFACTS_DIR / "uploads"

_ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".docx", ".doc"}


def _file_info(p: pathlib.Path) -> dict[str, Any]:
    stat = p.stat()
    return {
        "name":     p.name,
        "size":     stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


class ArtifactsOut(BaseModel):
    resumes: list[dict[str, Any]]
    covers:  list[dict[str, Any]]
    uploads: list[dict[str, Any]]


@router.get("", response_model=ArtifactsOut)
async def list_artifacts(_device=Depends(get_current_device)):
    def _list(d: pathlib.Path) -> list[dict[str, Any]]:
        if not d.exists():
            return []
        files = sorted(d.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        return [_file_info(f) for f in files if f.is_file()]

    return ArtifactsOut(
        resumes=_list(_RESUMES_DIR),
        covers=_list(_COVERS_DIR),
        uploads=_list(_UPLOADS_DIR),
    )


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), _device=Depends(get_current_device)):
    suffix = pathlib.Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, or DOC files accepted")
    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOADS_DIR / (file.filename or "upload")
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return {"name": dest.name, "size": dest.stat().st_size}


@router.get("/download/{subdir}/{filename}")
async def download_artifact(
    subdir: str,
    filename: str,
    _device=Depends(get_current_device),
):
    if subdir not in ("resumes", "covers", "uploads"):
        raise HTTPException(status_code=400, detail="Invalid subdir")
    # prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _ARTIFACTS_DIR / subdir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)
