# OCR/ocr_jpeg.py
from cryptography.fernet import Fernet
import json
import easyocr
import cv2
from matplotlib import image
import numpy as np
import os
import sys
import base64

from app.services.pii_main import extract_all_pii, extract_from_dictionaries
from app.resources.dictionaries import NAMES, ORG_NAMES, RACES, STATUS

def mask_region_improved(image, x_min, y_min, x_max, y_max):
    """
    改进的遮罩方法，使用渐变边缘减少硬边缘效应
    """
    # 创建基本的黑色矩形遮罩
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

    # 可选：添加轻微的模糊边缘来减少锐利边缘
    # 这有助于在解密时更好地融合
    border_width = 1
    if border_width > 0:
        # 在遮罩区域周围添加轻微的模糊
        x_start = max(0, x_min - border_width)
        y_start = max(0, y_min - border_width)
        x_end = min(image.shape[1], x_max + border_width)
        y_end = min(image.shape[0], y_max + border_width)

        # 获取边界区域
        border_region = image[y_start:y_end, x_start:x_end].copy()

        # 对边界区域应用轻微模糊
        if border_region.size > 0:
            blurred = cv2.GaussianBlur(border_region, (3, 3), 0.5)
            image[y_start:y_end, x_start:x_end] = blurred

            # 重新绘制核心黑色区域
            cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

# === 加密/解密 ===
def generate_key():
    return Fernet.generate_key()

def encrypt_text(text, fernet):
    return fernet.encrypt(text.encode()).decode()

# === bbox IOU 判定（去重用）===
def iou(bbox1, bbox2):
    x1_min = min(p[0] for p in bbox1)
    x1_max = max(p[0] for p in bbox1)
    y1_min = min(p[1] for p in bbox1)
    y1_max = max(p[1] for p in bbox1)

    x2_min = min(p[0] for p in bbox2)
    x2_max = max(p[0] for p in bbox2)
    y2_min = min(p[1] for p in bbox2)
    y2_max = max(p[1] for p in bbox2)

    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)

    if inter_x_min >= inter_x_max or inter_y_min >= inter_y_max:
        return 0.0

    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = area1 + area2 - inter_area
    return inter_area / union_area

def load_or_generate_valid_key(key_path):
    try:
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                key = f.read()
            Fernet(key)  # 验证是否是有效密钥
        else:
            raise ValueError("Key file does not exist")
    except Exception as e:
        print(f"[WARN] 无效或损坏的密钥（或路径冲突）: {e}")
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
    return key


