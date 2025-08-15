# OCR/pii_main.py
import re
import os
import json
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from app.resources.dictionaries import NAMES, ORG_NAMES, RACES, STATUS, LOCATIONS, RELIGIONS

# === Delay loading models ===
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
                aggregation_strategy=None
            )
            model_loaded = True
            print("✅ ML model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load ML model: {e}")
            # Fallback to regex-only detection
            model_loaded = False

# === ChatGPT API Integration ===
chatgpt_enabled = False
chatgpt_client = None

def load_chatgpt_client():
    """Initialize ChatGPT client if API key is available"""
    global chatgpt_client, chatgpt_enabled

    try:
        # Try to get API key from environment variable
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("[INFO] OPENAI_API_KEY not found in environment variables")
            print("[INFO] ChatGPT PII detection disabled - using Presidio + NER only")
            return False

        # Try to import OpenAI
        try:
            from openai import OpenAI
        except ImportError:
            print("[WARN] OpenAI library not installed. Install with: pip install openai")
            print("[INFO] ChatGPT PII detection disabled - using Presidio + NER only")
            return False
        # Initialize client
        chatgpt_client = OpenAI(api_key=api_key)
        chatgpt_enabled = True
        print("✅ ChatGPT API client initialized successfully")
        return True
    except Exception as e:
        print(f"[WARN] Failed to initialize ChatGPT client: {e}")
        print("[INFO] ChatGPT PII detection disabled - using Presidio + NER only")
        chatgpt_enabled = False
        return False

def chunk_text_intelligently(text: str, max_chunk_size: int = 3000) -> List[str]:
    """
    Intelligently chunk text to avoid breaking PII entities across chunks

    Args:
        text: Text to chunk
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of text chunks
    """
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    current_chunk = ""

    # Split by paragraphs first, then sentences if needed
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        # If adding this paragraph would exceed chunk size
        if len(current_chunk) + len(paragraph) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # If single paragraph is too long, split by sentences
            if len(paragraph) > max_chunk_size:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                    current_chunk += sentence + ". "
            else:
                current_chunk = paragraph
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

