# app/services/manual_masking_service.py
import cv2
import numpy as np
import os
import json
import uuid
from typing import List, Dict, Any
from cryptography.fernet import Fernet
import base64

def process_manual_masking(image_path: str, selections, task_id: str) -> Dict[str, Any]:
    """
    Process manually selected areas for masking
    
    Args:
        image_path: Path to the original image
        selections: List of manual selection areas
        task_id: Task ID for file organization
    
    Returns:
        dict: Processing result with masked image and metadata
    """
    try:
        print(f"[INFO] Starting manual masking for {image_path}")
        print(f"[INFO] Processing {len(selections)} manual selections")
        print(f"[DEBUG] Selections type: {type(selections)}")
        if selections:
            print(f"[DEBUG] First selection type: {type(selections[0])}")
            print(f"[DEBUG] First selection content: {selections[0]}")
        
        # Load the original image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        original_height, original_width = image.shape[:2]
        print(f"[INFO] Image dimensions: {original_width}x{original_height}")
        
        # Create a copy for masking
        masked_image = image.copy()
        
        # Generate encryption key
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)
        
        # Process each manual selection
        masked_areas = []
        areas_masked = 0
        
        for i, selection in enumerate(selections):
            try:
                # Handle both Pydantic models and dictionaries
                if hasattr(selection, 'dict'):
                    # Pydantic model
                    sel_dict = selection.dict()
                elif hasattr(selection, '__dict__'):
                    # Object with attributes
                    sel_dict = selection.__dict__
                else:
                    # Already a dictionary
                    sel_dict = selection

                # Extract selection coordinates
                x = int(sel_dict.get('x', 0))
                y = int(sel_dict.get('y', 0))
                width = int(sel_dict.get('width', 0))
                height = int(sel_dict.get('height', 0))
                selection_type = sel_dict.get('selection_type', 'rectangle')

                print(f"[DEBUG] Processing selection {i+1}: x={x}, y={y}, w={width}, h={height}, type={selection_type}")
                
                print(f"[INFO] Processing selection {i+1}: ({x}, {y}) {width}x{height}")

                # Validate coordinates
                if x < 0 or y < 0 or width <= 0 or height <= 0:
                    print(f"[WARN] Invalid selection coordinates: x={x}, y={y}, w={width}, h={height}")
                    continue
                
                # Ensure coordinates are within image bounds
                x = max(0, min(x, original_width - 1))
                y = max(0, min(y, original_height - 1))
                width = min(width, original_width - x)
                height = min(height, original_height - y)
                
                if width <= 0 or height <= 0:
                    print(f"[WARN] Selection outside image bounds: {selection}")
                    continue
                
                # Extract the area to be masked
                area_to_mask = image[y:y+height, x:x+width]
                
                # Create encrypted data for this area
                area_data = {
                    "selection_id": str(uuid.uuid4()),
                    "coordinates": {"x": x, "y": y, "width": width, "height": height},
                    "selection_type": selection_type,
                    "manual_selection": True,
                    "timestamp": str(uuid.uuid4())  # Using UUID as timestamp placeholder
                }
                
                # Encrypt the area data
                encrypted_data = cipher_suite.encrypt(json.dumps(area_data).encode())
                
                # Apply masking based on selection type
                if selection_type == "rectangle":
                    # Simple black rectangle mask
                    cv2.rectangle(masked_image, (x, y), (x + width, y + height), (0, 0, 0), -1)
                elif selection_type == "blur":
                    # Blur the selected area
                    roi = masked_image[y:y+height, x:x+width]
                    blurred_roi = cv2.GaussianBlur(roi, (51, 51), 0)
                    masked_image[y:y+height, x:x+width] = blurred_roi
                else:
                    # Default to black rectangle
                    cv2.rectangle(masked_image, (x, y), (x + width, y + height), (0, 0, 0), -1)
                
                # Store masked area info
                masked_areas.append({
                    "selection_id": area_data["selection_id"],
                    "coordinates": area_data["coordinates"],
                    "selection_type": selection_type,
                    "encrypted_data": base64.b64encode(encrypted_data).decode(),
                    "manual_selection": True
                })
                
                areas_masked += 1
                print(f"[SUCCESS] Masked area {i+1}: ({x}, {y}) {width}x{height}")
                
            except Exception as e:
                print(f"[ERROR] Failed to process selection {i+1}: {e}")
                continue
        
        # Generate output file paths
        name, ext = os.path.splitext(image_path)
        output_image_path = f"{name}_manual_masked{ext}"
        output_json_path = f"{name}_manual_review.json"
        key_file_path = f"{name}_manual.key"
        
        # Save the masked image
        cv2.imwrite(output_image_path, masked_image)
        print(f"[SUCCESS] Saved masked image: {output_image_path}")
        
        # Save the encrypted data
        manual_review_data = {
            "task_id": task_id,
            "original_image": os.path.basename(image_path),
            "masked_image": os.path.basename(output_image_path),
            "total_selections": len(selections),
            "areas_masked": areas_masked,
            "manual_review": True,
            "masked_areas": masked_areas,
            "image_dimensions": {
                "width": original_width,
                "height": original_height
            }
        }
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(manual_review_data, f, indent=2)
        print(f"[SUCCESS] Saved review data: {output_json_path}")
        
        # Save the encryption key
        with open(key_file_path, 'wb') as f:
            f.write(key)
        print(f"[SUCCESS] Saved encryption key: {key_file_path}")
        
        # Convert paths to relative URLs for serving
        base_path = os.path.dirname(image_path)
        relative_base = base_path.replace("uploads", "/uploads").replace("\\", "/")
        
        result = {
            "status": "success",
            "masked_image": f"{relative_base}/{os.path.basename(output_image_path)}",
            "json_output": f"{relative_base}/{os.path.basename(output_json_path)}",
            "key_file": f"{relative_base}/{os.path.basename(key_file_path)}",
            "areas_masked": areas_masked,
            "total_selections": len(selections),
            "manual_review": True,
            "image_dimensions": {
                "width": original_width,
                "height": original_height
            }
        }
        
        print(f"[SUCCESS] Manual masking completed: {areas_masked}/{len(selections)} areas processed")
        return result
        
    except Exception as e:
        print(f"[ERROR] Manual masking failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e)
        }

