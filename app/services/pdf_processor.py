import os
from app.services.ocr_jpeg import mask_sensitive_text
from app.services.ocr_pdf import pdf_to_images, process_pdf_images_multithread, images_to_pdf
import easyocr
import uuid

def run_pdf_processing(pdf_path: str):
    base_output = os.path.splitext(pdf_path)[0]
    image_output_folder = base_output + "_pages"
    masked_output_pdf = base_output + "_masked.pdf"
    key_file_path = base_output + "_aes.key"

    reader = easyocr.Reader(['en', 'ms'], gpu=False)

    # Step 1: PDF ➜ 图片
    image_paths = pdf_to_images(pdf_path, image_output_folder)

    # Step 2: 遮罩处理
    process_pdf_images_multithread(image_output_folder, reader, key_path=key_file_path)

    # Step 3: 图片 ➜ PDF
    final_pdf_path = images_to_pdf(image_output_folder, masked_output_pdf)

    return {
        "masked_pdf": final_pdf_path,
        "key_file": key_file_path,
    }
