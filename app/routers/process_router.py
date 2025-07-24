from fastapi import APIRouter, HTTPException, Request
import os

from app.services.image_processor import run_ocr_jpeg
from app.services.pdf_processor import run_pdf_processing

router = APIRouter()
UPLOAD_DIR = "uploads"

@router.post("/process/{task_id}")
async def process_task(task_id: str, request: Request):
    base_url = str(request.base_url)
    task_path = os.path.join(UPLOAD_DIR, task_id)
    
    if not os.path.exists(task_path):
        raise HTTPException(status_code=404, detail="Task not found")

    results = []

    for filename in os.listdir(task_path):
        file_path = os.path.join(task_path, filename)
        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                result = run_ocr_jpeg(file_path)
            elif ext in [".pdf"]:
                result = run_pdf_processing(file_path)
            elif ext in [".txt", ".csv"]:

                # 替换为完整 URL 链接（跨平台兼容）
                if "masked_image" in result:
                    result["masked_image"] = base_url + result["masked_image"].replace("\\", "/")
                if "json_output" in result:
                    result["json_output"] = base_url + result["json_output"].replace("\\", "/")
                if "key_file" in result:
                    result["key_file"] = base_url + result["key_file"].replace("\\", "/")

            else:
                result = {"error": f"Unsupported file type: {ext}"}

        except Exception as e:
            result = {"error": str(e)}

        results.append({
            "filename": filename,
            "result": result
        })

    return {
        "task_id": task_id,
        "processed": results
    }