def extract_pii_with_chatgpt(text: str, enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Use ChatGPT to identify PII in text with focus on Malaysian context and intelligent chunking

    Args:
        text: Text to analyze
        enabled_categories: List of enabled PII categories

    Returns:
        List of (label, value) tuples
    """
    if not chatgpt_enabled or not chatgpt_client:
        return []

    if not text or len(text.strip()) < 20:  # Minimum meaningful text length
        return []

    # Default to all categories if none specified
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    # Chunk text if it's too long for ChatGPT
    text_chunks = chunk_text_intelligently(text, max_chunk_size=3000)
    all_results = []

    print(f"[ChatGPT] Processing {len(text_chunks)} text chunks")

    for chunk_idx, chunk in enumerate(text_chunks):
        try:
            # Create enhanced category-specific prompt for financial documents
            categories_desc = {
                "NAMES": "Personal names (Malaysian names like 'Ahmad bin Ali', 'WONG JUN KEAT', 'Ramba anak Sumping')",
                "RACES": "Ethnic/racial information (Malay, Chinese, Indian, Iban, Dayak, etc.)",
                "ORG_NAMES": "Company and organization names (banks, corporations, government agencies)",
                "STATUS": "Marital/social status (married, single, etc.)",
                "LOCATIONS": "Geographic locations and addresses (Malaysian cities, states, postal codes)",
                "RELIGIONS": "Religious affiliations",
                "TRANSACTION NAME": "Transaction descriptions and references"
            }

            enabled_desc = [f"- {cat}: {categories_desc.get(cat, cat)}" for cat in enabled_categories if cat in categories_desc]
            categories_text = "\n".join(enabled_desc)

            # Enhanced prompt for better financial document detection
            prompt = f"""You are a PII detection expert specializing in Malaysian financial and identity documents.

Analyze the following text and identify PII entities. Focus on these categories:
{categories_text}

CRITICAL DETECTION RULES:
1. ALWAYS detect these sensitive items regardless of category settings:
   - IC numbers (format: 123456-78-9012 or similar)
   - Account numbers (long digit sequences: 1234567890123456)
   - Phone numbers (+60123456789, 03-77855409, etc.)
   - Email addresses
   - Credit card numbers

2. For Malaysian context:
   - Names: Look for Malaysian naming patterns (bin, binti, anak, Chinese names like WONG, LIM, TAN)
   - Locations: Malaysian cities (KUALA LUMPUR, PETALING JAYA, JOHOR BAHRU, etc.)
   - Banks: Malaysian bank names (Maybank, CIMB, Public Bank, etc.)

3. IGNORE these document artifacts:
   - MALAYSIA, KAD PENGENALAN, IDENTITY CARD, LELAKI, PEREMPUAN, WARGANEGARA
   - COPY, CONFIDENTIAL, SPECIMEN, SAMPLE
   - Form labels and headers

4. For bank statements specifically:
   - Account holder names
   - Account numbers (typically 10-16 digits)
   - Transaction reference numbers
   - Branch codes and addresses
   - Phone numbers and contact details

Return ONLY a JSON array with this exact format:
[
  {{"category": "NAMES", "value": "WONG JUN KEAT", "confidence": 0.95}},
  {{"category": "ACCOUNT", "value": "1234567890123456", "confidence": 1.0}},
  {{"category": "PHONE", "value": "03-77855409", "confidence": 0.9}}
]

Text to analyze (chunk {chunk_idx + 1}/{len(text_chunks)}):
{chunk}"""

            # Call ChatGPT API
            response = chatgpt_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a PII detection expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent results
            )

            # Parse response
            response_text = response.choices[0].message.content.strip()

            # Extract JSON from response (handle cases where GPT adds extra text)
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1

            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                pii_data = json.loads(json_text)

                # Convert to our format and filter by confidence
                chunk_results = []
                for item in pii_data:
                    if isinstance(item, dict) and 'category' in item and 'value' in item:
                        category = item['category']
                        value = item['value'].strip()
                        confidence = item.get('confidence', 0.8)

                        # Only include high-confidence results
                        if confidence >= 0.7 and value:
                            chunk_results.append((category, value))

                all_results.extend(chunk_results)
                print(f"[ChatGPT] Chunk {chunk_idx + 1}: Found {len(chunk_results)} PII items")
            else:
                print(f"[WARN] ChatGPT chunk {chunk_idx + 1}: No valid JSON in response")

        except json.JSONDecodeError as e:
            print(f"[WARN] ChatGPT chunk {chunk_idx + 1}: JSON parsing failed: {e}")
            continue
        except Exception as e:
            print(f"[WARN] ChatGPT chunk {chunk_idx + 1}: Processing failed: {e}")
            continue

    print(f"[ChatGPT] Total found across all chunks: {len(all_results)} PII items")
    return all_results

def validate_pii_with_chatgpt_context(text: str, candidate_pii: List[Tuple[str, str]], enabled_categories: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Stage 2: Use ChatGPT to validate and filter PII candidates based on context

    Args:
        text: Original full text for context
        candidate_pii: List of (label, value) tuples from Stage 1 detection
        enabled_categories: List of enabled PII categories

    Returns:
        Filtered list of (label, value) tuples that are truly PII
    """
    if not chatgpt_enabled or not chatgpt_client:
        print("[INFO] ChatGPT contextual validation skipped (not enabled)")
        return candidate_pii

    if not candidate_pii:
        print("[INFO] No PII candidates to validate")
        return []

    if len(text.strip()) < 50:
        print("[INFO] Text too short for contextual validation")
        return candidate_pii

    print(f"[ChatGPT-VALIDATION] Starting contextual validation of {len(candidate_pii)} candidates")

    try:
        # Prepare candidate list for ChatGPT analysis
        candidates_text = "\n".join([f"- {label}: '{value}'" for label, value in candidate_pii])

        # Create context-aware validation prompt
        prompt = f"""You are a PII validation expert specializing in Malaysian documents.

I have detected potential PII entities in a document, but need your help to filter out false positives and validate which items are truly sensitive personal information that should be masked.

ORIGINAL DOCUMENT CONTEXT:
{text[:2000]}{"..." if len(text) > 2000 else ""}

DETECTED PII CANDIDATES:
{candidates_text}

VALIDATION RULES:
1. **ALWAYS KEEP as PII (regardless of context)**:
   - IC numbers (123456-78-9012 format)
   - Phone numbers (+60123456789, 03-77855409)
   - Email addresses
   - Credit card numbers
   - Bank account numbers (long digit sequences)

2. **EVALUATE CONTEXTUALLY**:
   - Personal names: Keep if referring to individuals (account holders, customers)
   - Organization names: Remove if just company headers/logos (PUBLIC BANK, MAYBANK)
   - Locations: Keep if personal addresses, remove if just branch locations
   - Amounts: Remove if transaction amounts, keep if account numbers
   - Dates: Remove if transaction dates, keep if birth dates

3. **MALAYSIAN CONTEXT**:
   - Names like "WONG JUN KEAT", "Ahmad bin Ali" are personal names → KEEP
   - Bank names like "PUBLIC BANK", "MAYBANK" in headers → REMOVE
   - Cities like "KUALA LUMPUR" in addresses → KEEP, in branch info → REMOVE
   - "MALAYSIA" as country name → REMOVE

4. **DOCUMENT ARTIFACTS TO REMOVE**:
   - Bank names in headers/letterheads
   - Branch names and codes
   - Transaction categories/descriptions
   - Currency symbols and amounts
   - Form labels and instructions

Return ONLY a JSON array of items that should be KEPT (truly sensitive PII):
[
  {{"label": "NAMES", "value": "WONG JUN KEAT", "reason": "Personal account holder name"}},
  {{"label": "IC", "value": "123456-78-9012", "reason": "Personal identification number"}},
  {{"label": "PHONE", "value": "03-77855409", "reason": "Personal contact number"}}
]

Focus on protecting individual privacy while removing corporate/institutional information."""

        # Call ChatGPT for validation
        response = chatgpt_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a PII validation expert. Return only valid JSON with items that truly need privacy protection."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.1
        )
        response_text = response.choices[0].message.content.strip()
        # Extract JSON from response
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            validated_data = json.loads(json_text)
            # Convert back to our format
            validated_results = []
            for item in validated_data:
                if isinstance(item, dict) and 'label' in item and 'value' in item:
                    label = item['label']
                    value = item['value'].strip()
                    reason = item.get('reason', 'Validated by ChatGPT')
                    if value:
                        validated_results.append((label, value))
                        print(f"[ChatGPT-VALIDATION] KEEP: {label} = '{value}' ({reason})")

            # Show what was filtered out
            original_values = {value.lower() for _, value in candidate_pii}
            validated_values = {value.lower() for _, value in validated_results}
            filtered_out = original_values - validated_values

            if filtered_out:
                print(f"[ChatGPT-VALIDATION] FILTERED OUT: {len(filtered_out)} items")
                for value in list(filtered_out)[:5]:  # Show first 5
                    print(f"[ChatGPT-VALIDATION] REMOVED: '{value}' (document artifact)")
                if len(filtered_out) > 5:
                    print(f"[ChatGPT-VALIDATION] ... and {len(filtered_out) - 5} more")

            print(f"[ChatGPT-VALIDATION] Final result: {len(validated_results)}/{len(candidate_pii)} candidates validated as true PII")
            return validated_results
        else:
            print("[WARN] ChatGPT validation: No valid JSON in response")
            return candidate_pii

    except json.JSONDecodeError as e:
        print(f"[WARN] ChatGPT validation JSON parsing failed: {e}")
        return candidate_pii
    except Exception as e:
        print(f"[WARN] ChatGPT validation failed: {e}")
        return candidate_pii

