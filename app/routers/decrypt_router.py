from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import shutil
import tempfile
import os
import io
from app.services.decrypt_text import decrypt_masked_file
from app.services.decrypt_jpeg import decrypt_masked_image_to_bytes
from app.services.decrypt_pdf import decrypt_masked_pdf
from app.services.decrypt_docx import decrypt_masked_docx

router = APIRouter()

@router.post("/decrypt")
async def decrypt_file(
    masked_file: UploadFile = File(...),
    json_file: UploadFile = File(...),
    key_file: UploadFile = File(...)
):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            masked_path = os.path.join(tmpdir, masked_file.filename)
            json_path = os.path.join(tmpdir, json_file.filename)
            key_path = os.path.join(tmpdir, key_file.filename)

            for src, dst in [
                (masked_file, masked_path),
                (json_file, json_path),
                (key_file, key_path)
            ]:
                with open(dst, "wb") as f:
                    shutil.copyfileobj(src.file, f)

            ext = os.path.splitext(masked_path)[1].lower()

            if ext in [".jpg", ".jpeg", ".png"]:
                # 处理图像文件
                decrypted_bytes = decrypt_masked_image_to_bytes(masked_path, json_path, key_path)
                return StreamingResponse(
                    io.BytesIO(decrypted_bytes),
                    media_type="image/png",
                    headers={
                        "Content-Disposition": f"attachment; filename=decrypted_{os.path.splitext(masked_file.filename)[0]}.png"
                    }
                )
            elif ext in [".txt", ".csv"]:
                text_result = decrypt_masked_file(masked_path, json_path, key_path)
                
                # Handle return file path case
                if isinstance(text_result, dict):
                    if text_result.get("status") == "success":
                        decrypted_file_path = text_result.get("decrypted_file")
                        if decrypted_file_path and os.path.exists(decrypted_file_path):
                            # Read file content and return
                            with open(decrypted_file_path, "rb") as f:
                                file_content = f.read()
                            
                            # Determine media type
                            media_type = "text/plain" if ext == ".txt" else "text/csv"
                            
                            return StreamingResponse(
                                io.BytesIO(file_content),
                                media_type=media_type,
                                headers={
                                    "Content-Disposition": f"attachment; filename=decrypted_{masked_file.filename}"
                                }
                            )
                        else:
                            raise HTTPException(status_code=500, detail="解密文件未找到")
                    else:
                        raise HTTPException(status_code=500, detail=text_result.get("message", "解密失败"))
                else:
                    # If return is string content
                    content = str(text_result)
                    media_type = "text/plain" if ext == ".txt" else "text/csv"
                    return StreamingResponse(
                        io.StringIO(content),
                        media_type=media_type,
                        headers={
                            "Content-Disposition": f"attachment; filename=decrypted_{masked_file.filename}"
                        }
                    )
            elif ext in [".pdf"]:
                pdf_result = decrypt_masked_pdf(masked_path, json_path, key_path)
                if isinstance(pdf_result, dict):
                    if pdf_result.get("status") == "success":
                        # Use standardized key name
                        decrypted_file_path = pdf_result.get("decrypted_file")
                        if decrypted_file_path and os.path.exists(decrypted_file_path):
                            with open(decrypted_file_path, "rb") as f:
                                file_content = f.read()
                            return StreamingResponse(
                                io.BytesIO(file_content),
                                media_type="application/pdf",
                                headers={
                                    "Content-Disposition": f"attachment; filename=decrypted_{masked_file.filename}"
                                }
                            )
                        else:
                            raise HTTPException(status_code=500, detail="PDF解密文件未找到")
                    else:
                        raise HTTPException(status_code=500, detail=pdf_result.get("message", "PDF解密失败"))
                else:
                    pdf_bytes = pdf_result
                    if isinstance(pdf_bytes, str):
                        import base64
                        pdf_bytes = base64.b64decode(pdf_bytes)
                    return StreamingResponse(
                        io.BytesIO(pdf_bytes),
                        media_type="application/pdf",
                        headers={
                            "Content-Disposition": f"attachment; filename=decrypted_{masked_file.filename}"
                        }
                    )
            elif ext in [".docx"]:
                docx_result = decrypt_masked_docx(masked_path, json_path, key_path)
                if isinstance(docx_result, dict):
                    if docx_result.get("status") == "success":
                        # Use standardized key name
                        decrypted_file_path = docx_result.get("decrypted_file")
                        if decrypted_file_path and os.path.exists(decrypted_file_path):
                            with open(decrypted_file_path, "rb") as f:
                                file_content = f.read()
                            return StreamingResponse(
                                io.BytesIO(file_content),
                                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                headers={
                                    "Content-Disposition": f"attachment; filename=decrypted_{masked_file.filename}"
                                }
                            )
                        else:
                            raise HTTPException(status_code=500, detail="DOCX解密文件未找到")
                    else:
                        raise HTTPException(status_code=500, detail=docx_result.get("message", "DOCX解密失败"))
                else:
                    docx_bytes = docx_result
                    if isinstance(docx_bytes, str):
                        import base64
                        docx_bytes = base64.b64decode(docx_bytes)
                    return StreamingResponse(
                        io.BytesIO(docx_bytes),
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={
                            "Content-Disposition": f"attachment; filename=decrypted_{masked_file.filename}"
                        }
                    )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解密失败: {str(e)}")