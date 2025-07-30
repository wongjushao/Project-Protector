import base64
import cv2
import numpy as np
import json
from cryptography.fernet import Fernet
import io

def decrypt_masked_image_to_bytes(masked_image_path: str, json_path: str, key_path: str):
    # 加载图像
    image = cv2.imread(masked_image_path)
    if image is None:
        raise ValueError("Unable to read image (possibly not written yet or path error): {masked_image_path}")

    # 加载密钥
    with open(key_path, "rb") as f:
        key = f.read()
    fernet = Fernet(key)

    # 加载 JSON
    with open(json_path, "r", encoding="utf-8") as f:
        encrypted_data = json.load(f)

    print(f"starting decryption of {len(encrypted_data)} encrypted regions")

    # 解密并替换图像区域
    for i, entry in enumerate(encrypted_data):
        try:
            bbox = entry["bbox"]  # 现在是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 格式
            roi_b64 = entry.get("original_image_base64")

            if roi_b64:
                # 解码原始ROI图像
                roi_data = base64.b64decode(roi_b64)
                roi_array = np.frombuffer(roi_data, dtype=np.uint8)
                roi = cv2.imdecode(roi_array, cv2.IMREAD_COLOR)

                if roi is not None:
                    # 从bbox提取矩形坐标
                    x_coords = [int(p[0]) for p in bbox]
                    y_coords = [int(p[1]) for p in bbox]
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)

                    print(f"区域 {i+1}: 坐标 ({x_min},{y_min}) to ({x_max},{y_max}), ROI尺寸: {roi.shape}")

                    # 确保坐标在图像范围内
                    x_min = max(0, x_min)
                    y_min = max(0, y_min)
                    x_max = min(image.shape[1], x_max)
                    y_max = min(image.shape[0], y_max)

                    # 检查区域是否有效
                    if (y_max - y_min) > 0 and (x_max - x_min) > 0:
                        # 调整ROI大小以匹配目标区域
                        target_h, target_w = y_max - y_min, x_max - x_min

                        # 使用高质量插值方法调整ROI大小
                        if roi.shape[0] != target_h or roi.shape[1] != target_w:
                            roi_resized = cv2.resize(roi, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
                        else:
                            roi_resized = roi

                        # 创建一个稍大的区域来处理边界效应
                        # 扩展1-2像素以确保完全覆盖黑色区域
                        expand_pixels = 1
                        x_min_exp = max(0, x_min - expand_pixels)
                        y_min_exp = max(0, y_min - expand_pixels)
                        x_max_exp = min(image.shape[1], x_max + expand_pixels)
                        y_max_exp = min(image.shape[0], y_max + expand_pixels)

                        # 检查扩展区域是否为黑色（被遮罩的区域）
                        masked_region = image[y_min_exp:y_max_exp, x_min_exp:x_max_exp]

                        # 如果扩展区域比原ROI大，需要调整ROI大小
                        exp_h, exp_w = y_max_exp - y_min_exp, x_max_exp - x_min_exp
                        if exp_h != target_h or exp_w != target_w:
                            # 计算ROI在扩展区域中的位置
                            roi_y_offset = y_min - y_min_exp
                            roi_x_offset = x_min - x_min_exp

                            # 创建扩展的ROI，边缘使用原ROI的边缘像素填充
                            roi_expanded = np.zeros((exp_h, exp_w, 3), dtype=np.uint8)

                            # 将原ROI放置在正确位置
                            roi_expanded[roi_y_offset:roi_y_offset+target_h,
                                       roi_x_offset:roi_x_offset+target_w] = roi_resized

                            # 填充边缘区域
                            if roi_y_offset > 0:  # 上边缘
                                roi_expanded[:roi_y_offset, :] = roi_expanded[roi_y_offset:roi_y_offset+1, :]
                            if roi_y_offset + target_h < exp_h:  # 下边缘
                                roi_expanded[roi_y_offset+target_h:, :] = roi_expanded[roi_y_offset+target_h-1:roi_y_offset+target_h, :]
                            if roi_x_offset > 0:  # 左边缘
                                roi_expanded[:, :roi_x_offset] = roi_expanded[:, roi_x_offset:roi_x_offset+1]
                            if roi_x_offset + target_w < exp_w:  # 右边缘
                                roi_expanded[:, roi_x_offset+target_w:] = roi_expanded[:, roi_x_offset+target_w-1:roi_x_offset+target_w]

                            # 替换扩展区域
                            image[y_min_exp:y_max_exp, x_min_exp:x_max_exp] = roi_expanded
                        else:
                            # 直接替换原区域
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

    # 后处理：清理可能残留的黑色像素
    image = post_process_decrypted_image(image, encrypted_data)

    # 调试：保存解密后的图像
    cv2.imwrite("/tmp/debug_decrypted_result.png", image)
    print("decrypted image saved to /tmp/debug_decrypted_result.png")

    # 将图像编码为字节流
    _, buffer = cv2.imencode('.png', image)
    img_bytes = buffer.tobytes()
    return img_bytes

def post_process_decrypted_image(image, encrypted_data):
    """
    后处理解密后的图像，清理残留的黑色像素
    """
    # 创建图像副本
    processed_image = image.copy()

    # 对每个解密区域进行后处理
    for i, entry in enumerate(encrypted_data):
        try:
            bbox = entry["bbox"]
            x_coords = [int(p[0]) for p in bbox]
            y_coords = [int(p[1]) for p in bbox]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            # 确保坐标在图像范围内
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(image.shape[1], x_max)
            y_max = min(image.shape[0], y_max)

            if (y_max - y_min) > 0 and (x_max - x_min) > 0:
                # 获取区域
                region = processed_image[y_min:y_max, x_min:x_max]

                # 检测黑色像素 (RGB值接近0的像素)
                black_mask = np.all(region < 10, axis=2)  # 阈值设为10，处理接近黑色的像素

                if np.any(black_mask):
                    # 使用OpenCV的inpaint功能修复黑色像素
                    # 将黑色区域标记为需要修复的区域
                    inpaint_mask = black_mask.astype(np.uint8) * 255

                    # 使用TELEA算法进行图像修复
                    if np.sum(inpaint_mask) > 0:  # 确保有需要修复的像素
                        repaired_region = cv2.inpaint(region, inpaint_mask, 3, cv2.INPAINT_TELEA)
                        processed_image[y_min:y_max, x_min:x_max] = repaired_region
                        print(f"region {i+1} post-processed, fixed {np.sum(black_mask)} black pixels")

        except Exception as e:
            print(f"post-processing of region {i+1} failed: {e}")
            continue

    return processed_image