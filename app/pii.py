from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    # Vietnamese passport: 1 letter + 7 digits (e.g. B1234567).
    "passport_vn": r"\b[A-Za-z]\d{7}\b",
    # Vietnamese address keywords: "số nhà 12", "đường Nguyễn Huệ",
    # "phường Bến Nghé", "quận 1", "thành phố Hồ Chí Minh", ...
    "address_vn": (
        r"\b(?:số nhà|số|đường|phố|ngõ|hẻm|phường|xã|quận|huyện|thị xã|thành phố|tp\.?|tỉnh)"
        r"\s+[0-9A-Za-zÀ-ỹ]+(?:\s+[0-9A-Za-zÀ-ỹ]+){0,3}"
    ),
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe, flags=re.IGNORECASE)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