def combine_pii_results(presidio_results: List[Tuple[str, str]],
                       ner_results: List[Tuple[str, str]],
                       chatgpt_results: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Combine results from multiple PII detection methods using enhanced consensus mechanism
    Args:
        presidio_results: Results from Presidio/regex detection
        ner_results: Results from NER model (may be empty if failed)
        chatgpt_results: Results from ChatGPT
    Returns:
        Combined and deduplicated results
    """
    # Track which methods provided results
    methods_used = []
    if presidio_results:
        methods_used.append("Presidio/Regex")
    if ner_results:
        methods_used.append("NER")
    if chatgpt_results:
        methods_used.append("ChatGPT")
    print(f"[CONSENSUS] Active detection methods: {', '.join(methods_used)}")
    # Combine all results
    all_results = presidio_results + ner_results + chatgpt_results
    if not all_results:
        print("[CONSENSUS] No PII detected by any method")
        return []
    # Group by normalized value for deduplication
    value_groups = {}
    for label, value in all_results:
        normalized_value = value.strip().lower()
        if normalized_value not in value_groups:
            value_groups[normalized_value] = []
        value_groups[normalized_value].append((label, value))
    # Apply enhanced consensus logic
    final_results = []
    for normalized_value, candidates in value_groups.items():
        if len(candidates) == 1:
            # Single detection - include it
            label, value = candidates[0]
            final_results.append((label, value))
        else:
            # Multiple detections - use consensus with priority
            # Priority: ChatGPT > Presidio/Regex > NER for conflicting labels
            label_votes = {}
            label_sources = {}
            for label, value in candidates:
                if label not in label_votes:
                    label_votes[label] = 0
                    label_sources[label] = []
                label_votes[label] += 1
                # Determine source method (approximate)
                if (label, value) in chatgpt_results:
                    label_sources[label].append("ChatGPT")
                elif (label, value) in presidio_results:
                    label_sources[label].append("Presidio")
                else:
                    label_sources[label].append("NER")
            # Choose best label with priority weighting
            best_label = None
            best_score = 0
            for label, votes in label_votes.items():
                score = votes
                # Boost score based on source reliability
                if "ChatGPT" in label_sources[label]:
                    score += 2  # ChatGPT gets priority for context awareness
                if "Presidio" in label_sources[label]:
                    score += 1  # Regex patterns are reliable
                if score > best_score:
                    best_score = score
                    best_label = label
            # Get the best value (prefer original case)
            best_value = next(value for label, value in candidates if label == best_label)
            final_results.append((best_label, best_value))

    print(f"[CONSENSUS] Combined {len(all_results)} detections into {len(final_results)} final results")
    return final_results

# === General ignored words (non-sensitive, no encryption required) ===
IGNORE_WORDS = {
    "malaysia", "mykad", "identity", "card", "kad", "pengenalan",
    "warganegara", "lelaki", "perempuan", "bujang", "kawin",
    "lel", "per", "male", "female", "citizen", "not citizen"
}

# === Enhanced regular expression extractor ===
def extract_ic(text):
    """Extract Malaysian Identity Card Number"""
    patterns = [
        r"\b\d{6}-\d{2}-\d{4}\b", 
        r"\b\d{12}\b",            
        r"\b\d{6}\s\d{2}\s\d{4}\b"
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))

    # Verify IC number format
    validated_matches = []
    for match in matches:
        clean_ic = re.sub(r'[-\s]', '', match)
        if len(clean_ic) == 12 and validate_malaysian_ic(clean_ic):
            validated_matches.append(match)

    return validated_matches

def extract_email(text):
    """Extract email addresses"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def extract_dob(text):
    """Extract date of birth"""
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
    """Retrieve bank account number"""
    patterns = [
        r"\b\d{10,16}\b",                 
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4,8}\b",
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        # Filter out matches that might be phone numbers or other numbers
        for match in found:
            clean_num = re.sub(r'[-\s]', '', match)
            if 10 <= len(clean_num) <= 16 and not is_phone_number(clean_num):
                matches.append(match)
    return matches

def extract_phone(text):
    """Extract phone number (Malaysian format)"""
    patterns = [
        r'\+60\d{1,2}[-\s]?\d{7,8}',       
        r'\b01\d[-\s]?\d{7,8}\b',          
        r'\b03[-\s]?\d{8}\b',              
        r'\b0[4-9]\d[-\s]?\d{7}\b',        
        r'\b\d{3}[-\s]?\d{7,8}\b',         
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_phone_number(match):
                matches.append(match)
    return matches

def extract_money(text):
    pattern = r'\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\b'
    
    raw_matches = re.findall(pattern, text)
    filtered_matches = []
    seen = set()

    for match in raw_matches:
        try:
            normalized = match.replace(',', '')
            num = float(normalized)
            if 0.01 <= num <= 10_000_000 and match not in seen:
                filtered_matches.append(match)
                seen.add(match)
        except ValueError:
            continue

    return filtered_matches

def extract_gender(text):
    return re.findall(r'\b(LELAKI|PEREMPUAN|MALE|FEMALE)\b', text, re.I)

def extract_nationality(text):
    return re.findall(r'\b(WARGANEGARA|WARGA ASING|CITIZEN|NON-CITIZEN)\b', text, re.I)

def extract_passport(text):
    # Match passport number format: 1 letter + 7 numbers, or similar format
    patterns = [
        r'\b[A-Z]\d{7,8}\b',      # H12345678 or H1234567
        r'\b[A-Z]{1,2}\d{6,7}\b', # HK1234567 or A1234567
        r'\b\d{8,9}[A-Z]\b'       # 12345678A
    ]
    
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    
    return matches

def extract_credit_card(text):
    """Extract credit card numbers"""
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
    """Extract Malaysia Address"""
    patterns = [
        r"\b\d+[A-Za-z]?,?\s+[A-Za-z\s]+,\s*\d{5}\s+[A-Za-z\s]+\b",
        r"\b[A-Za-z\s]+,\s*\d{5}\s+[A-Za-z\s]+,\s*[A-Za-z\s]+\b",
        r"\bNo\.?\s*\d+[A-Za-z]?,?\s+[A-Za-z\s]+,\s*\d{5}\b",   
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    return matches

def extract_vehicle_registration(text):
    """Extract license plate number"""
    patterns = [
        r"\b[A-Z]{1,3}\s?\d{1,4}\s?[A-Z]?\b",
        r"\b[A-Z]{2}\d{4}[A-Z]\b",            
    ]
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        for match in found:
            if validate_vehicle_plate(match):
                matches.append(match)
    return matches

# === Validation Function ===
def validate_malaysian_ic(ic_number: str) -> bool:
    if len(ic_number) != 12 or not ic_number.isdigit():
        return False

    try:
        # Verify that the date of birth is legitimate
        year = int(ic_number[:2])
        month = int(ic_number[2:4])
        day = int(ic_number[4:6])
        full_year = 2000 + year if year <= 30 else 1900 + year
        datetime(full_year, month, day)
    except ValueError:
        return False
    return True

def validate_credit_card(cc_number):
    """Validating credit card numbers using the Luhn algorithm"""
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
    """Validate phone number format"""
    clean_phone = re.sub(r'[\s+\-]', '', phone)

    # Malaysia Mobile Number Verification
    if clean_phone.startswith('60'):
        clean_phone = clean_phone[2:]

    # mobile patterns
    mobile_patterns = [
        r'^01[0-9]\d{7,8}$',
        r'^03\d{8}$',      
        r'^0[4-9]\d{7,8}$',
    ]

    for pattern in mobile_patterns:
        if re.match(pattern, clean_phone):
            return True

    return False

def validate_vehicle_plate(plate):
    """Verify license plate number format"""
    clean_plate = re.sub(r'\s', '', plate.upper())

    # Malaysian license plate format
    patterns = [
        r'^[A-Z]{1,3}\d{1,4}[A-Z]?$',\
        r'^[A-Z]{2}\d{4}[A-Z]$',       
    ]

    for pattern in patterns:
        if re.match(pattern, clean_plate):
            return True

    return False

def is_phone_number(number_str):
    """Check if a numeric string is possibly a phone number"""
    clean_num = re.sub(r'[\s-]', '', number_str)
    return len(clean_num) in [10, 11, 12] and (clean_num.startswith('01') or clean_num.startswith('03'))

# === Malaysia location whitelist (to prevent accidental merging) ===
MALAYSIA_LOCATIONS = {
    "KUALA LUMPUR", "PETALING JAYA", "SELANGOR", "JOHOR", "JOHOR BAHRU",
    "PENANG", "GEORGETOWN", "ALOR SETAR", "KELANTAN", "TERENGGANU",
    "MELAKA", "KUCHING", "KOTA KINABALU", "LABUAN", "SABAH", "SARAWAK"
}

def extract_from_dictionaries(text, enabled_categories=None):
    """
    Extracts PII from a dictionary, supporting selective category filtering

    Args:
        text: The text to be analyzed
        enabled_categories: A list of enabled selective PII categories

    Returns:
        list: [(label, value), ...] 
    """
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    print(f"[DEBUG] 字典提取，启用类别: {enabled_categories}")
    print("[DEBUG] 原始文本：", text)

    results = []
    text_lower = text.lower()

    # 1. Full name matching (highest priority)
    if "NAMES" in enabled_categories:
        for name in NAMES:
            if name.lower() in text_lower:
                # Make sure it matches the entire word, not a partial one
                pattern = r'\b' + re.escape(name.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("NAMES", name))
                    print(f"[DEBUG] Find full name: {name}")

    # 2. Full organization name matching
    if "ORG_NAMES" in enabled_categories:
        for org in ORG_NAMES:
            if org.lower() in text_lower:
                pattern = r'\b' + re.escape(org.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("ORG_NAMES", org))
                    print(f"[DEBUG] Find the organization name: {org}")

    # 3. Race Matching
    if "RACES" in enabled_categories:
        for race in RACES:
            if race.lower() in text_lower:
                pattern = r'\b' + re.escape(race.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("RACES", race))
                    print(f"[DEBUG] Find the race: {race}")

    # 4. State Matching
    if "STATUS" in enabled_categories:
        for status in STATUS:
            if status.lower() in text_lower:
                pattern = r'\b' + re.escape(status.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("STATUS", status))
                    print(f"[DEBUG] Found status: {status}")

    # 5. Location Matching
    if "LOCATIONS" in enabled_categories:
        for location in LOCATIONS:
            if location.lower() in text_lower:
                # Locations may contain special characters, use a looser match
                if location.lower() in text_lower:
                    results.append(("LOCATIONS", location))
                    print(f"[DEBUG] Find the location: {location}")

    # 6. Religious Match
    if "RELIGIONS" in enabled_categories:
        for religion in RELIGIONS:
            if religion.lower() in text_lower:
                pattern = r'\b' + re.escape(religion.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    results.append(("RELIGIONS", religion))
                    print(f"[DEBUG] Find religion: {religion}")

    print(f"[DEBUG] Dictionary matching results: Found {len(results)} PII items")
    for label, value in results:
        print(f"[DEBUG]   - {label}: {value}")
    return results

# ✅ Optional PII Category Definitions
SELECTABLE_PII_CATEGORIES = {
    "NAMES": "Personal names and identities",
    "RACES": "Ethnic and racial information",
    "ORG_NAMES": "Company and organization names",
    "STATUS": "Marital and social status",
    "LOCATIONS": "Geographic locations and addresses",
    "RELIGIONS": "Religious affiliations"
}

# ✅ Non-selective PII categories (always masked)
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

# ✅ Main function: Extract all PII (with selective filtering + ChatGPT enhancement)
def extract_all_pii(text, enabled_categories=None):
    """
    Extract PII, support selective category filtering, and integrate ChatGPT enhanced detection

    Args:
        text: Text to analyze
        enabled_categories: A list of selective PII categories to enable, such as ["NAMES", "RACES"]
                If None, all categories are enabled.

    Returns:
        list: PII实体列表 [(label, value), ...]
    """
    # If not specified, all optional categories are enabled by default.
    if enabled_categories is None:
        enabled_categories = list(SELECTABLE_PII_CATEGORIES.keys())

    # Initialize ChatGPT client if not already done
    if not chatgpt_enabled:
        load_chatgpt_client()

    print(f"[INFO] PII detection started - Enabled categories: {enabled_categories}")
    print(f"[INFO] Detection methods: NER + Regex + Dictionary + {'ChatGPT' if chatgpt_enabled else 'No ChatGPT'}")

    presidio_regex_results = []
    ner_results = []
    chatgpt_results = []

    # --- 1. NER extraction (fine-grained) with token limit handling ---
    try:
        # Load model if not already loaded
        if not model_loaded:
            load_model()

        if ner_pipeline is not None:
            # Handle token limit by chunking text for NER
            text_length = len(text.split())
            max_tokens = 300  # Conservative limit for NER model (model limit is ~512 tokens)

            if text_length > max_tokens:
                print(f"[NER] Text too long ({text_length} tokens), chunking for NER processing...")
                # Split text into smaller chunks for NER
                words = text.split()
                chunk_size = max_tokens
                ner_raw_results = []

                for i in range(0, len(words), chunk_size):
                    chunk_words = words[i:i + chunk_size]
                    chunk_text = " ".join(chunk_words)

                    # Additional safety check - if chunk is still too long, skip it
                    if len(chunk_text.split()) > max_tokens:
                        print(f"[WARN] NER chunk {i//chunk_size + 1} still too long, skipping")
                        continue

                    try:
                        chunk_results = ner_pipeline(chunk_text)
                        ner_raw_results.extend(chunk_results)
                        print(f"[NER] Processed chunk {i//chunk_size + 1}: {len(chunk_results)} entities")
                    except Exception as chunk_e:
                        print(f"[WARN] NER chunk {i//chunk_size + 1} failed: {chunk_e}")
                        continue
            else:
                ner_raw_results = ner_pipeline(text)
        else:
            print("[WARN] NER model not available, using regex-only detection")
            ner_raw_results = []
        tokens = []
        for ent in ner_raw_results:
            word = ent["word"]
            entity = ent["entity"].replace("B-", "").replace("I-", "")
            # Determine whether it is the beginning of a new word
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
            # If it is a new word, end the current word
            if current_label and tok["is_new_word"]:
                if current_word:
                    ner_results.append((current_label, current_word))
                current_word = tok["word"]
                current_label = tok["entity"]
            # If it is a continuation (starting with ## or ), and the entity types are the same, then concatenate
            elif current_label == tok["entity"]:
                current_word += tok["word"]
            # Different types, end the old one first, then start the new one
            else:
                if current_word:
                    ner_results.append((current_label, current_word))
                current_word = tok["word"]
                current_label = tok["entity"]

        # End the last one
        if current_word:
            ner_results.append((current_label, current_word))

        print(f"[NER] Found {len(ner_results)} entities")

    except Exception as e:
        print(f"[WARN] NER extraction failed: {e}")
        print("[INFO] Continuing with regex and ChatGPT detection methods")

    # --- 2. Enhanced regular rule supplement ---
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
    }

    print(f"[INFO] Start regular extraction, total {len(extractors)} PII types")

    for label, func in extractors.items():
        matches = func(text)
        for match in matches:
            presidio_regex_results.append((label, match.strip()))

    # --- 3. Dictionary matching supplement (selective filtering) ---
    dict_results = extract_from_dictionaries(text, enabled_categories)
    for label, value in dict_results:
        presidio_regex_results.append((label, value))

    print(f"[PRESIDIO/REGEX] Found {len(presidio_regex_results)} entities")

    # --- 4. ChatGPT Enhanced Detection ---
    if chatgpt_enabled and len(text.strip()) >= 20:  # Use ChatGPT for meaningful text
        print("[INFO] Starting ChatGPT enhanced detection...")
        chatgpt_results = extract_pii_with_chatgpt(text, enabled_categories)
        print(f"[ChatGPT] Found {len(chatgpt_results)} entities")
    else:
        if not chatgpt_enabled:
            print("[INFO] ChatGPT detection skipped (not enabled)")
        else:
            print(f"[INFO] ChatGPT detection skipped (text too short: {len(text.strip())} chars < 20)")

    # --- 5. Result merging and consensus mechanism (Stage 1 Complete) ---
    print("[INFO] Stage 1: Apply consensus mechanism to merge test results...")
    stage1_results = combine_pii_results(presidio_regex_results, ner_results, chatgpt_results)

    # --- 6. Deduplication + Filtering Non-sensitive Words (Stage 1 Filtering) ---
    seen = set()
    stage1_filtered = []
    for label, value in stage1_results:
        clean_val = value.strip().lower()
        # Skipping empty values and ignoring words
        if not clean_val or clean_val in IGNORE_WORDS:
            continue
        if clean_val not in seen:
            seen.add(clean_val)
            stage1_filtered.append((label, value.strip()))  # Keep original case

    print(f"[STAGE-1] Initially detected {len(stage1_filtered)} PII candidates")

    # --- 7. Stage 2: ChatGPT Contextual Validation (ADDITIVE, not filtering) ---
    if len(stage1_filtered) > 0 and len(text.strip()) >= 100:  # Only for substantial documents
        print("[INFO] Stage 2: Starting ChatGPT contextual validation...")
        chatgpt_validated = validate_pii_with_chatgpt_context(text, stage1_filtered, enabled_categories)

        # Calculate filtering statistics for logging
        filtered_count = len(stage1_filtered) - len(chatgpt_validated)
        if filtered_count > 0:
            print(f"[STAGE-2] ChatGPT validation: {len(chatgpt_validated)}/{len(stage1_filtered)} items passed validation")
        else:
            print(f"[STAGE-2] ChatGPT validation: All candidates passed validation")

        # IMPORTANT: Use ALL Stage 1 results, not just ChatGPT-validated ones
        # This ensures comprehensive PII protection while benefiting from ChatGPT's accuracy insights
        final_results = stage1_filtered
        print(f"[STAGE-2] Retaining all Stage 1 detection results to ensure comprehensive protection")
    else:
        print("[INFO] Stage 2: Skipping contextual validation (document too short or no candidates)")
        final_results = stage1_filtered

    print(f"[FINAL] Finally detected {len(final_results)} PII items")
    return final_results
