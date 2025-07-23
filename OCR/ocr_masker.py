import json
import sys
import os
import cv2
import numpy as np
from cryptography.fernet import Fernet
import base64

def decrypt_sensitive_data(json_path, key_path, render_back=False):
    with open(key_path, 'rb') as key_file:
        key = key_file.read()
    cipher = Fernet(key)

    with open(json_path, 'r', encoding='utf-8') as json_file:
        encrypted_data = json.load(json_file)

    print("\n🔓 解密结果：")
    decrypted_items = []
    for i, item in enumerate(encrypted_data):
        try:
            decrypted = cipher.decrypt(item["cipher"].encode()).decode()
            print(f"{i+1:02d}. '{decrypted}' @ bbox={item['bbox']}")
            item["text"] = decrypted
            decrypted_items.append(item)
        except Exception as e:
            print(f"{i+1:02d}. [ERROR] 解密失败: {e}")

    if render_back:
        base = json_path.replace("_masked.json", "")
        image_path = f"{base}_masked.jpg"
        if not os.path.exists(image_path):
            print(f"[WARN] 无法找到图像: {image_path}，跳过渲染")
            return
        render_back_roi(image_path, decrypted_items)

def render_back_roi(image_path, decrypted_items):
    image = cv2.imread(image_path)
    if image is None:
        print(f"[ERROR] 无法加载图像: {image_path}")
        return

    for item in decrypted_items:
        bbox = np.array(item["bbox"], dtype=np.int32)
        base64_data = item.get("original_image_base64")
        if not base64_data:
            print("[WARN] 缺失原始图像数据，跳过该项")
            continue

        try:
            roi_bytes = base64.b64decode(base64_data)
            roi_image = cv2.imdecode(np.frombuffer(roi_bytes, np.uint8), cv2.IMREAD_COLOR)

            x, y, w, h = cv2.boundingRect(bbox)
            if roi_image.shape[0] != h or roi_image.shape[1] != w:
                roi_image = cv2.resize(roi_image, (w, h))

            image[y:y+h, x:x+w] = roi_image
            print(f"[RESTORED] '{item['text']}' 区域已还原")
        except Exception as e:
            print(f"[ERROR] 解码失败：{e}")

    output_path = image_path.replace("_masked.jpg", "_restored.jpg")
    cv2.imwrite(output_path, image)
    print(f"\n🎉 已将图像区域还原，保存为: {output_path}")

# === CLI ===
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python restore_from_mask.py decrypt <json_path> <key_path> [--render]")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == 'decrypt':
        if len(sys.argv) not in (4, 5):
            print("用法错误：python restore_from_mask.py decrypt <json_file> <key_file> [--render]")
            sys.exit(1)
        json_path = sys.argv[2]
        key_path = sys.argv[3]
        render_flag = len(sys.argv) == 5 and sys.argv[4] == "--render"
        decrypt_sensitive_data(json_path, key_path, render_flag)
    else:
        print(f"未知模式: {mode}")
