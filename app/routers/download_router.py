# app/routers/download_router.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
import os
import zipfile
from pathlib import Path
import uuid

router = APIRouter()

# Configuration
UPLOADS_DIR = "uploads"
DOWNLOADS_DIR = "downloads"

# Create downloads directory if it doesn't exist
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

@router.get("/download/{task_id}")
async def download_task_files(task_id: str):
    """
    Download all files for a given task ID as a ZIP file
    """
    print(f"[INFO] Download request received for task: {task_id}")

    # Validate task_id format (basic validation)
    if not task_id or len(task_id) < 5:
        print(f"[ERROR] Invalid task ID format: {task_id}")
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    # Check if task directory exists
    task_dir = os.path.join(UPLOADS_DIR, task_id)
    print(f"[INFO] Looking for task directory: {task_dir}")

    if not os.path.exists(task_dir):
        print(f"[ERROR] Task directory not found: {task_dir}")
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    print(f"[INFO] Task directory found, creating ZIP file...")
    
    # Create zip file
    zip_filename = f"{task_id}_{uuid.uuid4().hex[:8]}.zip"
    zip_filepath = os.path.join(DOWNLOADS_DIR, zip_filename)
    
    try:
        # Create zip file containing all task files
        files_added = 0
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(task_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Preserve directory structure in zip
                    arcname = os.path.relpath(file_path, task_dir)
                    zipf.write(file_path, arcname=os.path.join(task_id, arcname))
                    files_added += 1
                    print(f"[INFO] Added file to ZIP: {arcname}")

        print(f"[INFO] ZIP file created with {files_added} files: {zip_filepath}")
        
        # Return the zip file
        return FileResponse(
            path=zip_filepath,
            filename=zip_filename,
            media_type='application/zip',
            headers={"Content-Disposition": f"attachment; filename={task_id}.zip"}
        )
    
    except Exception as e:
        # Clean up zip file if creation failed
        if os.path.exists(zip_filepath):
            os.remove(zip_filepath)
        raise HTTPException(status_code=500, detail=f"Failed to create zip file: {str(e)}")

# Optional: Add endpoint to list available tasks
@router.get("/tasks")
async def list_tasks():
    """
    List all available tasks
    """
    if not os.path.exists(UPLOADS_DIR):
        return []
    
    tasks = []
    for item in os.listdir(UPLOADS_DIR):
        item_path = os.path.join(UPLOADS_DIR, item)
        if os.path.isdir(item_path):
            tasks.append({
                "task_id": item,
                "created": os.path.getctime(item_path) if os.path.exists(item_path) else None
            })
    
    # Sort by creation time (newest first)
    tasks.sort(key=lambda x: x["created"] if x["created"] else 0, reverse=True)
    return tasks