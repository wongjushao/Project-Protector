import base64
import cv2
import numpy as np
import json
from cryptography.fernet import Fernet
import io

def decrypt_masked_image_to_bytes(masked_image_path: str, json_path: str, key_path: str):
    # Loading an Image
    image = cv2.imread(masked_image_path)
    if image is None:
        raise ValueError("Unable to read image (possibly not written yet or path error): {masked_image_path}")

    # Loading Keys
    with open(key_path, "rb") as f:
        key = f.read()
    fernet = Fernet(key)

    # loading json
    with open(json_path, "r", encoding="utf-8") as f:
        encrypted_data = json.load(f)

    print(f"starting decryption of {len(encrypted_data)} encrypted regions")

    # Decrypt and replace image regions
    for i, entry in enumerate(encrypted_data):
        try:
            bbox = entry["bbox"]  # Now it is in the format [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            roi_b64 = entry.get("original_image_base64")

            if roi_b64:
                # Decode the original ROI image
                roi_data = base64.b64decode(roi_b64)
                roi_array = np.frombuffer(roi_data, dtype=np.uint8)
                roi = cv2.imdecode(roi_array, cv2.IMREAD_COLOR)

                if roi is not None:
                    # Extract rectangle coordinates from bbox
                    x_coords = [int(p[0]) for p in bbox]
                    y_coords = [int(p[1]) for p in bbox]
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)

                    print(f"Region {i+1}: coordinates ({x_min},{y_min}) to ({x_max},{y_max}), ROI size: {roi.shape}")

                    # Make sure the coordinates are within the image range
                    x_min = max(0, x_min)
                    y_min = max(0, y_min)
                    x_max = min(image.shape[1], x_max)
                    y_max = min(image.shape[0], y_max)

                    # Check if the region is valid
                    if (y_max - y_min) > 0 and (x_max - x_min) > 0:
                        # Resize the ROI to match the target region
                        target_h, target_w = y_max - y_min, x_max - x_min

                        # Resize ROI using high-quality interpolation methods
                        if roi.shape[0] != target_h or roi.shape[1] != target_w:
                            roi_resized = cv2.resize(roi, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
                        else:
                            roi_resized = roi

                        # Create a slightly larger area to handle border effects
                        # Expand by 1-2 pixels to ensure full coverage of the black area
                        expand_pixels = 1
                        x_min_exp = max(0, x_min - expand_pixels)
                        y_min_exp = max(0, y_min - expand_pixels)
                        x_max_exp = min(image.shape[1], x_max + expand_pixels)
                        y_max_exp = min(image.shape[0], y_max + expand_pixels)

                        #Check if the extended area is black (the masked area)
                        masked_region = image[y_min_exp:y_max_exp, x_min_exp:x_max_exp]
                        # If the expanded area is larger than the original ROI, the ROI size needs to be adjusted.
                        exp_h, exp_w = y_max_exp - y_min_exp, x_max_exp - x_min_exp
                        if exp_h != target_h or exp_w != target_w:
                            # Calculate the position of ROI in the expansion area
                            roi_y_offset = y_min - y_min_exp
                            roi_x_offset = x_min - x_min_exp

                            # Create an extended ROI, and fill the edges with the edge pixels of the original ROI
                            roi_expanded = np.zeros((exp_h, exp_w, 3), dtype=np.uint8)

                            # Place the original ROI in the correct position
                            roi_expanded[roi_y_offset:roi_y_offset+target_h,
                                       roi_x_offset:roi_x_offset+target_w] = roi_resized
                            # Fill edge area
                            if roi_y_offset > 0:  # up edge
                                roi_expanded[:roi_y_offset, :] = roi_expanded[roi_y_offset:roi_y_offset+1, :]
                            if roi_y_offset + target_h < exp_h:  # down edge
                                roi_expanded[roi_y_offset+target_h:, :] = roi_expanded[roi_y_offset+target_h-1:roi_y_offset+target_h, :]
                            if roi_x_offset > 0:  # left edge
                                roi_expanded[:, :roi_x_offset] = roi_expanded[:, roi_x_offset:roi_x_offset+1]
                            if roi_x_offset + target_w < exp_w:  # right edge
                                roi_expanded[:, roi_x_offset+target_w:] = roi_expanded[:, roi_x_offset+target_w-1:roi_x_offset+target_w]

                            # Replace extension area
                            image[y_min_exp:y_max_exp, x_min_exp:x_max_exp] = roi_expanded
                        else:
                            # Directly replace the original area
                            image[y_min:y_max, x_min:x_max] = roi_resized

                        print(f"region {i+1} decrypted (expanded area: {exp_w}x{exp_h})")
                    else:
                        print(f"region {i+1} failed: invalid coordinates")
                else:
                    print(f"region {i+1} ROI decoding failed, skipping")
            else:
                print(f"region {i+1} missing original image data, skipping")

        except Exception as e:
            print(f"decryption of region {i+1} failed: {e}")
            continue

    # Post-processing: Clean up any remaining black pixels
    image = post_process_decrypted_image(image, encrypted_data)

    # DEBUG: Saving the decrypted image
    cv2.imwrite("/tmp/debug_decrypted_result.png", image)
    print("decrypted image saved to /tmp/debug_decrypted_result.png")

    # Encode the image as a byte stream
    _, buffer = cv2.imencode('.png', image)
    img_bytes = buffer.tobytes()
    return img_bytes

def post_process_decrypted_image(image, encrypted_data):
    """
    Post-process the decrypted image to clean up the remaining black pixels
    """
    # Create a copy of an image
    processed_image = image.copy()

    # Post-process each decrypted area
    for i, entry in enumerate(encrypted_data):
        try:
            bbox = entry["bbox"]
            x_coords = [int(p[0]) for p in bbox]
            y_coords = [int(p[1]) for p in bbox]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            # Make sure the coordinates are within the image range
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(image.shape[1], x_max)
            y_max = min(image.shape[0], y_max)

            if (y_max - y_min) > 0 and (x_max - x_min) > 0:
                # Get Region
                region = processed_image[y_min:y_max, x_min:x_max]

                # Detect black pixels (pixels with RGB values close to 0)
                black_mask = np.all(region < 10, axis=2)  # The threshold is set to 10 to process pixels close to black.

                if np.any(black_mask):
                    # Use OpenCV's inpaint function to inpaint black pixels
                    # Mark black areas as areas that need inpainting
                    inpaint_mask = black_mask.astype(np.uint8) * 255

                    # Image restoration using the TELEA algorithm
                    if np.sum(inpaint_mask) > 0:  # Make sure there are pixels that need repairing
                        repaired_region = cv2.inpaint(region, inpaint_mask, 3, cv2.INPAINT_TELEA)
                        processed_image[y_min:y_max, x_min:x_max] = repaired_region
                        print(f"region {i+1} post-processed, fixed {np.sum(black_mask)} black pixels")

        except Exception as e:
            print(f"post-processing of region {i+1} failed: {e}")
            continue

    return processed_image