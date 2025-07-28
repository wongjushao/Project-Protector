# text_processor.py
import os
import json
import base64
import hashlib
import pandas as pd
import re
from cryptography.fernet import Fernet
from app.services.pii_main import extract_all_pii
# 导入字典
from app.resources.dictionaries import NAMES, ORG_NAMES, RACES, STATUS, LOCATIONS, RELIGIONS

# === Fernet 加密相关 ===
def generate_fernet_key():
    return Fernet.generate_key()

def encrypt_fernet(text, fernet: Fernet):
    return fernet.encrypt(text.encode()).decode()

# === 字典匹配函数 ===
def extract_from_dictionaries(text):
    """从字典中提取PII"""
    results = []
    
    # 预处理文本
    text_lower = text.lower()
    
    # 匹配姓名
    for name in NAMES:
        if name.lower() in text_lower:
            # 使用正则表达式确保是完整单词匹配
            pattern = r'\b' + re.escape(name) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Name", match))
    
    # 匹配组织名称
    for org in ORG_NAMES:
        if org.lower() in text_lower:
            pattern = r'\b' + re.escape(org) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("ORG", match))
    
    # 匹配种族
    for race in RACES:
        if race.lower() in text_lower:
            pattern = r'\b' + re.escape(race) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Race", match))
    
    # 匹配状态
    for status in STATUS:
        if status.lower() in text_lower:
            pattern = r'\b' + re.escape(status) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Status", match))
    
    # 匹配地点
    for location in LOCATIONS:
        if location.lower() in text_lower:
            pattern = r'\b' + re.escape(location) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Location", match))
    
    for religion in RELIGIONS:
        if religion.lower() in text_lower:
            pattern = r'\b' + re.escape(religion) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Religion", match))
    return results

# === 文本读取 ===
def read_text_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".txt", ".csv"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

# === 优化的主函数 ===
def run_text_processing(file_path: str, enabled_pii_categories=None, key_str: str = None):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        key = key_str.encode() if key_str else generate_fernet_key()
        fernet = Fernet(key)

        if ext == ".csv":
            return process_csv_optimized(file_path, fernet, key, enabled_pii_categories)
        else:
            return process_text_optimized(file_path, fernet, key)

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def process_csv_optimized(file_path: str, fernet: Fernet, key, enabled_pii_categories=None):
    """优化的CSV处理函数，支持选择性PII遮罩"""
    # 1. 读取整个CSV为文本进行PII识别
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        full_content = f.read()

    print(f"[INFO] 开始提取PII，启用类别: {enabled_pii_categories}")
    # 2. 一次性提取所有PII（NER + 规则，支持选择性过滤）
    pii_list = extract_all_pii(full_content, enabled_pii_categories)

    # 注意：字典匹配现在已经集成到extract_all_pii中，不需要单独调用
    all_pii_list = pii_list
    
    print(f"[INFO] 总共找到 {len(all_pii_list)} 个PII项")
    
    # 4. 创建加密映射 - 使用哈希来创建唯一标签
    pii_mapping = {}
    mapping = []
    
    for label, value in all_pii_list:
        if value not in pii_mapping:  # 避免重复加密
            try:
                enc = encrypt_fernet(value, fernet)
                
                # 使用值的哈希创建唯一标签，确保相同值总是得到相同标签
                value_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                unique_tag = f"[ENC:{label}_{value_hash}]"
                
                pii_mapping[value] = {"encrypted": enc, "tag": unique_tag}
                mapping.append({
                    "original": value,
                    "encrypted": enc,
                    "label": label,
                    "masked": unique_tag
                })
            except Exception as e:
                print(f"[ERROR] 加密失败 '{value}': {e}")

    # 5. 读取CSV数据进行替换
    df = pd.read_csv(file_path, dtype=str).fillna("")
    
    # 6. 按长度排序进行替换（避免部分替换）
    sorted_pii_items = sorted(pii_mapping.items(), key=lambda x: len(x[0]), reverse=True)
    
    # 7. 批量替换 - 使用精确匹配避免列错位
    print(f"[INFO] 开始替换 {len(sorted_pii_items)} 个PII项")
    for pii_value, pii_info in sorted_pii_items:
        # 使用精确字符串匹配而不是正则表达式，避免意外匹配
        df = df.replace(pii_value, pii_info["tag"], regex=False)
        print(f"[DEBUG] 替换 '{pii_value}' -> '{pii_info['tag']}'")

    print(f"[INFO] CSV替换完成，最终形状: {df.shape}")

    # 8. 保存结果
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.dirname(file_path)
    masked_csv_path = os.path.join(output_dir, base_name + ".masked.csv")
    json_output_path = os.path.join(output_dir, base_name + ".masked.json")
    key_file_path = os.path.join(output_dir, base_name + ".key")

    df.to_csv(masked_csv_path, index=False)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    with open(key_file_path, "wb") as f:
        f.write(key)

    return {
        "status": "success",
        "masked_file": masked_csv_path,
        "json_output": json_output_path,
        "key_file": key_file_path
    }

def process_text_optimized(file_path: str, fernet: Fernet, key):
    """优化的文本处理函数"""
    content = read_text_file(file_path)
    
    print("[INFO] 开始提取PII...")
    # 提取所有PII（NER + 规则 + 字典）
    pii_list = extract_all_pii(content)
    dict_pii_list = extract_from_dictionaries(content)
    all_pii_list = pii_list + dict_pii_list
    
    print(f"[INFO] NER找到 {len(pii_list)} 个PII项")
    print(f"[INFO] 字典匹配找到 {len(dict_pii_list)} 个PII项")
    print(f"[INFO] 总共找到 {len(all_pii_list)} 个PII项")
    
    # 创建唯一PII映射避免重复处理 - 使用哈希来创建唯一标签
    unique_pii = {}
    mapping = []
    
    for label, value in all_pii_list:
        if value not in unique_pii:
            try:
                enc = encrypt_fernet(value, fernet)
                
                # 使用值的哈希创建唯一标签，确保相同值总是得到相同标签
                value_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                unique_tag = f"[ENC:{label}_{value_hash}]"
                
                unique_pii[value] = {"encrypted": enc, "tag": unique_tag}
                mapping.append({
                    "original": value,
                    "encrypted": enc,
                    "label": label,
                    "masked": unique_tag
                })
            except Exception as e:
                print(f"[ERROR] 加密失败 '{value}': {e}")

    # 按长度排序进行替换
    sorted_pii_items = sorted(unique_pii.items(), key=lambda x: len(x[0]), reverse=True)
    
    masked_text = content
    for pii_value, pii_info in sorted_pii_items:
        escaped_pii = re.escape(pii_value)
        masked_text = re.sub(escaped_pii, pii_info["tag"], masked_text)

    # 保存结果
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.dirname(file_path)
    masked_file_path = os.path.join(output_dir, base_name + ".masked.txt")
    json_output_path = os.path.join(output_dir, base_name + ".masked.json")
    key_file_path = os.path.join(output_dir, base_name + ".key")

    with open(masked_file_path, "w", encoding="utf-8") as f:
        f.write(masked_text)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    with open(key_file_path, "wb") as f:
        f.write(key)

    return {
        "status": "success",
        "masked_file": masked_file_path,
        "json_output": json_output_path,
        "key_file": key_file_path
    }