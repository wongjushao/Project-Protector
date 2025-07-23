from pdf2image import convert_from_path
import os
from app.services.ocr_jpeg import mask_sensitive_text
from concurrent.futures import ThreadPoolExecutor, as_completed
import easyocr

def pdf_to_images(pdf_path, output_folder, dpi=100):
    poppler_path = os.path.abspath("../env/Lib/poppler-24.08.0/Library/bin")
    os.makedirs(output_folder, exist_ok=True)

    try:
        pages = convert_from_path(
            pdf_path,
            dpi=dpi,
            poppler_path=poppler_path,
            first_page=1,
        )
    except Exception as e:
        print(f"❌ PDF 转图片失败: {e}")
        return []

    image_paths = []
    for i, page in enumerate(pages):
        image_path = os.path.join(output_folder, f"page_{i+1}.jpg")
        page.save(image_path, "JPEG")
        image_paths.append(image_path)
        print(f"✅ 已保存: {image_path}")

    return image_paths


def process_pdf_images(image_dir, reader, key_path="aes_key.key"):
    for filename in sorted(os.listdir(image_dir)):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            image_path = os.path.join(image_dir, filename)
            print(f"\n=== 处理图像: {image_path} ===")
            mask_sensitive_text(image_path, key_path=key_path, reader=reader)

def process_image_with_mask(image_path, reader, key_path):
    print(f"[THREAD] 处理：{image_path}")
    return mask_sensitive_text(image_path, key_path=key_path, reader=reader)

def process_pdf_images_multithread(image_dir, reader, key_path="aes_key.key", max_workers=4):
    image_paths = [
        os.path.join(image_dir, f) for f in sorted(os.listdir(image_dir))
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_image_with_mask, path, reader, key_path): path
            for path in image_paths
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"❌ 处理失败 {path}: {e}")

if __name__ == "__main__":
    test_pdf = "../public_bank.pdf"
    output_dir = "pdf_pages_output"

    pdf_to_images(test_pdf, output_dir)

    print("\n🚀 正在加载 OCR 引擎...")
    reader = easyocr.Reader(['en', 'ms'], gpu=False)
    print("✅ OCR 引擎加载完成")

    process_pdf_images_multithread(output_dir, reader=reader, max_workers=4)
