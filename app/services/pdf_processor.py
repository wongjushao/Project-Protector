import os
from app.services.ocr_jpeg import mask_sensitive_text
from app.services.ocr_pdf import pdf_to_images, process_pdf_images_multithread, images_to_pdf
import easyocr
import uuid

def run_pdf_processing(pdf_path: str, enabled_pii_categories=None):
    """
    Process PDF file with PII detection, masking, and ignore words filtering.

    Args:
        pdf_path (str): Path to the input PDF file
        enabled_pii_categories (list): List of PII categories to mask (e.g., ['NAMES', 'RACES'])

    Returns:
        dict: Processing results with paths to masked PDF, JSON, and key files
    """
    base_output = os.path.splitext(pdf_path)[0]
    image_output_folder = base_output + "_pages"
    masked_output_pdf = base_output + "_masked.pdf"
    key_file_path = base_output + ".key"  # Use consistent naming with other processors
    json_output_path = base_output + "_masked.json"

    # Default to all selectable categories if none specified
    if enabled_pii_categories is None:
        enabled_pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']

    print(f"[INFO] PDF处理开始: {pdf_path}")
    print(f"[INFO] 启用的PII类别: {enabled_pii_categories}")

    reader = easyocr.Reader(['en', 'ms'], gpu=False)

    try:
        # Step 1: PDF ➜ 图片
        print("[INFO] Step 1: 转换PDF为图片...")
        image_paths = pdf_to_images(pdf_path, image_output_folder)
        if not image_paths:
            return {
                "status": "error",
                "message": "PDF转换为图片失败"
            }

        # Step 2: 遮罩处理（传递PII类别配置）
        print("[INFO] Step 2: 处理图片并应用PII遮罩...")
        process_pdf_images_multithread(
            image_output_folder,
            reader,
            key_path=key_file_path,
            enabled_pii_categories=enabled_pii_categories
        )

        # Step 3: 图片 ➜ PDF
        print("[INFO] Step 3: 合成遮罩后的PDF...")
        final_pdf_path = images_to_pdf(image_output_folder, masked_output_pdf)

        # Convert paths to relative URLs for serving
        base_path = os.path.dirname(pdf_path)
        relative_base = base_path.replace("uploads", "/uploads").replace("\\", "/")

        result = {
            "status": "success",
            "masked_pdf": f"{relative_base}/{os.path.basename(final_pdf_path)}",
            "json_output": f"{relative_base}/{os.path.basename(json_output_path)}",
            "key_file": f"{relative_base}/{os.path.basename(key_file_path)}",
            "pii_categories_used": enabled_pii_categories,
            "pages_processed": len(image_paths)
        }

        print(f"[SUCCESS] PDF处理完成: {len(image_paths)} 页已处理")
        return result

    except Exception as e:
        print(f"[ERROR] PDF处理失败: {e}")
        return {
            "status": "error",
            "message": f"PDF处理失败: {str(e)}"
        }
