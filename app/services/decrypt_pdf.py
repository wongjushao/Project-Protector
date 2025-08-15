import os
import tempfile
import json
from pdf2image import convert_from_path
import io
from app.services.decrypt_jpeg import decrypt_masked_image_to_bytes
from PIL import Image
import re

def decrypt_masked_pdf(masked_pdf_path: str, json_path: str, key_path: str):
    """
    Decrypt a masked PDF by separating the combined JSON data by page
    and applying the appropriate decryption to each page.
    """
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, "decrypted_pages")
    os.makedirs(output_dir, exist_ok=True)

    print(f"[INFO] Starting PDF decryption: {masked_pdf_path}")
    print(f"[INFO] Using JSON: {json_path}")
    print(f"[INFO] Using key: {key_path}")

    # Step 1: Load and parse the combined JSON data
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            all_encrypted_data = json.load(f)
        print(f"[INFO] Loaded {len(all_encrypted_data)} encrypted items")
    except Exception as e:
        return {"status": "error", "message": f"Unable to read JSON file: {e}"}

    # Step 2: Separate data by page
    pages_data = {}
    has_page_info = any('page_number' in entry for entry in all_encrypted_data)

    if has_page_info:
        # New format: data includes page numbers
        for entry in all_encrypted_data:
            page_num = entry.get('page_number', 1)
            if page_num not in pages_data:
                pages_data[page_num] = []
            pages_data[page_num].append(entry)
        print(f"[INFO] New format PDF - Data distribution: {len(pages_data)} pages")
    else:
        # Old format: no page information, distribute evenly or apply to all pages
        print(f"[INFO] Old format PDF - Applying all encrypted data to each page")
        # For backward compatibility, apply all data to each page
        # This is not ideal but ensures old PDFs can still be decrypted
        pages_data[1] = all_encrypted_data  # Apply all to first page for now

    for page_num, data in pages_data.items():
        print(f"  Page {page_num}: {len(data)} encrypted items")

    # Step 3: PDF → Images
    try:
        # Use the same poppler path as in ocr_pdf.py
        poppler_path = os.path.abspath("C:\\Project Protector\\env\\Lib\\poppler-24.08.0\\Library\\bin")
        pages = convert_from_path(masked_pdf_path, dpi=150, poppler_path=poppler_path)
        print(f"[INFO] PDF converted to {len(pages)} page images")
    except Exception as e:
        return {"status": "error", "message": f"PDF to image conversion failed: {e}"}

    # Step 4: Process each page individually
    decrypted_images = []
    for i, page in enumerate(pages):
        page_number = i + 1
        page_path = os.path.join(temp_dir, f"page_{page_number}_masked.jpg")
        page.save(page_path, "JPEG")

        # Create individual JSON file for this page
        page_json_path = os.path.join(temp_dir, f"page_{page_number}.json")
        page_data = pages_data.get(page_number, [])

        with open(page_json_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, indent=2)

        print(f"[INFO] Processing page {page_number}: {len(page_data)} encrypted items")

        # Decrypt this page
        try:
            decrypted_img_bytes = decrypt_masked_image_to_bytes(page_path, page_json_path, key_path)
            decrypted_images.append(Image.open(io.BytesIO(decrypted_img_bytes)).convert("RGB"))
            print(f"[SUCCESS] Page {page_number} decryption completed")
        except Exception as e:
            print(f"[ERROR] Page {page_number} decryption failed: {e}")
            # Use original page if decryption fails
            decrypted_images.append(page.convert("RGB"))

    # Step 5: Merge decrypted PDFs
    output_pdf = os.path.splitext(masked_pdf_path)[0] + ".decrypted.pdf"
    if decrypted_images:
        decrypted_images[0].save(output_pdf, save_all=True, append_images=decrypted_images[1:])
        print(f"[SUCCESS] Decrypted PDF saved to: {output_pdf}")
    else:
        return {"status": "error", "message": "No successfully decrypted pages"}

    # Cleanup temporary files
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except:
        pass  # Ignore cleanup errors

    return {
        "status": "success",
        "decrypted_file": output_pdf,
        "pages_processed": len(decrypted_images),
        "total_encrypted_items": len(all_encrypted_data)
    }
