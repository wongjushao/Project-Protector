# app/routers/process_router.py
from fastapi import APIRouter, HTTPException, Request
import os, json, time, uuid

from app.services.image_processor import run_ocr_jpeg
from app.services.pdf_processor import run_pdf_processing
from app.services.text_processor import run_text_processing
from app.services.docx_processor import run_docx_processing
from app.services.xlsx_processor import run_xlsx_processing

# Optional audit service import
try:
    from app.services.audit_service import AuditService
    AUDIT_ENABLED = True
    print("✅ Audit service available in process router")
except ImportError:
    AUDIT_ENABLED = False
    print("⚠️ Audit service not available in process router - using basic logging")

router = APIRouter()
UPLOAD_DIR = "uploads"

@router.post("/process/{task_id}")
async def process_task(task_id: str, request: Request):
    start_time = time.time()
    base_url = str(request.base_url)
    task_path = os.path.join(UPLOAD_DIR, task_id)

    # Get client information for audit
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    session_id = request.cookies.get("audit_session_id", str(uuid.uuid4()))

    if not os.path.exists(task_path):
        raise HTTPException(status_code=404, detail="Task not found")

    # Load PII configuration
    config_path = os.path.join(task_path, "pii_config.json")
    enabled_pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']  # Default

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                enabled_pii_categories = config.get('enabled_pii_categories', enabled_pii_categories)
        except Exception as e:
            print(f"[WARN] Failed to load PII config: {e}, using defaults")

    print(f"[INFO] Processing task {task_id} with PII categories: {enabled_pii_categories}")

    results = []
    total_pii_found = 0
    total_pii_masked = 0

    for filename in os.listdir(task_path):
        file_path = os.path.join(task_path, filename)
        ext = os.path.splitext(filename)[1].lower()

        file_start_time = time.time()

        try:
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                result = run_ocr_jpeg(file_path, enabled_pii_categories)
                if "masked_image" in result:
                    result["masked_image"] = base_url + result["masked_image"].replace("\\", "/")
                if "json_output" in result:
                    result["json_output"] = base_url + result["json_output"].replace("\\", "/")
                if "key_file" in result:
                    result["key_file"] = base_url + result["key_file"].replace("\\", "/")
            elif ext in [".pdf"]:
                result = run_pdf_processing(file_path, enabled_pii_categories)
                # Convert relative paths to full URLs for PDF files
                if isinstance(result, dict) and result.get("status") == "success":
                    if "masked_pdf" in result:
                        result["masked_pdf"] = base_url + result["masked_pdf"].replace("\\", "/")
                    if "json_output" in result:
                        result["json_output"] = base_url + result["json_output"].replace("\\", "/")
                    if "key_file" in result:
                        result["key_file"] = base_url + result["key_file"].replace("\\", "/")
            elif ext in [".txt", ".csv"]:
                result = run_text_processing(file_path, enabled_pii_categories)
            elif ext in [".docx"]:
                result = run_docx_processing(file_path, enabled_pii_categories)
            elif ext in [".xlsx", ".xls"]:
                result = run_xlsx_processing(file_path, enabled_pii_categories)
            else:
                result = {"error": f"Unsupported file type: {ext}"}

        except Exception as e:
            result = {"error": str(e)}

        # Calculate file processing time
        file_processing_time = time.time() - file_start_time

        # Extract PII statistics from result if available
        file_pii_found = result.get("pii_found", 0) if isinstance(result, dict) else 0
        file_pii_masked = result.get("pii_masked", 0) if isinstance(result, dict) else 0
        total_pii_found += file_pii_found
        total_pii_masked += file_pii_masked

        # Simple audit logging (non-blocking)
        try:
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            status = "success" if "error" not in result else "error"

            print(f"[AUDIT] File processed: {filename}")
            print(f"[AUDIT]   - Task ID: {task_id}")
            print(f"[AUDIT]   - Size: {file_size} bytes")
            print(f"[AUDIT]   - Processing time: {file_processing_time:.2f}s")
            print(f"[AUDIT]   - PII found: {file_pii_found}, PII masked: {file_pii_masked}")
            print(f"[AUDIT]   - Status: {status}")
            print(f"[AUDIT]   - Enabled PII categories: {enabled_pii_categories}")

            # Try advanced audit logging if available
            if AUDIT_ENABLED:
                try:
                    with AuditService() as audit:
                        file_op_id = audit.log_file_operation(
                            session_id=session_id,
                            task_id=task_id,
                            operation_type="process",
                            file_name=filename,
                            file_type=ext,
                            file_size=file_size,
                            enabled_pii_categories=enabled_pii_categories,
                            ip_address=client_ip,
                            user_agent=user_agent,
                            processing_time=file_processing_time,
                            status=status,
                            error_message=result.get("error") if "error" in result else None
                        )
                        print(f"[AUDIT] Advanced logging successful for {filename}")
                except Exception as audit_error:
                    print(f"[AUDIT] Advanced logging failed: {audit_error}")

        except Exception as e:
            print(f"[AUDIT] Basic logging failed: {e}")

        results.append({
            "filename": filename,
            "result": result
        })

    # Log overall processing completion
    total_processing_time = time.time() - start_time

    print(f"[AUDIT] Task completed: {task_id}")
    print(f"[AUDIT]   - Files processed: {len(results)}")
    print(f"[AUDIT]   - Total PII found: {total_pii_found}")
    print(f"[AUDIT]   - Total PII masked: {total_pii_masked}")
    print(f"[AUDIT]   - Total processing time: {total_processing_time:.2f}s")
    print(f"[AUDIT]   - Enabled PII categories: {enabled_pii_categories}")

    # Try advanced audit logging if available
    if AUDIT_ENABLED:
        try:
            with AuditService() as audit:
                audit.log_system_event(
                    event_type="info",
                    event_category="processing",
                    event_name="task_completed",
                    event_message=f"Task {task_id} completed processing {len(results)} files",
                    severity_level="info",
                    component="process_router",
                    session_id=session_id,
                    context_data={
                        "task_id": task_id,
                        "files_processed": len(results),
                        "total_pii_found": total_pii_found,
                        "total_pii_masked": total_pii_masked,
                        "processing_time": total_processing_time,
                        "enabled_pii_categories": enabled_pii_categories
                    }
                )
                print(f"[AUDIT] Advanced task logging successful")
        except Exception as audit_error:
            print(f"[AUDIT] Advanced task logging failed: {audit_error}")

    return {
        "task_id": task_id,
        "processed": results
    }
