from fastapi import UploadFile, File, APIRouter, HTTPException, Form, Request
from typing import List, Optional
import uuid, os, json, time
from app.services.audit_service import AuditService

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
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    enabled_pii_categories: Optional[str] = Form(None)
):
    start_time = time.time()
    task_id = str(uuid.uuid4())
    save_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(save_dir, exist_ok=True)

    # Get client information for audit
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    session_id = request.cookies.get("audit_session_id", str(uuid.uuid4()))

    # Parse PII categories selection
    pii_categories = []
    if enabled_pii_categories:
        try:
            pii_categories = json.loads(enabled_pii_categories)
        except json.JSONDecodeError:
            pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']  # Default
    else:
        pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']  # Default

    print(f"[INFO] Task {task_id}: Enabled PII categories: {pii_categories}")

    # Save PII selection to a config file for later use
    config_path = os.path.join(save_dir, "pii_config.json")
    with open(config_path, 'w') as f:
        json.dump({
            "enabled_pii_categories": pii_categories,
            "task_id": task_id
        }, f, indent=2)

    results = []

    # Initialize audit service
    with AuditService() as audit:
        for file in files:
            file_start_time = time.time()
            file_content = None

            try:
                content_type = file.content_type
                if content_type not in ALLOWED_MIME_TYPES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsupported file type: {content_type}"
                    )

                file_type = ALLOWED_MIME_TYPES[content_type]
                file_path = os.path.join(save_dir, file.filename)

                # Read and save file
                file_content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(file_content)

                # Calculate processing time
                processing_time = time.time() - file_start_time

                # Log successful file upload
                audit.log_file_operation(
                    session_id=session_id,
                    task_id=task_id,
                    operation_type="upload",
                    file_name=file.filename,
                    file_type=content_type,
                    file_size=len(file_content),
                    enabled_pii_categories=pii_categories,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    file_content=file_content,
                    processing_time=processing_time,
                    status="success"
                )

                results.append({
                    "filename": file.filename,
                    "file_type": file_type,
                    "path": file_path
                })

            except Exception as e:
                # Calculate processing time for failed upload
                processing_time = time.time() - file_start_time

                # Log failed file upload
                audit.log_file_operation(
                    session_id=session_id,
                    task_id=task_id,
                    operation_type="upload",
                    file_name=file.filename,
                    file_type=content_type if 'content_type' in locals() else "unknown",
                    file_size=len(file_content) if file_content else 0,
                    enabled_pii_categories=pii_categories,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    processing_time=processing_time,
                    status="error",
                    error_message=str(e)
                )

                # Log system error
                audit.log_system_event(
                    event_type="error",
                    event_category="system",
                    event_name="file_upload_failed",
                    event_message=f"Failed to upload file {file.filename}: {str(e)}",
                    severity_level="medium",
                    component="upload_router",
                    session_id=session_id,
                    context_data={
                        "task_id": task_id,
                        "filename": file.filename,
                        "error": str(e)
                    }
                )

                # Re-raise the exception
                raise

    return {
        "task_id": task_id,
        "files": results,
        "enabled_pii_categories": pii_categories,
        "pii_selection_summary": f"{len(pii_categories)} of 6 optional PII types selected for masking"
    }