# === 主函数：遮罩 + 加密 ===
def mask_sensitive_text(image_path, key_path, output_json_path=None, output_image_path=None, reader=None, keywords=None, enabled_pii_categories=None):
    from easyocr import Reader
    if reader is None:
        reader = Reader(['en', 'ms'], gpu=True)
    results = reader.readtext(image_path)
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"无法读取图像（可能尚未写入完成或路径错误）: {image_path}")
    encrypted_data = []

    # === Step 1: 按 y 位置对文本行进行分组（模拟“行”）===
    lines = []
    for bbox, text, confidence in results:
        y_coords = [point[1] for point in bbox]
        center_y = (min(y_coords) + max(y_coords)) / 2
        lines.append({
            'text': text,
            'bbox': bbox,
            'confidence': confidence,
            'center_y': center_y
        })

    # 排序并分组为“行”
    lines.sort(key=lambda x: x['center_y'])
    grouped_lines = []
    current_group = []
    threshold = 25  # 行间距阈值（可根据图像分辨率调整）

    for line in lines:
        if not current_group:
            current_group.append(line)
        else:
            prev_y = current_group[-1]['center_y']
            if abs(line['center_y'] - prev_y) < threshold:
                current_group.append(line)
            else:
                grouped_lines.append(current_group)
                current_group = [line]
    if current_group:
        grouped_lines.append(current_group)

    # === Step 2: 构造每行的完整文本 ===
    full_text_lines = []
    for group in grouped_lines:
        # 按 x 排序一行内的文本
        group_sorted = sorted(group, key=lambda x: min(p[0] for p in x['bbox']))
        line_text = " ".join(item['text'] for item in group_sorted)
        full_text_lines.append(line_text)

    full_text = "\n".join(full_text_lines)
    print(f"[INFO] 完整文本：\n{full_text}\n")

    # === Step 3: 提取 PII（支持选择性类别过滤）===
    # Default to all selectable categories if none specified
    if enabled_pii_categories is None:
        enabled_pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']

    print(f"[INFO] 启用的PII类别: {enabled_pii_categories}")

    # 使用选择性PII提取
    pii_entries = extract_all_pii(full_text, enabled_pii_categories)
    print(f"[INFO] 提取到 {len(pii_entries)} 个PII项（包含选择性过滤）")

    # ✅ 业务级忽略词（只在图像遮罩场景中忽略）
    IGNORE_WORDS = {
        "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
        "warganegara", "lelaki", "perempuan", "bujang", "kawin",
        "lel", "per", "male", "female", "citizen", "not citizen",
        "id", "no", "identification", "type", "my", "k", "your", "name", "address", "phone", "email", "bank", "account", "number",
        "passport", "ic", "ic number", "ic no", "ic no.", "Account", "account no", "account number", "bank account", "bank account no", "bank account number",
        "bank", "bank name", "bank account name", "bank account holder", "bank account holder name", "bank account holder no",
        "bank account holder id", "bank account holder ic", "bank account holder passport", "bank account holder mykad", "bank account holder identity card",
        "bank account holder identity", "bank account holder identification", "bank account holder type",
        "bank account holder name", "bank account holder address", "bank account holder phone", "bank account holder email",
        "bank account holder dob", "bank account holder date of birth", "bank account holder", "Account Type", "Account No", "Account Number",
        "Bank Statement", "Bank Account Statement", "Bank Account Statement No", "Bank Account Statement Number",
        "Bank Account Statement Type", "Bank Account Statement Holder", "Bank Account Statement Holder Name", "Bank Statement Example", "Four Bank"
    }

    # ✅ 马来西亚地点白名单（用于 LOC 过滤）
    MALAYSIA_LOCATIONS = {
    }

    # 过滤和处理PII结果
    filtered_pii = []
    selectable_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']

    print("[INFO] 处理PII检测结果：")
    for label, value in pii_entries:
        clean_val = value.strip().lower()
        original_val = value.strip()

        # 跳过空值
        if not original_val:
            continue

        # 忽略通用非敏感词
        if any(ignore in clean_val for ignore in IGNORE_WORDS):
            print(f"[SKIP] 忽略非敏感词: {original_val}")
            continue

        # 选择性PII类别：只有在enabled_categories中的才会被遮罩
        if label in selectable_categories:
            if label in enabled_pii_categories:
                filtered_pii.append((label, original_val))
                print(f"[MASK] 选择性PII - {label}: {original_val}")
            else:
                print(f"[SKIP] 选择性PII未启用 - {label}: {original_val}")
        else:
            # 非选择性PII（如IC、EMAIL、PHONE等）：始终遮罩
            filtered_pii.append((label, original_val))
            print(f"[MASK] 非选择性PII - {label}: {original_val}")

    # 更新 keywords
    keywords = list(set(value for _, value in filtered_pii))
    print(f"[INFO] 最终将遮罩 {len(keywords)} 个关键词")

    # === Step 4: 加载或生成密钥 ===
    key = load_or_generate_valid_key(key_path)
    fernet = Fernet(key)

    seen = []

    # === Step 5: 遍历原始 OCR 结果，匹配关键词（支持跨行关键词）===
    for bbox, text, confidence in results:
        matched = False
        for keyword in keywords:
            # 检查关键词是否“跨行”，但当前行包含其一部分
            if keyword.lower() in text.lower():
                matched = True
                break
            # 或者：当前文本是关键词的子串（前缀/后缀），且附近有另一部分？
            if (keyword.lower().startswith(text.lower()) or keyword.lower().endswith(text.lower())) and len(text) > 3:
                # 启用“跨行合并检测”（进阶可做，这里先简单处理）
                pass  # 可扩展：搜索邻近框拼接

        if not matched:
            continue

        # 去重：使用 IOU 判断是否已处理
        duplicate = False
        for s in seen:
            if iou(bbox, s["bbox"]) > 0.85 and text.lower() == s["text"].lower():
                duplicate = True
                break
        if duplicate:
            continue
        seen.append({"bbox": bbox, "text": text})

        # === 遮罩 + 加密 ===
        x_coords = [int(p[0]) for p in bbox]
        y_coords = [int(p[1]) for p in bbox]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        roi = image[y_min:y_max, x_min:x_max]

        success, roi_encoded = cv2.imencode('.png', roi)
        if not success:
            print(f"[WARN] 区域编码失败，跳过: {text}")
            continue

        roi_base64 = base64.b64encode(roi_encoded).decode('utf-8')
        # 使用改进的遮罩方法，避免硬边缘
        mask_region_improved(image, x_min, y_min, x_max, y_max)
        cipher = encrypt_text(text, fernet)
        encrypted_data.append({
            "cipher": cipher,
            "bbox": [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]],
            "confidence": confidence,
            "original_image_base64": roi_base64
        })
        print(f"[MASKED + ENCRYPTED] '{text}' -> {cipher[:12]}...")

    # === 保存图像和 JSON ===
    if output_image_path is None:
        name, ext = os.path.splitext(image_path)
        output_image_path = f"{name}_masked{ext}"
    cv2.imwrite(output_image_path, image)
    print(f"✅ 遮罩图像保存至：{output_image_path}")

    json_path = output_json_path or output_image_path.replace(ext, ".json")
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(encrypted_data, f, indent=2)
    print(f"✅ 加密数据保存至：{json_path}")

    # === 输出处理摘要 ===
    print(f"\n📊 图像处理摘要:")
    print(f"   - 启用PII类别: {enabled_pii_categories}")
    print(f"   - 检测到PII项: {len(pii_entries)}")
    print(f"   - 实际遮罩项: {len(encrypted_data)}")
    print(f"   - 遮罩图像: {output_image_path}")
    print(f"   - 加密数据: {json_path}")
    print(f"   - 密钥文件: {key_path}")

    return output_image_path, json_path, key_path
