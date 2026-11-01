import pytest

from benchmark.m3_validation import (
    ValidationError,
    InvalidEmailError,
    InvalidPhoneError,
    validate_email,
    validate_phone,
    validate_username,
    validate_age,
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

def test_exception_hierarchy():
    assert issubclass(ValidationError, ValueError)
    assert issubclass(InvalidEmailError, ValidationError)
    assert issubclass(InvalidPhoneError, ValidationError)


# ---------------------------------------------------------------------------
# validate_email
# ---------------------------------------------------------------------------

def test_validate_email_valid():
    assert validate_email("user@example.com") == "user@example.com"
    assert validate_email("a.b+c%d-e@sub.example.co.uk") == "a.b+c%d-e@sub.example.co.uk"


def test_validate_email_strips_whitespace():
    assert validate_email("  user@example.com  ") == "user@example.com"


def test_validate_email_non_string():
    with pytest.raises(InvalidEmailError, match="email must be a string"):
        validate_email(123)


def test_validate_email_none():
    with pytest.raises(InvalidEmailError, match="email must be a string"):
        validate_email(None)


def test_validate_email_empty():
    with pytest.raises(InvalidEmailError, match="email must not be empty"):
        validate_email("")


def test_validate_email_whitespace_only():
    with pytest.raises(InvalidEmailError, match="email must not be empty"):
        validate_email("   ")


def test_validate_email_too_long():
    local = "a" * 240
    email = local + "@example.com"
    assert len(email) > 254
    with pytest.raises(InvalidEmailError, match="email exceeds 254 characters"):
        validate_email(email)


def test_validate_email_exactly_254_chars():
    # Build a valid email of exactly 254 characters.
    domain = "@example.com"  # 12 chars
    local = "a" * (254 - len(domain))
    email = local + domain
    assert len(email) == 254
    assert validate_email(email) == email


def test_validate_email_multiple_at():
    with pytest.raises(InvalidEmailError, match="invalid email address"):
        validate_email("a@b@example.com")


def test_validate_email_no_at():
    with pytest.raises(InvalidEmailError, match="invalid email address"):
        validate_email("userexample.com")


def test_validate_email_no_dot_in_domain():
    with pytest.raises(InvalidEmailError, match="invalid email address"):
        validate_email("user@example")


def test_validate_email_whitespace_inside():
    with pytest.raises(InvalidEmailError, match="invalid email address"):
        validate_email("us er@example.com")


def test_validate_email_local_leading_dot():
    with pytest.raises(InvalidEmailError, match="invalid dot placement"):
        validate_email(".user@example.com")


def test_validate_email_local_trailing_dot():
    with pytest.raises(InvalidEmailError, match="invalid dot placement"):
        validate_email("user.@example.com")


def test_validate_email_local_consecutive_dots():
    with pytest.raises(InvalidEmailError, match="invalid dot placement"):
        validate_email("us..er@example.com")


def test_validate_email_domain_label_leading_hyphen():
    with pytest.raises(InvalidEmailError, match="hyphen"):
        validate_email("user@-example.com")


def test_validate_email_domain_label_trailing_hyphen():
    with pytest.raises(InvalidEmailError, match="hyphen"):
        validate_email("user@example-.com")


def test_validate_email_domain_label_hyphen_in_middle_ok():
    assert validate_email("user@ex-ample.com") == "user@ex-ample.com"


# ---------------------------------------------------------------------------
# validate_phone
# ---------------------------------------------------------------------------

def test_validate_phone_valid_plain():
    assert validate_phone("1234567890") == "1234567890"


def test_validate_phone_valid_with_plus():
    assert validate_phone("+1234567890") == "+1234567890"


def test_validate_phone_valid_with_spaces_and_dashes():
    assert validate_phone("123-456-7890") == "1234567890"
    assert validate_phone("123 456 7890") == "1234567890"
    assert validate_phone("+1 234-567-8901") == "+12345678901"


def test_validate_phone_strips_whitespace():
    assert validate_phone("  1234567890  ") == "1234567890"


def test_validate_phone_min_length_10():
    assert validate_phone("1234567890") == "1234567890"


def test_validate_phone_max_length_15():
    assert validate_phone("123456789012345") == "123456789012345"


def test_validate_phone_too_short():
    with pytest.raises(InvalidPhoneError, match="10-15 digits"):
        validate_phone("123456789")


def test_validate_phone_too_long():
    with pytest.raises(InvalidPhoneError, match="10-15 digits"):
        validate_phone("1234567890123456")


def test_validate_phone_non_string():
    with pytest.raises(InvalidPhoneError, match="phone must be a string"):
        validate_phone(1234567890)


def test_validate_phone_empty():
    with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
        validate_phone("")


def test_validate_phone_whitespace_only():
    with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
        validate_phone("   ")


def test_validate_phone_invalid_character():
    with pytest.raises(InvalidPhoneError, match="invalid character"):
        validate_phone("12345abc90")


def test_validate_phone_plus_not_at_start():
    with pytest.raises(InvalidPhoneError, match="plus prefix"):
        validate_phone("123+4567890")


def test_validate_phone_plus_in_middle():
    with pytest.raises(InvalidPhoneError, match="plus prefix"):
        validate_phone("1234567890+")


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------

def test_validate_username_valid():
    assert validate_username("user_1") == "user_1"
    assert validate_username("abc") == "abc"
    assert validate_username("a" * 20) == "a" * 20


def test_validate_username_non_string():
    with pytest.raises(ValidationError, match="username must be a string"):
        validate_username(123)


def test_validate_username_too_short():
    with pytest.raises(ValidationError, match="3-20 characters"):
        validate_username("ab")


def test_validate_username_too_long():
    with pytest.raises(ValidationError, match="3-20 characters"):
        validate_username("a" * 21)


def test_validate_username_invalid_characters():
    with pytest.raises(ValidationError, match="only letters, digits or underscores"):
        validate_username("user-name")


def test_validate_username_starts_with_digit():
    with pytest.raises(ValidationError, match="must start with a letter"):
        validate_username("1user")


def test_validate_username_starts_with_underscore():
    with pytest.raises(ValidationError, match="must start with a letter"):
        validate_username("_user")


def test_validate_username_consecutive_underscores():
    with pytest.raises(ValidationError, match="consecutive underscores"):
        validate_username("us__er")


def test_validate_username_purely_numeric():
    # Purely numeric passes the regex but fails the leading-letter check.
    with pytest.raises(ValidationError, match="must start with a letter"):
        validate_username("12345")


# ---------------------------------------------------------------------------
# validate_age
# ---------------------------------------------------------------------------

def test_validate_age_valid():
    assert validate_age(0) == 0
    assert validate_age(130) == 130
    assert validate_age(42) == 42


def test_validate_age_custom_bounds():
    assert validate_age(5, minimum=5, maximum=10) == 5
    assert validate_age(10, minimum=5, maximum=10) == 10


def test_validate_age_bool_rejected():
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(True)
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(False)


def test_validate_age_non_int():
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(42.0)
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age("42")


def test_validate_age_negative_minimum():
    with pytest.raises(ValidationError, match="minimum must be non-negative"):
        validate_age(5, minimum=-1)


def test_validate_age_minimum_exceeds_maximum():
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        validate_age(5, minimum=10, maximum=5)


def test_validate_age_below_minimum():
    with pytest.raises(ValidationError, match="age must be >= 0"):
        validate_age(-1)


def test_validate_age_above_maximum():
    with pytest.raises(ValidationError, match="age must be <= 130"):
        validate_age(131)


def test_validate_age_custom_below_minimum():
    with pytest.raises(ValidationError, match="age must be >= 5"):
        validate_age(4, minimum=5, maximum=10)


def test_validate_age_custom_above_maximum():
    with pytest.raises(ValidationError, match="age must be <= 10"):
        validate_age(11, minimum=5, maximum=10)
