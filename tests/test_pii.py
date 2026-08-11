from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_passport_vn() -> None:
    out = scrub_text("Ho chieu cua toi la B1234567")
    assert "B1234567" not in out
    assert "REDACTED_PASSPORT_VN" in out


def test_scrub_address_vn_keywords() -> None:
    out = scrub_text("Toi o so nha 12 đường Nguyễn Huệ, quận 1")
    assert "REDACTED_ADDRESS_VN" in out


def test_no_false_positive_on_plain_english() -> None:
    text = "How do I debug tail latency for an AI API?"
    assert scrub_text(text) == text
