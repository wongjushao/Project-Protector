from pdf2image import convert_from_path
import os
from PIL import Image
from app.services.ocr_jpeg import mask_sensitive_text
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

def pdf_to_images(pdf_path, output_folder, dpi=100, first_page=None, last_page=None):
    poppler_path = os.path.abspath("C:\\Project Protector\\env\\Lib\\poppler-24.08.0\\Library\\bin")
    os.makedirs(output_folder, exist_ok=True)

    try:
        pages = convert_from_path(
            pdf_path,
            dpi=dpi,
            poppler_path=poppler_path,
            first_page=first_page,
            last_page=last_page,
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

def images_to_pdf(image_folder, output_pdf_path):
    def extract_page_number(filename):
        # 提取 page_1_masked.png 中的 1 作为排序键
        match = re.search(r'page_(\d+)_masked\.(jpg|jpeg|png)$', filename, re.IGNORECASE)
        return int(match.group(1)) if match else float('inf')  # 未匹配的文件排到最后

    # 仅包含 *_masked 的文件
    image_files = sorted([
        os.path.join(image_folder, f)
        for f in os.listdir(image_folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png")) and '_masked' in f
    ], key=lambda f: extract_page_number(f))

    if not image_files:
        raise ValueError("No masked images found to convert to PDF")

    image_list = [Image.open(img).convert("RGB") for img in image_files]
    image_list[0].save(output_pdf_path, save_all=True, append_images=image_list[1:])
    print(f"✅ 合成 PDF 完成: {output_pdf_path}")
    return output_pdf_path

def process_image_with_mask(image_path, reader, key_path, enabled_pii_categories=None):
    print(f"[THREAD] 处理：{image_path}")
    # 获取 JSON 路径：将 .key 扩展名替换为 .json
    base_path, _ = os.path.splitext(key_path)
    json_path = base_path + ".json"
    return mask_sensitive_text(
        image_path=image_path,
        key_path=key_path,
        reader=reader,
        output_json_path=json_path,
        enabled_pii_categories=enabled_pii_categories
    )

def process_pdf_images_multithread(image_dir, reader, key_path="aes_key.key", max_workers=4, enabled_pii_categories=None):
    image_paths = [
        os.path.join(image_dir, f) for f in sorted(os.listdir(image_dir))
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    print(f"[INFO] 开始多线程处理 {len(image_paths)} 个图片页面")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_image_with_mask, path, reader, key_path, enabled_pii_categories): path
            for path in image_paths
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                future.result()
                print(f"[SUCCESS] 页面处理完成: {os.path.basename(path)}")
            except Exception as e:
                print(f"❌ 处理失败 {path}: {e}")
