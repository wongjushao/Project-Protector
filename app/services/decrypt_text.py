# decrypt_text.py
from cryptography.fernet import Fernet
import os
import json
import pandas as pd
import re # Need to import the re module

def decrypt_fernet(ciphertext, fernet: Fernet):
    return fernet.decrypt(ciphertext.encode()).decode()

def decrypt_masked_file(masked_file_path, json_path, key_path):
    try:
        ext = os.path.splitext(masked_file_path)[1].lower()

        # Load key and json mapping
        with open(key_path, "rb") as f:
            key = f.read()
        fernet = Fernet(key)

        with open(json_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)

        # === Decrypting a CSV file ===
        if ext == ".csv":
            # Reading CSV using pandas keeping structure intact
            df = pd.read_csv(masked_file_path, dtype=str).fillna("")

            print(f"[INFO] Start decrypting CSV file, total {len(mapping_data)} mapping items")
            print(f"[INFO] CSV shape: {df.shape}")
            # Create a mapping of labels to raw values
            tag_to_original = {}
            for entry in mapping_data:
                tag_to_original[entry["masked"]] = entry["original"]
            # Sort by tag length in descending order to avoid short tags being mistakenly replaced by part of long tags
            sorted_tags = sorted(tag_to_original.items(), key=lambda x: len(x[0]), reverse=True)
            # Replace each cell in a DataFrame
            for tag, original_value in sorted_tags:
                # Use pandas' replace method to ensure only complete matches are replaced
                df = df.replace(tag, original_value, regex=False)
                print(f"[DEBUG] replacing '{tag}' -> '{original_value}'")

            # Write the decrypted file
            decrypted_file_path = masked_file_path.replace(".masked.csv", ".decrypted.csv")
            df.to_csv(decrypted_file_path, index=False)
            print(f"[INFO] csv decrypted: {decrypted_file_path}")

        # === Decrypt TXT file ===
        elif ext == ".txt":
            with open(masked_file_path, "r", encoding="utf-8") as f:
                masked_content = f.read()

            # --- Improved replacement method: replace all tags at once ---
            decrypted_content = masked_content
            # Sort by tag length in descending order to avoid short tags being mistakenly replaced by part of long tags
            sorted_entries = sorted(mapping_data, key=lambda x: len(x["masked"]), reverse=True)
            
            for entry in sorted_entries:
                unique_tag = entry["masked"]
                original_text = entry["original"]
                # Make sure to only replace complete tag matches, not partial matches
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
