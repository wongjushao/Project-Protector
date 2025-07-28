# OCR/pii_main.py
import re
from datetime import datetime
from app.resources.dictionaries import NAMES, ORG_NAMES, RACES, STATUS, LOCATIONS, RELIGIONS

# === 延迟加载模型 ===
ner_pipeline = None
model_loaded = False

def load_model():
    """Lazy load the ML model only when needed"""
    global ner_pipeline, model_loaded
    if not model_loaded:
        try:
            print("🔄 Loading ML model for PII detection...")
            from transformers import TFAutoModelForTokenClassification, AutoTokenizer, pipeline

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
            model_loaded = True
            print("✅ ML model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load ML model: {e}")
            # Fallback to regex-only detection
            model_loaded = False

# === 通用忽略词（非敏感，不需加密）===
IGNORE_WORDS = {
    "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
    "warganegara", "lelaki", "perempuan", "bujang", "kawin",
    "lel", "per", "male", "female", "citizen", "not citizen"
}

# === 增强的正则提取器 ===
def extract_ic(text):
    """提取马来西亚身份证号码"""
    patterns = [
        r"\b\d{6}-\d{2}-\d{4}\b",  # 标准格式: 123456-78-9012
        r"\b\d{12}\b",             # 无连字符: 123456789012
        r"\b\d{6}\s\d{2}\s\d{4}\b" # 空格分隔: 123456 78 9012
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))

    # 验证IC号码格式
    validated_matches = []
    for match in matches:
        clean_ic = re.sub(r'[-\s]', '', match)
        if len(clean_ic) == 12 and validate_malaysian_ic(clean_ic):
            validated_matches.append(match)

    return validated_matches

