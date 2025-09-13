# text_processor.py
import os
import json
import base64
import hashlib
import pandas as pd
import re
from cryptography.fernet import Fernet
from app.services.pii_main import extract_all_pii
# Importing a dictionary
from app.resources.dictionaries import NAMES, ORG_NAMES, RACES, STATUS, LOCATIONS, RELIGIONS

# === Fernet encryption related ===
def generate_fernet_key():
    return Fernet.generate_key()

def encrypt_fernet(text, fernet: Fernet):
    return fernet.encrypt(text.encode()).decode()

# === Dictionary matching function ===
def extract_from_dictionaries(text):
    results = []
    
    # Preprocessing text
    text_lower = text.lower()
    
    # Matching Names
    for name in NAMES:
        if name.lower() in text_lower:
            # Use regular expressions to ensure full word matches
            pattern = r'\b' + re.escape(name) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Name", match))
    
    # Matching Organisaion name
    for org in ORG_NAMES:
        if org.lower() in text_lower:
            pattern = r'\b' + re.escape(org) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("ORG", match))
    
    # Matching Races
    for race in RACES:
        if race.lower() in text_lower:
            pattern = r'\b' + re.escape(race) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Race", match))
    
    # Matching Status
    for status in STATUS:
        if status.lower() in text_lower:
            pattern = r'\b' + re.escape(status) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                results.append(("Status", match))
    
    # Matching Locations
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

# === Text reading ===
def read_text_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".txt", ".csv"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

# === Optimized main function ===
def run_text_processing(file_path: str, enabled_pii_categories=None, key_str: str = None):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        key = key_str.encode() if key_str else generate_fernet_key()
        fernet = Fernet(key)

        if ext == ".csv":
            return process_csv_optimized(file_path, fernet, key, enabled_pii_categories)
        else:
            return process_text_optimized(file_path, fernet, key, enabled_pii_categories)

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def process_csv_optimized(file_path: str, fernet: Fernet, key, enabled_pii_categories=None):
    """Optimized CSV processing functions, supporting selective PII masking"""
    # 1. Read the entire CSV as text for PII identification
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        full_content = f.read()

    print(f"[INFO] Starting PII extraction, enabled categories: {enabled_pii_categories}")
    # 2. Extract all PII at once (NER + rules, with selective filtering)
    pii_list = extract_all_pii(full_content, enabled_pii_categories)

    # Note: Dictionary matching is now integrated into extract_all_pii, no need to call separately
    all_pii_list = pii_list

    print(f"[INFO] Total found {len(all_pii_list)} PII items")
    
    # 4. Creating a Crypto Map - Using Hashing to Create Unique Labels
    pii_mapping = {}
    mapping = []
    
    for label, value in all_pii_list:
        if value not in pii_mapping:
            try:
                enc = encrypt_fernet(value, fernet)
                
                # Use a hash of the value to create a unique label, ensuring that the same value always gets the same label
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
                print(f"[ERROR] Failed to encrypt '{value}': {e}")

    # 5. Read CSV data for replacement
    df = pd.read_csv(file_path, dtype=str).fillna("")
    
    # 6. Sort replacements by length (avoiding partial replacements)
    sorted_pii_items = sorted(pii_mapping.items(), key=lambda x: len(x[0]), reverse=True)
    
    # 7. Batch Replace - Use exact match to avoid column misalignment
    print(f"[INFO] starting masking of {len(sorted_pii_items)} PII items")
    for pii_value, pii_info in sorted_pii_items:
        # Use exact string matching instead of regular expressions to avoid accidental matches
        df = df.replace(pii_value, pii_info["tag"], regex=False)
        print(f"[DEBUG] masking '{pii_value}' -> '{pii_info['tag']}'")

    print(f"[INFO] Masking completed: {df.shape}")

    # 8. save result
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

def process_text_optimized(file_path: str, fernet: Fernet, key, enabled_pii_categories=None):
    """Optimized text processing functions, supporting selective PII masking"""
    content = read_text_file(file_path)

    print("[INFO] Starting PII extraction...")
    # Use enhanced extract_all_pii (includes NER + rules + dictionary + Gemini)
    all_pii_list = extract_all_pii(content, enabled_pii_categories)

    print(f"[INFO] Total found {len(all_pii_list)} PII items")
    
    # Create unique PII mappings to avoid duplicate processing - use hashing to create unique tags
    unique_pii = {}
    mapping = []
    
    for label, value in all_pii_list:
        if value not in unique_pii:
            try:
                enc = encrypt_fernet(value, fernet)
                
                # Use a hash of the value to create a unique label, ensuring that the same value always gets the same label
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
                print(f"[ERROR] Failed to encrypt '{value}': {e}")

    # Replace by length
    sorted_pii_items = sorted(unique_pii.items(), key=lambda x: len(x[0]), reverse=True)

    masked_text = content
    for pii_value, pii_info in sorted_pii_items:
        # Use a safer replacement method that avoids nested encryption tags
        # Split text by existing encryption tags and only replace in non-encrypted parts
        parts = re.split(r'(\[ENC:[^\]]+\])', masked_text)

        for i in range(len(parts)):
            # Only replace in parts that are not encryption tags (odd indices are tags)
            if i % 2 == 0 and not parts[i].startswith('[ENC:'):
                escaped_pii = re.escape(pii_value)
                # Use word boundaries to ensure we match complete words when possible
                # For single characters or numbers, be more careful
                if len(pii_value) == 1 and pii_value.isdigit():
                    # For single digits, use word boundaries to avoid partial matches
                    pattern = r'\b' + escaped_pii + r'\b'
                else:
                    pattern = escaped_pii
                parts[i] = re.sub(pattern, pii_info["tag"], parts[i])

        masked_text = ''.join(parts)

    # save result
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
