from fastapi import UploadFile, File, APIRouter, HTTPException
from typing import List
import uuid, os

router = APIRouter()
UPLOAD_DIR = "uploads"

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "text/csv": "csv",
    "text/plain": "txt",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
}

@router.post("/upload_files")
async def upload_files(files: List[UploadFile] = File(...)):
    task_id = str(uuid.uuid4())
    save_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(save_dir, exist_ok=True)

    results = []

    for file in files:
        content_type = file.content_type
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}"
            )

        file_type = ALLOWED_MIME_TYPES[content_type]
        file_path = os.path.join(save_dir, file.filename)

        with open(file_path, "wb") as f:
            f.write(await file.read())

        results.append({
            "filename": file.filename,
            "file_type": file_type,
            "path": file_path
        })

    return {
        "task_id": task_id,
        "files": results
    }
