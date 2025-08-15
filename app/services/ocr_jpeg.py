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
import re

def _should_ignore_word(text, ignore_words):
    """
    Check if text should be ignored based on exact word matching.
    Uses word boundaries to avoid false positives from substring matching.

    Args:
        text (str): The text to check (should be lowercase)
        ignore_words (set): Set of words to ignore (should be lowercase)

    Returns:
        bool: True if the text should be ignored
    """
    # Normalize the text
    text = text.strip().lower()

    # Check for exact match first
    if text in ignore_words:
        return True

    # For multi-word ignore phrases, check if the entire text matches
    # Split text into words and check if it forms any ignore phrase
    text_words = re.findall(r'\b\w+\b', text)
    text_phrase = ' '.join(text_words)

    if text_phrase in ignore_words:
        return True

    # Check if text is a single word that should be ignored
    if len(text_words) == 1 and text_words[0] in ignore_words:
        return True

    return False

def mask_region_improved(image, x_min, y_min, x_max, y_max):
    """
    Improved masking method using gradient edges to reduce hard edge effects
    """
    # Create a basic black rectangular mask
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

    # Add a slight edge blur to reduce sharp edges
    # This helps with better blending during decryption
    border_width = 1
    if border_width > 0:
        # Adds a slight blur around the masked area
        x_start = max(0, x_min - border_width)
        y_start = max(0, y_min - border_width)
        x_end = min(image.shape[1], x_max + border_width)
        y_end = min(image.shape[0], y_max + border_width)

        # Get the bounding area
        border_region = image[y_start:y_end, x_start:x_end].copy()

        # Apply a slight blur to the boundary areas
        if border_region.size > 0:
            blurred = cv2.GaussianBlur(border_region, (3, 3), 0.5)
            image[y_start:y_end, x_start:x_end] = blurred

            # Repaint the core black area
            cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

# === Encryption/Decryption ===
def generate_key():
    return Fernet.generate_key()

def encrypt_text(text, fernet):
    return fernet.encrypt(text.encode()).decode()

# === bbox IOU determination (remove reuse) ===
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
            Fernet(key)
        else:
            raise ValueError("Key file does not exist")
    except Exception as e:
        print(f"[WARN] Invalid or corrupted key (or path conflict): {e}")
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
    return key


