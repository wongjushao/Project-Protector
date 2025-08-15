import os
import json
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

    print(f"[INFO] PDF processing started: {pdf_path}")
    print(f"[INFO] Enabled PII categories: {enabled_pii_categories}")

    reader = easyocr.Reader(['en', 'ms'], gpu=False)

    try:
        # Step 1: PDF ➜ Images
        print("[INFO] Step 1: Converting PDF to images...")
        image_paths = pdf_to_images(pdf_path, image_output_folder)
        if not image_paths:
            return {
                "status": "error",
                "message": "Failed to convert PDF to images"
            }

        # Step 2: Masking processing (pass PII category configuration)
        print("[INFO] Step 2: Processing images and applying PII masking...")
        process_pdf_images_multithread(
            image_output_folder,
            reader,
            key_path=key_file_path,
            enabled_pii_categories=enabled_pii_categories
        )

        # Step 3: Synthesize masked PDF
        print("[INFO] Step 3: Synthesizing masked PDF...")
        final_pdf_path = images_to_pdf(image_output_folder, masked_output_pdf)

        # Step 4: Merge all page JSON data
        print("[INFO] Step 4: Merging page JSON data...")
        combined_json_data = []
        base_key_path = os.path.splitext(key_file_path)[0]

        for i in range(1, len(image_paths) + 1):
            page_json_path = f"{base_key_path}_page_{i}.json"
            if os.path.exists(page_json_path):
                try:
                    with open(page_json_path, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                    combined_json_data.extend(page_data)
                    print(f"[SUCCESS] Merged page {i}: {len(page_data)} encrypted items")
                except Exception as e:
                    print(f"[WARN] Unable to read page {i} JSON: {e}")

        # Save merged JSON file
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(combined_json_data, f, indent=2)
        print(f"[SUCCESS] JSON merge completed: {len(combined_json_data)} total encrypted items")

        # Convert paths to relative URLs for serving
        base_path = os.path.dirname(pdf_path)
        relative_base = base_path.replace("uploads", "/uploads").replace("\\", "/")

        result = {
            "status": "success",
            "masked_pdf": f"{relative_base}/{os.path.basename(final_pdf_path)}",
            "json_output": f"{relative_base}/{os.path.basename(json_output_path)}",
            "key_file": f"{relative_base}/{os.path.basename(key_file_path)}",
            "pii_categories_used": enabled_pii_categories,
            "pages_processed": len(image_paths),
            "total_encrypted_items": len(combined_json_data)
        }

        print(f"[SUCCESS] PDF processing completed: {len(image_paths)} pages processed")
        return result

    except Exception as e:
        print(f"[ERROR] PDF processing failed: {e}")
        return {
            "status": "error",
            "message": f"PDF processing failed: {str(e)}"
        }
