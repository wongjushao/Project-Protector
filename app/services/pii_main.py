# OCR/pii_main.py
import re
from transformers import TFAutoModelForTokenClassification, AutoTokenizer, pipeline

# === 模型加载 ===
model_name = "jplu/tf-xlm-r-ner-40-lang"
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
model = TFAutoModelForTokenClassification.from_pretrained(model_name)

ner_pipeline = pipeline(
    task="ner",
    model=model,
    tokenizer=tokenizer,
    framework="tf",
    aggregation_strategy=None  # 细粒度输出
)

# === 通用忽略词（非敏感，不需加密）===
IGNORE_WORDS = {
    "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
    "warganegara", "lelaki", "perempuan", "bujang", "kawin",
    "lel", "per", "male", "female", "citizen", "not citizen"
}

# === 正则提取器 ===
def extract_ic(text):
    return re.findall(r"\b\d{6}-\d{2}-\d{4}\b", text)

def extract_email(text):
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

def extract_dob(text):
    return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)

def extract_bank_account(text):
    return re.findall(r"\b\d{10,16}\b", text)

def extract_passport(text):
    return re.findall(r"\b[A-Z]\d{7}\b", text)

def extract_phone(text):
    return re.findall(r'(\+60\d{1,2}[-\s]?\d{6,8}|\b01\d[-\s]?\d{7,8}\b)', text)

def extract_money(text):
    return re.findall(r"\bRM\s?\d+(?:,\d{3})*(?:\.\d{2})?\b", text)

def extract_gender(text):
    return re.findall(r'\b(LELAKI|PEREMPUAN|MALE|FEMALE)\b', text, re.I)

def extract_nationality(text):
    return re.findall(r'\b(WARGANEGARA|WARGA ASING|CITIZEN|NON-CITIZEN)\b', text, re.I)

# === 马来西亚地点白名单（防止误合并）===
MALAYSIA_LOCATIONS = {
    "KUALA LUMPUR", "PETALING JAYA", "SELANGOR", "JOHOR", "JOHOR BAHRU",
    "PENANG", "GEORGETOWN", "ALOR SETAR", "KELANTAN", "TERENGGANU",
    "MELAKA", "KUCHING", "KOTA KINABALU", "LABUAN", "SABAH", "SARAWAK"
}

# ✅ 主函数：提取所有 PII（带过滤）
def extract_all_pii(text):
    results = []

    # --- 1. NER 提取（细粒度）---
    try:
        ner_results = ner_pipeline(text)
        tokens = []
        for ent in ner_results:
            word = ent["word"]
            entity = ent["entity"].replace("B-", "").replace("I-", "")
            # 判断是否是新词开始
            is_new_word = word.startswith("▁") or (not word.startswith("##") and not word.startswith("▁"))
            clean_word = word.replace("##", "").replace("▁", "")
            tokens.append({
                "word": clean_word,
                "entity": entity,
                "is_new_word": is_new_word
            })

        current_word = ""
        current_label = ""

        for tok in tokens:
            # 如果是新词，结束当前词
            if current_label and tok["is_new_word"]:
                if current_word:
                    results.append((current_label, current_word))
                current_word = tok["word"]
                current_label = tok["entity"]
            # 如果是延续（## 或 ▁ 开头），且实体类型相同，则拼接
            elif current_label == tok["entity"]:
                current_word += tok["word"]
            # 不同类型，先结束旧的，再开新的
            else:
                if current_word:
                    results.append((current_label, current_word))
                current_word = tok["word"]
                current_label = tok["entity"]

        # 结束最后一个
        if current_word:
            results.append((current_label, current_word))

    except Exception as e:
        print(f"[WARN] NER 提取失败: {e}")

    # --- 2. 正则规则补充 ---
    extractors = {
        "IC": extract_ic,
        "Email": extract_email,
        "DOB": extract_dob,
        "Bank Account": extract_bank_account,
        "Passport": extract_passport,
        "Phone": extract_phone,
        "Money": extract_money,
        "Gender": extract_gender,
        "Nationality": extract_nationality,
        "Name": lambda t: [],  # 可扩展：姓名规则
    }

    for label, func in extractors.items():
        matches = func(text)
        for match in matches:
            results.append((label, match.strip()))

    # --- 3. 去重 + 过滤非敏感词 ---
    seen = set()
    filtered_results = []
    for label, value in results:
        clean_val = value.strip().lower()
        # 跳过空值和忽略词
        if not clean_val or clean_val in IGNORE_WORDS:
            continue
        if clean_val not in seen:
            seen.add(clean_val)
            filtered_results.append((label, value.strip()))  # 保留原始大小写

    return filtered_results