def extract_email(text):
    """提取电子邮件地址"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def extract_dob(text):
    """提取出生日期"""
    patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",      # DD/MM/YYYY or D/M/YYYY
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",      # DD-MM-YYYY
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",      # YYYY-MM-DD
        r"\b\d{1,2}\s+\w+\s+\d{4}\b",     # DD Month YYYY
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    return matches

def extract_bank_account(text):
    """提取银行账户号码"""
    patterns = [
        r"\b\d{10,16}\b",                  # 基本账户号码
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4,8}\b", # 分段格式
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        # 过滤掉可能是电话号码或其他数字的匹配
        for match in found:
            clean_num = re.sub(r'[-\s]', '', match)
            if 10 <= len(clean_num) <= 16 and not is_phone_number(clean_num):
                matches.append(match)
    return matches

def extract_phone(text):
    """提取电话号码（马来西亚格式）"""
    patterns = [
        r'\+60\d{1,2}[-\s]?\d{7,8}',       # 国际格式: +60123456789
        r'\b01\d[-\s]?\d{7,8}\b',          # 手机: 0123456789
        r'\b03[-\s]?\d{8}\b',              # 固话KL: 0312345678
        r'\b0[4-9]\d[-\s]?\d{7}\b',        # 其他州固话
        r'\b\d{3}[-\s]?\d{7,8}\b',         # 简化格式
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_phone_number(match):
                matches.append(match)
    return matches

def extract_money(text):
    # 更严格的金额匹配
    patterns = [
        r'\b\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b',  # e.g. 1,234.56 or 1,234
        r'\b\d{4,}(?:\.\d{1,2})?\b',              # e.g. 1234.5 or 1234.56
        r'\b\d{3}\.\d{1,2}\b'                     # e.g. 123.4 or 123.45
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    unique_matches = list(set(matches))
    filtered_matches = []
    for match in unique_matches:
        try:
            num_value = float(match.replace(',', ''))
            # 只保留合理的金额范围（避免匹配日期、编号等）
            if 10 <= num_value <= 10000000:  # 10到1000万之间
                filtered_matches.append(match)
        except ValueError:
            continue  # 跳过无法转换的值
    return filtered_matches

def extract_gender(text):
    return re.findall(r'\b(LELAKI|PEREMPUAN|MALE|FEMALE)\b', text, re.I)

def extract_nationality(text):
    return re.findall(r'\b(WARGANEGARA|WARGA ASING|CITIZEN|NON-CITIZEN)\b', text, re.I)

def extract_passport(text):
    # 匹配护照号码格式：1个字母+7个数字，或类似格式
    patterns = [
        r'\b[A-Z]\d{7,8}\b',      # H12345678 或 H1234567
        r'\b[A-Z]{1,2}\d{6,7}\b', # HK1234567 或 A1234567
        r'\b\d{8,9}[A-Z]\b'       # 12345678A (反向格式)
    ]
    
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    
    return matches

def extract_credit_card(text):
    """提取信用卡号码"""
    patterns = [
        r"\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",      # Visa
        r"\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", # Mastercard
        r"\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b",             # American Express
        r"\b6(?:011|5\d{2})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", # Discover
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            clean_cc = re.sub(r'[\s-]', '', match)
            if validate_credit_card(clean_cc):
                matches.append(match)
    return matches

def extract_malaysian_address(text):
    """提取马来西亚地址"""
    patterns = [
        r"\b\d+[A-Za-z]?,?\s+[A-Za-z\s]+,\s*\d{5}\s+[A-Za-z\s]+\b",  # 标准地址
        r"\b[A-Za-z\s]+,\s*\d{5}\s+[A-Za-z\s]+,\s*[A-Za-z\s]+\b",    # 无门牌号
        r"\bNo\.?\s*\d+[A-Za-z]?,?\s+[A-Za-z\s]+,\s*\d{5}\b",        # No. 开头
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    return matches

def extract_vehicle_registration(text):
    """提取车牌号码"""
    patterns = [
        r"\b[A-Z]{1,3}\s?\d{1,4}\s?[A-Z]?\b",  # 马来西亚车牌
        r"\b[A-Z]{2}\d{4}[A-Z]\b",             # 新格式
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_vehicle_plate(match):
                matches.append(match)
    return matches

# === 验证函数 ===
def validate_malaysian_ic(ic_number: str) -> bool:
    if len(ic_number) != 12 or not ic_number.isdigit():
        return False

    try:
        # 验证出生日期是否合法
        year = int(ic_number[:2])
        month = int(ic_number[2:4])
        day = int(ic_number[4:6])
        full_year = 2000 + year if year <= 30 else 1900 + year
        datetime(full_year, month, day)
    except ValueError:
        return False

    return True

def validate_credit_card(cc_number):
    """使用Luhn算法验证信用卡号码"""
    def luhn_checksum(card_num):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10

    return luhn_checksum(cc_number) == 0

def validate_phone_number(phone):
    """验证电话号码格式"""
    clean_phone = re.sub(r'[\s-+]', '', phone)

    # 马来西亚手机号码验证
    if clean_phone.startswith('60'):
        clean_phone = clean_phone[2:]

    # 手机号码格式
    mobile_patterns = [
        r'^01[0-9]\d{7,8}$',  # 手机
        r'^03\d{8}$',         # 固话KL
        r'^0[4-9]\d{7,8}$',   # 其他州固话
    ]

    for pattern in mobile_patterns:
        if re.match(pattern, clean_phone):
            return True

    return False

def validate_vehicle_plate(plate):
    """验证车牌号码格式"""
    clean_plate = re.sub(r'\s', '', plate.upper())

    # 马来西亚车牌格式
    patterns = [
        r'^[A-Z]{1,3}\d{1,4}[A-Z]?$',  # 标准格式
        r'^[A-Z]{2}\d{4}[A-Z]$',       # 新格式
    ]

    for pattern in patterns:
        if re.match(pattern, clean_plate):
            return True

    return False

def is_phone_number(number_str):
    """检查数字字符串是否可能是电话号码"""
    clean_num = re.sub(r'[\s-]', '', number_str)
    return len(clean_num) in [10, 11, 12] and (clean_num.startswith('01') or clean_num.startswith('03'))

# === 马来西亚地点白名单（防止误合并）===
MALAYSIA_LOCATIONS = {
    "KUALA LUMPUR", "PETALING JAYA", "SELANGOR", "JOHOR", "JOHOR BAHRU",
    "PENANG", "GEORGETOWN", "ALOR SETAR", "KELANTAN", "TERENGGANU",
    "MELAKA", "KUCHING", "KOTA KINABALU", "LABUAN", "SABAH", "SARAWAK"
}

def extract_from_dictionaries(text, enabled_categories=None):
    """
    从字典中提取PII，支持选择性类别过滤

    Args:
        text: 要分析的文本
        enabled_categories: 启用的选择性PII类别列表

    Returns:
        list: [(label, value), ...] 格式的结果
    """
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    print(f"[DEBUG] 字典提取，启用类别: {enabled_categories}")
    print("[DEBUG] 原始文本：", text[:200])  # 只显示前200字符

    results = []
    text_lower = text.lower()

    # 1. 完整名称匹配（优先级最高）
    if "NAMES" in enabled_categories:
        for name in NAMES:
            if name.lower() in text_lower:
                # 确保是完整单词匹配，不是部分匹配
                pattern = r'\b' + re.escape(name.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("NAMES", name))
                    print(f"[DEBUG] 找到完整姓名: {name}")

    # 2. 完整组织名称匹配
    if "ORG_NAMES" in enabled_categories:
        for org in ORG_NAMES:
            if org.lower() in text_lower:
                pattern = r'\b' + re.escape(org.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("ORG_NAMES", org))
                    print(f"[DEBUG] 找到组织名称: {org}")

    # 3. 种族匹配
    if "RACES" in enabled_categories:
        for race in RACES:
            if race.lower() in text_lower:
                pattern = r'\b' + re.escape(race.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("RACES", race))
                    print(f"[DEBUG] 找到种族: {race}")

    # 4. 状态匹配
    if "STATUS" in enabled_categories:
        for status in STATUS:
            if status.lower() in text_lower:
                pattern = r'\b' + re.escape(status.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("STATUS", status))
                    print(f"[DEBUG] 找到状态: {status}")

    # 5. 地点匹配
    if "LOCATIONS" in enabled_categories:
        for location in LOCATIONS:
            if location.lower() in text_lower:
                # 地点可能包含特殊字符，使用更宽松的匹配
                if location.lower() in text_lower:
                    results.append(("LOCATIONS", location))
                    print(f"[DEBUG] 找到地点: {location}")

    # 6. 宗教匹配
    if "RELIGIONS" in enabled_categories:
        for religion in RELIGIONS:
            if religion.lower() in text_lower:
                pattern = r'\b' + re.escape(religion.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("RELIGIONS", religion))
                    print(f"[DEBUG] 找到宗教: {religion}")

    print(f"[DEBUG] 字典匹配结果: 找到 {len(results)} 个PII项")
    for label, value in results:
        print(f"[DEBUG]   - {label}: {value}")
    return results

# ✅ 选择性PII类别定义
SELECTABLE_PII_CATEGORIES = {
    "NAMES": "Personal names and identities",
    "RACES": "Ethnic and racial information",
    "ORG_NAMES": "Company and organization names",
    "STATUS": "Marital and social status",
    "LOCATIONS": "Geographic locations and addresses",
    "RELIGIONS": "Religious affiliations"
}

# ✅ 非选择性PII类别（始终遮罩）
NON_SELECTABLE_PII_CATEGORIES = {
    "IC": "Malaysian IC numbers",
    "Email": "Email addresses",
    "DOB": "Date of birth",
    "Bank Account": "Bank account numbers",
    "Passport": "Passport numbers",
    "Phone": "Phone numbers",
    "Money": "Financial amounts",
    "Credit Card": "Credit card numbers",
    "Address": "Street addresses",
    "Vehicle Registration": "Vehicle registration numbers"
}

# ✅ 主函数：提取所有 PII（带选择性过滤）
def extract_all_pii(text, enabled_categories=None):
    """
    提取PII，支持选择性类别过滤

    Args:
        text: 要分析的文本
        enabled_categories: 启用的选择性PII类别列表，如 ["NAMES", "RACES"]
                          如果为None，则启用所有类别

    Returns:
        list: PII实体列表 [(label, value), ...]
    """
    # 如果未指定，默认启用所有选择性类别
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    results = []

    # --- 1. NER 提取（细粒度）---
    try:
        # Load model if not already loaded
        if not model_loaded:
            load_model()

        if ner_pipeline is not None:
            ner_results = ner_pipeline(text)
        else:
            print("[WARN] NER model not available, using regex-only detection")
            ner_results = []
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

    # --- 2. 增强的正则规则补充 ---
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
        "Credit Card": extract_credit_card,
        "Address": extract_malaysian_address,
        "Vehicle Registration": extract_vehicle_registration,
        "Name": lambda t: [],  # 可扩展：姓名规则
    }

    print(f"[INFO] 开始正则提取，共 {len(extractors)} 种PII类型")

    for label, func in extractors.items():
        matches = func(text)
        for match in matches:
            results.append((label, match.strip()))

    # --- 3. 字典匹配补充（选择性过滤）---
    dict_results = extract_from_dictionaries(text, enabled_categories)
    for label, value in dict_results:
        results.append((label, value))

    # --- 4. 去重 + 过滤非敏感词 ---
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