def decrypt_manual_selection(encrypted_data: str, key_path: str) -> Dict[str, Any]:
    """
    Decrypt manually selected area data
    
    Args:
        encrypted_data: Base64 encoded encrypted data
        key_path: Path to the encryption key file
    
    Returns:
        dict: Decrypted area data
    """
    try:
        # Load the encryption key
        with open(key_path, 'rb') as f:
            key = f.read()
        
        cipher_suite = Fernet(key)
        
        # Decode and decrypt the data
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted_data = cipher_suite.decrypt(encrypted_bytes)
        
        # Parse the JSON data
        area_data = json.loads(decrypted_data.decode())
        
        return area_data
        
    except Exception as e:
        print(f"[ERROR] Failed to decrypt manual selection: {e}")
        return {}

def validate_manual_selections(selections: List[Dict], image_width: int, image_height: int) -> List[Dict]:
    """
    Validate and sanitize manual selections
    
    Args:
        selections: List of manual selections
        image_width: Image width for bounds checking
        image_height: Image height for bounds checking
    
    Returns:
        list: Validated selections
    """
    validated_selections = []
    
    for i, selection in enumerate(selections):
        try:
            # Extract and validate coordinates
            x = max(0, min(int(selection.get('x', 0)), image_width - 1))
            y = max(0, min(int(selection.get('y', 0)), image_height - 1))
            width = max(1, min(int(selection.get('width', 1)), image_width - x))
            height = max(1, min(int(selection.get('height', 1)), image_height - y))
            
            # Validate selection type
            selection_type = selection.get('selection_type', 'rectangle')
            if selection_type not in ['rectangle', 'blur', 'freehand']:
                selection_type = 'rectangle'
            
            validated_selection = {
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'selection_type': selection_type
            }
            
            validated_selections.append(validated_selection)
            print(f"[INFO] Validated selection {i+1}: ({x}, {y}) {width}x{height}")
            
        except Exception as e:
            print(f"[WARN] Invalid selection {i+1}: {e}")
            continue
    
    return validated_selections
