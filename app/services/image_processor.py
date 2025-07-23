from app.services.ocr_jpeg import mask_sensitive_text

def run_ocr_jpeg(image_path: str):
    try:
        key_path = image_path.replace(".jpg", ".key")  # 或其他逻辑生成
        masked_img, json_path, key_file = mask_sensitive_text(
            image_path=image_path,
            key_path=key_path
        )
        return {
            "status": "success",
            "masked_image": masked_img,
            "json_output": json_path,
            "key_file": key_file
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
