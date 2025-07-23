# OCR/ocr_jpeg.py
from cryptography.fernet import Fernet
import json
import easyocr
import cv2
import numpy as np
import os
import sys
import base64

from app.services.pii_main import extract_all_pii

# === 加密/解密 ===
def generate_key():
    return Fernet.generate_key()

def encrypt_text(text, fernet):
    return fernet.encrypt(text.encode()).decode()

def decrypt_text(cipher_text, fernet):
    return fernet.decrypt(cipher_text.encode()).decode()

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
            # 尝试验证合法性
            Fernet(key)
        else:
            raise ValueError("Key file does not exist")
    except Exception as e:
        print(f"[WARN] 无效或损坏的密钥，将重新生成: {e}")
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
    return key
# === 主函数：遮罩 + 加密 ===
def mask_sensitive_text(image_path, key_path, output_json_path=None, output_image_path=None, reader=None, keywords=None):
    from easyocr import Reader
    if reader is None:
        reader = Reader(['en', 'ms'], gpu=True)
    results = reader.readtext(image_path)
    image = cv2.imread(image_path)
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
    # === Step 3: 提取 PII ===
    pii_entries = extract_all_pii(full_text)

    # ✅ 业务级忽略词（只在图像遮罩场景中忽略）
    IGNORE_WORDS = {
        "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
        "warganegara", "lelaki", "perempuan", "bujang", "kawin",
        "lel", "per", "male", "female", "citizen", "not citizen",
        "id", "no", "identification", "type", "my", "k"
    }

    # ✅ 马来西亚地点白名单（用于 LOC 过滤）
    MALAYSIA_LOCATIONS = {
        "KUALA LUMPUR", "PETALING JAYA", "SELANGOR", "JOHOR", "JOHOR BAHRU",
        "PENANG", "GEORGETOWN", "ALOR SETAR", "KELANTAN", "TERENGGANU",
        "MELAKA", "KUCHING", "KOTA KINABALU", "LABUAN", "SABAH", "SARAWAK"
    }

    # 过滤规则
    filtered_pii = []
    print("[INFO] 动态提取关键词如下：")
    for label, value in pii_entries:
        clean_val = value.strip().lower()
        original_val = value.strip()

        # 跳过空值
        if not original_val:
            continue

        # 忽略通用非敏感词
        if clean_val in IGNORE_WORDS:
            continue

        # 如果是 LOC，只保留白名单中的地名
        if label == "LOC":
            words = original_val.upper().split()
            matched = False
            for w in words:
                if w in MALAYSIA_LOCATIONS:
                    filtered_pii.append((label, w))
                    matched = True
            if not matched:
                continue
            continue  # 已处理

        # 其他类型：直接保留（如 IC、姓名等）
        filtered_pii.append((label, original_val))

    # 更新 keywords
    keywords = list(set(value for _, value in filtered_pii))
    print("[INFO] 动态提取关键词如下：")
    for label, value in pii_entries:
        print(f"  - 类型: {label}, 值: {value}")

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
        pts = np.array(bbox, dtype=np.int32)
        cv2.fillPoly(image, [pts], color=(0, 0, 0))
        cipher = encrypt_text(text, fernet)
        encrypted_data.append({
            "cipher": cipher,
            "bbox": pts.tolist(),
            "confidence": confidence,
            "original_image_base64": roi_base64
        })
        print(f"[MASKED + ENCRYPTED] '{text}' -> {cipher[:12]}...")

    # === 保存图像和 JSON ===
    if output_image_path is None:
        name, ext = os.path.splitext(image_path)
        output_image_path = f"{name}_masked{ext}"
    cv2.imwrite(output_image_path, image)
    print(f"✅ 图像保存至：{output_image_path}")

    json_path = output_json_path or output_image_path.replace(ext, ".json")
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(encrypted_data, f, indent=2)
    print(f"✅ 加密数据保存至：{json_path}")

    return output_image_path, json_path, key_path
