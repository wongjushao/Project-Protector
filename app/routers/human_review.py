# app/routers/human_review.py
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Any
import os
import json
import uuid
import time
from pydantic import BaseModel

# Optional audit service import
try:
    from app.services.audit_service import AuditService
    AUDIT_ENABLED = True
except ImportError:
    AUDIT_ENABLED = False

router = APIRouter()
templates = Jinja2Templates(directory="templates")
UPLOAD_DIR = "uploads"

class ManualSelection(BaseModel):
    x: int
    y: int
    width: int
    height: int
    selection_type: str = "rectangle"

class ManualReviewRequest(BaseModel):
    task_id: str
    filename: str
    selections: List[ManualSelection]

@router.get("/human-review/{task_id}/{filename}", response_class=HTMLResponse)
async def human_review_page(request: Request, task_id: str, filename: str):
    """Serve the human review page for JPEG/JPG files"""
    try:
        # Verify task exists
        task_path = os.path.join(UPLOAD_DIR, task_id)
        if not os.path.exists(task_path):
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Verify file exists and is JPEG/JPG
        file_path = os.path.join(task_path, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check file extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg"]:
            raise HTTPException(status_code=400, detail="Human review only available for JPEG/JPG files")
        
        # Get base URL for serving files
        base_url = str(request.base_url).rstrip('/')
        
        # Construct file URLs
        original_image_url = f"{base_url}/uploads/{task_id}/{filename}"
        
        # Look for existing masked image
        name, ext = os.path.splitext(filename)
        masked_filename = f"{name}_masked{ext}"
        masked_image_path = os.path.join(task_path, masked_filename)
        
        masked_image_url = None
        if os.path.exists(masked_image_path):
            masked_image_url = f"{base_url}/uploads/{task_id}/{masked_filename}"
        
        # Log human review access
        if AUDIT_ENABLED:
            try:
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent", "")
                session_id = request.cookies.get("audit_session_id", str(uuid.uuid4()))
                
                with AuditService() as audit:
                    audit.log_user_action(
                        session_id=session_id,
                        action_type="page_visit",
                        action_name="human_review_access",
                        action_details={"task_id": task_id, "filename": filename},
                        page_url=str(request.url),
                        http_method="GET",
                        endpoint=f"/human-review/{task_id}/{filename}",
                        ip_address=client_ip,
                        user_agent=user_agent
                    )
            except Exception as e:
                print(f"[WARN] Audit logging failed: {e}")
        
        return templates.TemplateResponse("human_review.html", {
            "request": request,
            "task_id": task_id,
            "filename": filename,
            "original_image_url": original_image_url,
            "masked_image_url": masked_image_url
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Human review page error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/api/human-review/process")
async def process_manual_selections(request: Request, review_request: ManualReviewRequest):
    """Process manually selected areas for masking"""
    try:
        task_id = review_request.task_id
        filename = review_request.filename
        selections = review_request.selections

        print(f"[INFO] Processing manual selections for {filename} in task {task_id}")
        print(f"[INFO] Received {len(selections)} manual selections")
        print(f"[DEBUG] Request data type: {type(review_request)}")
        print(f"[DEBUG] Selections type: {type(selections)}")
        if selections:
            print(f"[DEBUG] First selection: {selections[0]}")
            print(f"[DEBUG] First selection type: {type(selections[0])}")

        # Verify task and file exist
        task_path = os.path.join(UPLOAD_DIR, task_id)
        file_path = os.path.join(task_path, filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Check file extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg"]:
            raise HTTPException(status_code=400, detail="Manual review only available for JPEG/JPG files")

        # Process manual selections
        from app.services.manual_masking_service import process_manual_masking

        try:
            output_image_path, output_json_path, key_file_path = process_manual_masking(
                image_path=file_path,
                selections=selections,
                task_id=task_id
            )

            # Get base URL for serving files
            base_url = str(request.base_url).rstrip('/')

            # Convert absolute paths to relative URLs
            base_path = os.path.dirname(file_path)
            relative_base = base_path.replace("uploads", "/uploads").replace("\\", "/")

            result = {
                "status": "success",
                "masked_image": f"{relative_base}/{os.path.basename(output_image_path)}",
                "json_output": f"{relative_base}/{os.path.basename(output_json_path)}",
                "key_file": f"{relative_base}/{os.path.basename(key_file_path)}",
                "areas_masked": len(selections),
                "total_selections": len(selections),
                "manual_review": True
            }

            # Update URLs to be accessible
            result["masked_image"] = base_url + result["masked_image"].replace("\\", "/")
            result["json_output"] = base_url + result["json_output"].replace("\\", "/")
            result["key_file"] = base_url + result["key_file"].replace("\\", "/")

            # Log manual review processing
            if AUDIT_ENABLED:
                try:
                    client_ip = request.client.host if request.client else "unknown"
                    user_agent = request.headers.get("user-agent", "")
                    session_id = request.cookies.get("audit_session_id", str(uuid.uuid4()))

                    with AuditService() as audit:
                        # Log user action
                        audit.log_user_action(
                            session_id=session_id,
                            action_type="manual_review",
                            action_name="manual_masking_applied",
                            action_details={
                                "task_id": task_id,
                                "filename": filename,
                                "selections_count": len(selections),
                                "areas_masked": result.get("areas_masked", 0)
                            },
                            page_url=str(request.url),
                            http_method="POST",
                            endpoint="/api/human-review/process",
                            ip_address=client_ip,
                            user_agent=user_agent
                        )

                        # Log system event
                        audit.log_system_event(
                            event_type="info",
                            event_category="manual_review",
                            event_name="manual_masking_completed",
                            event_message=f"Manual masking applied to {filename} with {len(selections)} selections",
                            severity_level="info",
                            component="human_review_router",
                            session_id=session_id,
                            context_data={
                                "task_id": task_id,
                                "filename": filename,
                                "selections": [{"x": s.x, "y": s.y, "width": s.width, "height": s.height} for s in selections]
                            }
                        )
                except Exception as e:
                    print(f"[WARN] Audit logging failed: {e}")

            areas_masked = result.get("areas_masked", 0)
            total_selections = result.get("total_selections", 0)
            print(f"[SUCCESS] Manual masking completed for {filename}: {areas_masked}/{total_selections} areas processed")

            # Update result message for better user feedback
            result["message"] = f"Successfully processed {areas_masked} out of {total_selections} selected areas"

            return JSONResponse(content=result)

        except Exception as processing_error:
            print(f"[ERROR] Manual masking failed: {processing_error}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(processing_error)}")

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Manual review processing error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/human-review/status/{task_id}/{filename}")
async def get_review_status(task_id: str, filename: str):
    """Get the current status of a file for human review"""
    try:
        task_path = os.path.join(UPLOAD_DIR, task_id)
        file_path = os.path.join(task_path, filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Check if file is eligible for human review
        ext = os.path.splitext(filename)[1].lower()
        eligible = ext in [".jpg", ".jpeg"]

        # Check if masked version exists
        name, ext = os.path.splitext(filename)
        masked_filename = f"{name}_masked{ext}"
        masked_exists = os.path.exists(os.path.join(task_path, masked_filename))

        # Check if manual review has been performed (check for masked.json file)
        manual_review_file = os.path.join(task_path, f"{name}_masked.json")
        manual_review_performed = os.path.exists(manual_review_file)

        return JSONResponse(content={
            "eligible_for_review": eligible,
            "masked_version_exists": masked_exists,
            "manual_review_performed": manual_review_performed,
            "filename": filename,
            "task_id": task_id
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Review status error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