# === Main Function: Masking + Encryption ===
def mask_sensitive_text(image_path, key_path, output_json_path=None, output_image_path=None, reader=None, keywords=None, enabled_pii_categories=None):
    from easyocr import Reader
    if reader is None:
        reader = Reader(['en', 'ms'], gpu=True)
    results = reader.readtext(image_path)
    image = cv2.imread(image_path)
    if image is None: 
        raise ValueError(f"Unable to read image (possibly not written yet or path error): {image_path}")
    encrypted_data = []
 
    # === Step 1: Group text lines by y position (simulating "rows") ===
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

    # Sort and group into "rows"
    lines.sort(key=lambda x: x['center_y'])
    grouped_lines = []
    current_group = []
    threshold = 25  # Line spacing threshold (adjustable based on image resolution)

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

    # === Step 2: Construct the complete text of each line ===
    full_text_lines = []
    for group in grouped_lines:
        # Sort text within a line by x
        group_sorted = sorted(group, key=lambda x: min(p[0] for p in x['bbox']))
        line_text = " ".join(item['text'] for item in group_sorted)
        full_text_lines.append(line_text)

    full_text = "\n".join(full_text_lines)
    print(f"[INFO] Full text:\n{full_text}\n")

    # === Step 3: Extract PII (supports selective category filtering) ===
    # Default to all selectable categories if none specified
    if enabled_pii_categories is None:
        enabled_pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']

    print(f"[INFO] Enabled PII categories: {enabled_pii_categories}")

    # Use selective PII extraction
    pii_entries = extract_all_pii(full_text, enabled_pii_categories)
    print(f"[INFO] Extracted {len(pii_entries)} PII items (with selective filtering)")

    # ✅ Business-level ignored words (ignored only in image mask scenarios)
    # Note: Using exact word matching to avoid false positives
    IGNORE_WORDS = {
        # Document artifacts and watermarks
        "copy", "confidential", "draft", "sample", "example", "template", "specimen",
        "watermark", "void", "duplicate", "original", "certified", "true copy",

        # Malaysian document terms
        "malaysia", "mykad", "identity", "card", "identity card", "kad", "pengenalan",
        "kad pengenalan", "warganegara", "lelaki", "perempuan", "bujang", "kawin",
        "male", "female", "citizen", "not citizen",

        # Generic form labels (exact matches only)
        "name", "address", "phone", "email", "type", "number",
        "identification", "passport",

        # Banking terms (form labels, not actual data)
        "bank", "account", "account type", "account no", "account number",
        "bank account", "bank name", "bank statement", "statement",
        "account holder", "account holder name",
        "public bank", "maybank", "cimb", "hsbc", "standard chartered", "uob", "ocbc",

        # Common short words that cause false positives (removed)
        # Removed: "id", "no", "my", "k", "your" - too generic and cause false matches

        # Specific document headers/footers
        "bank statement example", "four bank", "specimen copy"
    }

    # ✅ Malaysia location whitelist (for LOC filtering)
    MALAYSIA_LOCATIONS = {
    }

    # 过滤和处理PII结果
    filtered_pii = []
    selectable_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']

    print("[INFO] Processing PII detection results:")
    for label, value in pii_entries:
        clean_val = value.strip().lower()
        original_val = value.strip()
        # Skipping null values
        if not original_val:
            continue
        # Ignore common non-sensitive words (use exact word matching to avoid misjudgment)
        if _should_ignore_word(clean_val, IGNORE_WORDS):
            print(f"[SKIP] Ignoring non-sensitive word: {original_val}")
            continue
        # Selective PII categories: Only those in enabled_categories will be masked
        if label in selectable_categories:
            if label in enabled_pii_categories:
                filtered_pii.append((label, original_val))
                print(f"[MASK] Selective PII - {label}: {original_val}")
            else:
                print(f"[SKIP] Selective PII not enabled - {label}: {original_val}")
        else:
            # Non-selective PII (like IC, EMAIL, PHONE, etc.): always mask
            filtered_pii.append((label, original_val))
            print(f"[MASK] Non-selective PII - {label}: {original_val}")
    # Update keywords
    keywords = list(set(value for _, value in filtered_pii))
    print(f"[INFO] Will finally mask {len(keywords)} keywords")
    # === Step 4: Load or generate a key ===
    key = load_or_generate_valid_key(key_path)
    fernet = Fernet(key)
    seen = []
    # === Step 5: Traverse the original OCR results and match keywords (support cross-line keywords) ===
    for bbox, text, confidence in results:
        matched = False
        for keyword in keywords:
            # Checks if a keyword "spreads across lines" but the current line contains part of it
            if keyword.lower() in text.lower():
                matched = True
                break
            # Or: Is the current text a substring (prefix/suffix) of the keyword, and is there another part nearby?
            if (keyword.lower().startswith(text.lower()) or keyword.lower().endswith(text.lower())) and len(text) > 3:
                # Enable "cross-row merge detection" (advanced option available, but simple processing is provided here)
                pass  # Scalable: Search neighboring box stitching

        if not matched:
            continue

        # Checks if this text should be ignored (checked before masking)
        if _should_ignore_word(text, IGNORE_WORDS):
            print(f"[SKIP] Ignoring non-sensitive word (OCR stage): {text}")
            continue

        # Deduplication: Use IOU to determine whether it has been processed
        duplicate = False
        for s in seen:
            if iou(bbox, s["bbox"]) > 0.85 and text.lower() == s["text"].lower():
                duplicate = True
                break
        if duplicate:
            continue
        seen.append({"bbox": bbox, "text": text})

        # === Masking + Encryption ===
        x_coords = [int(p[0]) for p in bbox]
        y_coords = [int(p[1]) for p in bbox]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        roi = image[y_min:y_max, x_min:x_max]

        success, roi_encoded = cv2.imencode('.png', roi)
        if not success:
            print(f"[WARN] Region encoding failed, skipping: {text}")
            continue

        roi_base64 = base64.b64encode(roi_encoded).decode('utf-8')
        # Use improved masking methods to avoid hard edges
        mask_region_improved(image, x_min, y_min, x_max, y_max)
        cipher = encrypt_text(text, fernet)
        encrypted_data.append({
            "cipher": cipher,
            "bbox": [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]],
            "confidence": confidence,
            "original_image_base64": roi_base64
        })
        print(f"[MASKED + ENCRYPTED] '{text}' -> {cipher[:12]}...")

    # === Saving images and JSON ===
    if output_image_path is None:
        name, ext = os.path.splitext(image_path)
        output_image_path = f"{name}_masked{ext}"
    cv2.imwrite(output_image_path, image)
    print(f"✅ Masked image saved to: {output_image_path}")

    json_path = output_json_path or output_image_path.replace(ext, ".json")
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(encrypted_data, f, indent=2)
    print(f"✅ Encrypted data saved to: {json_path}")

    # === Output processing summary ===
    print(f"\n📊 Image processing summary:")
    print(f"   - Enabled PII categories: {enabled_pii_categories}")
    print(f"   - Detected PII items: {len(pii_entries)}")
    print(f"   - Actually masked items: {len(encrypted_data)}")
    print(f"   - Masked image: {output_image_path}")
    print(f"   - Encrypted data: {json_path}")
    print(f"   - Key file: {key_path}")

    return output_image_path, json_path, key_path
