# image_processor.py
from app.services.ocr_jpeg import mask_sensitive_text
import os

def run_ocr_jpeg(image_path: str, enabled_pii_categories=None):
    """
    Process JPEG/image files with OCR and selective PII masking

    Args:
        image_path: Path to the image file
        enabled_pii_categories: List of PII categories to mask (selective masking)

    Returns:
        dict: Processing result with masked image, JSON output, and key file
    """
    try:
        # Default to all selectable categories if none specified
        if enabled_pii_categories is None:
            enabled_pii_categories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']

        print(f"[INFO] Processing image with enabled PII categories: {enabled_pii_categories}")

        # 生成一个单独的 .key 文件路径
        name, _ = os.path.splitext(image_path)
        key_path = f"{name}.key"  # 不覆盖原图

        masked_img, json_path, key_file = mask_sensitive_text(
            image_path=image_path,
            key_path=key_path,
            enabled_pii_categories=enabled_pii_categories
        )

        # Calculate PII statistics for audit logging
        pii_stats = _calculate_pii_stats(json_path, enabled_pii_categories)

        return {
            "status": "success",
            "masked_image": masked_img,
            "json_output": json_path,
            "key_file": key_file,
            "pii_found": pii_stats.get("total_found", 0),
            "pii_masked": pii_stats.get("total_masked", 0),
            "selectable_pii_found": pii_stats.get("selectable_found", {}),
            "non_selectable_pii_found": pii_stats.get("non_selectable_found", {}),
            "average_confidence": pii_stats.get("average_confidence", 0.0),
            "low_confidence_count": pii_stats.get("low_confidence_count", 0)
        }
    except Exception as e:
        print(f"[ERROR] Image processing failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def _calculate_pii_stats(json_path, enabled_categories):
    """Calculate PII statistics from the JSON output"""
    try:
        if not os.path.exists(json_path):
            return {"total_found": 0, "total_masked": 0}

        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_masked = len(data)
        confidences = [item.get("confidence", 0.0) for item in data]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        low_confidence = sum(1 for c in confidences if c < 0.7)

        return {
            "total_found": total_masked,  # For images, found = masked (we only detect what we mask)
            "total_masked": total_masked,
            "selectable_found": {"IMAGES": total_masked},  # Simplified for images
            "non_selectable_found": {},
            "average_confidence": avg_confidence,
            "low_confidence_count": low_confidence
        }
    except Exception as e:
        print(f"[WARN] Failed to calculate PII stats: {e}")
        return {"total_found": 0, "total_masked": 0}
