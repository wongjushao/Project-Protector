# decrypt_text.py
from cryptography.fernet import Fernet
import os
import json
import pandas as pd
import re # 需要导入 re 模块

def decrypt_fernet(ciphertext, fernet: Fernet):
    return fernet.decrypt(ciphertext.encode()).decode()

def decrypt_masked_file(masked_file_path, json_path, key_path):
    try:
        ext = os.path.splitext(masked_file_path)[1].lower()

        # 加载 key 和 json 映射
        with open(key_path, "rb") as f:
            key = f.read()
        fernet = Fernet(key)

        with open(json_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)

        # === 解密 CSV 文件 ===
        if ext == ".csv":
            # 使用pandas读取CSV以保持结构完整性
            df = pd.read_csv(masked_file_path, dtype=str).fillna("")

            print(f"[INFO] 开始解密CSV文件，共 {len(mapping_data)} 个映射项")
            print(f"[INFO] CSV形状: {df.shape}")

            # 创建标签到原始值的映射
            tag_to_original = {}
            for entry in mapping_data:
                tag_to_original[entry["masked"]] = entry["original"]

            # 按标签长度降序排序，避免短标签被长标签的一部分误替换
            sorted_tags = sorted(tag_to_original.items(), key=lambda x: len(x[0]), reverse=True)

            # 对DataFrame中的每个单元格进行替换
            for tag, original_value in sorted_tags:
                # 使用pandas的replace方法，确保只替换完整匹配
                df = df.replace(tag, original_value, regex=False)
                print(f"[DEBUG] 替换标签 '{tag}' -> '{original_value}'")

            # 写入解密后的文件
            decrypted_file_path = masked_file_path.replace(".masked.csv", ".decrypted.csv")
            df.to_csv(decrypted_file_path, index=False)
            print(f"[INFO] CSV解密完成，保存到: {decrypted_file_path}")

        # === 解密 TXT 文件 ===
        elif ext == ".txt":
            with open(masked_file_path, "r", encoding="utf-8") as f:
                masked_content = f.read()

            # --- 改进的替换方法：一次性替换所有标签 ---
            decrypted_content = masked_content
            
            # 按标签长度降序排序，避免短标签被长标签的一部分误替换
            sorted_entries = sorted(mapping_data, key=lambda x: len(x["masked"]), reverse=True)
            
            for entry in sorted_entries:
                unique_tag = entry["masked"]
                original_text = entry["original"]
                # 确保只替换完整的标签匹配，而不是部分匹配
                decrypted_content = decrypted_content.replace(unique_tag, original_text)

            decrypted_file_path = masked_file_path.replace(".masked.txt", ".decrypted.txt")
            with open(decrypted_file_path, "w", encoding="utf-8") as f:
                f.write(decrypted_content)

        else:
            return {"status": "error", "message": f"Unsupported file extension: {ext}"}

        return {
            "status": "success",
            "decrypted_file": decrypted_file_path
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
