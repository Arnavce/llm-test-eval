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
    assert validate_email("a.b+c%d-e_f@sub.example.co.uk") == "a.b+c%d-e_f@sub.example.co.uk"


def test_validate_email_strips_whitespace():
    assert validate_email("  user@example.com  ") == "user@example.com"


def test_validate_email_not_string():
    with pytest.raises(InvalidEmailError, match="email must be a string"):
        validate_email(123)
    with pytest.raises(InvalidEmailError):
        validate_email(None)


def test_validate_email_empty():
    with pytest.raises(InvalidEmailError, match="email must not be empty"):
        validate_email("")
    with pytest.raises(InvalidEmailError, match="email must not be empty"):
        validate_email("   ")


def test_validate_email_too_long():
    local = "a" * 250
    email = local + "@example.com"
    assert len(email) > 254
    with pytest.raises(InvalidEmailError, match="email exceeds 254 characters"):
        validate_email(email)


def test_validate_email_max_length_boundary():
    # Build an exactly-254-char valid email.
    domain = "@example.com"  # 12 chars
    local = "a" * (254 - len(domain))
    email = local + domain
    assert len(email) == 254
    assert validate_email(email) == email


def test_validate_email_invalid_shape():
    for bad in ["plainaddress", "user@", "@example.com", "user@example", "user@@example.com"]:
        with pytest.raises(InvalidEmailError):
            validate_email(bad)


def test_validate_email_multiple_at():
    with pytest.raises(InvalidEmailError):
        validate_email("a@b@c.com")


def test_validate_email_local_dot_placement():
    with pytest.raises(InvalidEmailError, match="invalid dot placement"):
        validate_email(".user@example.com")
    with pytest.raises(InvalidEmailError, match="invalid dot placement"):
        validate_email("user.@example.com")
    with pytest.raises(InvalidEmailError, match="invalid dot placement"):
        validate_email("us..er@example.com")


def test_validate_email_domain_hyphen():
    with pytest.raises(InvalidEmailError, match="hyphen"):
        validate_email("user@-example.com")
    with pytest.raises(InvalidEmailError, match="hyphen"):
        validate_email("user@example-.com")
    with pytest.raises(InvalidEmailError, match="hyphen"):
        validate_email("user@sub.-example.com")


def test_validate_email_domain_hyphen_inside_ok():
    assert validate_email("user@ex-ample.com") == "user@ex-ample.com"


# ---------------------------------------------------------------------------
# validate_phone
# ---------------------------------------------------------------------------

def test_validate_phone_valid():
    assert validate_phone("1234567890") == "1234567890"
    assert validate_phone("+1234567890") == "+1234567890"
    assert validate_phone("123456789012345") == "123456789012345"
    assert validate_phone("+123456789012345") == "+123456789012345"


def test_validate_phone_strips_spaces_and_dashes():
    assert validate_phone("123 456 7890") == "1234567890"
    assert validate_phone("123-456-7890") == "1234567890"
    assert validate_phone("+1 234-567-890") == "+1234567890"


def test_validate_phone_strips_outer_whitespace():
    assert validate_phone("  1234567890  ") == "1234567890"


def test_validate_phone_not_string():
    with pytest.raises(InvalidPhoneError, match="phone must be a string"):
        validate_phone(1234567890)
    with pytest.raises(InvalidPhoneError):
        validate_phone(None)


def test_validate_phone_empty():
    with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
        validate_phone("")
    with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
        validate_phone("   ")


def test_validate_phone_invalid_character():
    with pytest.raises(InvalidPhoneError, match="invalid character"):
        validate_phone("12345abc90")
    with pytest.raises(InvalidPhoneError, match="invalid character"):
        validate_phone("12345.67890")


def test_validate_phone_plus_not_at_start():
    with pytest.raises(InvalidPhoneError, match="plus prefix"):
        validate_phone("123+4567890")


def test_validate_phone_too_short():
    with pytest.raises(InvalidPhoneError, match="10-15 digits"):
        validate_phone("123456789")


def test_validate_phone_too_long():
    with pytest.raises(InvalidPhoneError, match="10-15 digits"):
        validate_phone("1234567890123456")


def test_validate_phone_length_boundaries():
    assert validate_phone("1234567890") == "1234567890"  # 10 digits
    assert validate_phone("123456789012345") == "123456789012345"  # 15 digits


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------

def test_validate_username_valid():
    assert validate_username("abc") == "abc"
    assert validate_username("user_123") == "user_123"
    assert validate_username("A" * 20) == "A" * 20


def test_validate_username_not_string():
    with pytest.raises(ValidationError, match="username must be a string"):
        validate_username(123)
    with pytest.raises(ValidationError):
        validate_username(None)


def test_validate_username_length_boundaries():
    with pytest.raises(ValidationError, match="3-20 characters"):
        validate_username("ab")
    with pytest.raises(ValidationError, match="3-20 characters"):
        validate_username("a" * 21)
    assert validate_username("abc") == "abc"
    assert validate_username("a" * 20) == "a" * 20


def test_validate_username_invalid_characters():
    with pytest.raises(ValidationError, match="only letters, digits or underscores"):
        validate_username("user-name")
    with pytest.raises(ValidationError, match="only letters, digits or underscores"):
        validate_username("user name")
    with pytest.raises(ValidationError, match="only letters, digits or underscores"):
        validate_username("user!")


def test_validate_username_must_start_with_letter():
    with pytest.raises(ValidationError, match="start with a letter"):
        validate_username("1abc")
    with pytest.raises(ValidationError, match="start with a letter"):
        validate_username("_abc")


def test_validate_username_consecutive_underscores():
    with pytest.raises(ValidationError, match="consecutive underscores"):
        validate_username("ab__c")


# ---------------------------------------------------------------------------
# validate_age
# ---------------------------------------------------------------------------

def test_validate_age_valid():
    assert validate_age(0) == 0
    assert validate_age(130) == 130
    assert validate_age(25) == 25


def test_validate_age_custom_bounds():
    assert validate_age(5, minimum=5, maximum=10) == 5
    assert validate_age(10, minimum=5, maximum=10) == 10


def test_validate_age_bool_rejected():
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(True)
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(False)


def test_validate_age_not_int():
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(25.0)
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age("25")
    with pytest.raises(ValidationError):
        validate_age(None)


def test_validate_age_negative_minimum():
    with pytest.raises(ValidationError, match="minimum must be non-negative"):
        validate_age(5, minimum=-1)


def test_validate_age_minimum_exceeds_maximum():
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        validate_age(5, minimum=10, maximum=5)


def test_validate_age_below_minimum():
    with pytest.raises(ValidationError, match="age must be >= 0"):
        validate_age(-1)
    with pytest.raises(ValidationError, match="age must be >= 5"):
        validate_age(4, minimum=5, maximum=10)


def test_validate_age_above_maximum():
    with pytest.raises(ValidationError, match="age must be <= 130"):
        validate_age(131)
    with pytest.raises(ValidationError, match="age must be <= 10"):
        validate_age(11, minimum=5, maximum=10)
