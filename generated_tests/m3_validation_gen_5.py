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

@pytest.mark.parametrize(
    "email",
    [
        "a@b.co",
        "user.name+tag@example.com",
        "USER_99%x-y@sub.domain.org",
        "  padded@example.com  ",
    ],
)
def test_validate_email_valid(email):
    result = validate_email(email)
    assert result == email.strip()


def test_validate_email_returns_stripped():
    assert validate_email("  a@b.co  ") == "a@b.co"


def test_validate_email_max_length_boundary():
    # Build an address of exactly 254 characters.
    local = "a" * (254 - len("@example.com"))
    email = local + "@example.com"
    assert len(email) == 254
    assert validate_email(email) == email


def test_validate_email_too_long():
    local = "a" * (255 - len("@example.com"))
    email = local + "@example.com"
    assert len(email) == 255
    with pytest.raises(InvalidEmailError, match="254"):
        validate_email(email)


@pytest.mark.parametrize("bad", [None, 123, 1.5, [], b"a@b.co"])
def test_validate_email_not_string(bad):
    with pytest.raises(InvalidEmailError, match="must be a string"):
        validate_email(bad)


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_validate_email_empty(bad):
    with pytest.raises(InvalidEmailError, match="must not be empty"):
        validate_email(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "plainaddress",
        "a@b",
        "a@@b.co",
        "a@b@c.co",
        "a b@c.co",
        "@b.co",
        "a@.co",
        "a@b..co",
        "a@b.c",
        "a@b.co ",
    ],
)
def test_validate_email_invalid_shape(bad):
    with pytest.raises(InvalidEmailError):
        validate_email(bad)


@pytest.mark.parametrize(
    "bad",
    [
        ".a@b.co",
        "a.@b.co",
        "a..b@c.co",
    ],
)
def test_validate_email_local_dot_placement(bad):
    with pytest.raises(InvalidEmailError, match="dot placement"):
        validate_email(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "a@-b.co",
        "a@b-.co",
        "a@b.-c.co",
        "a@b.c-.co",
    ],
)
def test_validate_email_domain_hyphen(bad):
    with pytest.raises(InvalidEmailError, match="hyphen"):
        validate_email(bad)


# ---------------------------------------------------------------------------
# validate_phone
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phone,expected",
    [
        ("1234567890", "1234567890"),
        ("+1234567890", "+1234567890"),
        ("123456789012345", "123456789012345"),
        ("+123456789012345", "+123456789012345"),
        ("123 456 7890", "1234567890"),
        ("123-456-7890", "1234567890"),
        ("+1 234-567-8901", "+12345678901"),
        ("  1234567890  ", "1234567890"),
    ],
)
def test_validate_phone_valid(phone, expected):
    assert validate_phone(phone) == expected


def test_validate_phone_min_digits():
    assert validate_phone("1234567890") == "1234567890"


def test_validate_phone_max_digits():
    assert validate_phone("123456789012345") == "123456789012345"


def test_validate_phone_too_few_digits():
    with pytest.raises(InvalidPhoneError, match="10-15"):
        validate_phone("123456789")


def test_validate_phone_too_many_digits():
    with pytest.raises(InvalidPhoneError, match="10-15"):
        validate_phone("1234567890123456")


@pytest.mark.parametrize("bad", [None, 1234567890, 1.0, [], b"1234567890"])
def test_validate_phone_not_string(bad):
    with pytest.raises(InvalidPhoneError, match="must be a string"):
        validate_phone(bad)


@pytest.mark.parametrize("bad", ["", "   ", "\t"])
def test_validate_phone_empty(bad):
    with pytest.raises(InvalidPhoneError, match="must not be empty"):
        validate_phone(bad)


@pytest.mark.parametrize("bad", ["12345abcde", "12345.67890", "12345_67890", "12345(67890"])
def test_validate_phone_invalid_character(bad):
    with pytest.raises(InvalidPhoneError, match="invalid character"):
        validate_phone(bad)


@pytest.mark.parametrize("bad", ["123+4567890", "1+234567890", "++1234567890"])
def test_validate_phone_plus_not_at_start(bad):
    with pytest.raises(InvalidPhoneError, match="plus prefix"):
        validate_phone(bad)


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "username",
    [
        "abc",
        "a_b",
        "User123",
        "a" * 20,
        "a" + "b" * 19,
        "A1_b2",
    ],
)
def test_validate_username_valid(username):
    assert validate_username(username) == username


def test_validate_username_min_length():
    assert validate_username("abc") == "abc"


def test_validate_username_max_length():
    name = "a" * 20
    assert validate_username(name) == name


@pytest.mark.parametrize("bad", [None, 123, 1.0, [], b"abc"])
def test_validate_username_not_string(bad):
    with pytest.raises(ValidationError, match="must be a string"):
        validate_username(bad)


@pytest.mark.parametrize("bad", ["", "ab", "a" * 21])
def test_validate_username_length(bad):
    with pytest.raises(ValidationError, match="3-20"):
        validate_username(bad)


@pytest.mark.parametrize("bad", ["ab-cd", "ab cd", "ab.cd", "ab@cd"])
def test_validate_username_invalid_chars(bad):
    with pytest.raises(ValidationError, match="only letters, digits or underscores"):
        validate_username(bad)


@pytest.mark.parametrize("bad", ["1abc", "_abc", "9_9"])
def test_validate_username_must_start_with_letter(bad):
    with pytest.raises(ValidationError, match="start with a letter"):
        validate_username(bad)


@pytest.mark.parametrize("bad", ["ab__c", "a__b", "abc__"])
def test_validate_username_consecutive_underscores(bad):
    with pytest.raises(ValidationError, match="consecutive underscores"):
        validate_username(bad)


# ---------------------------------------------------------------------------
# validate_age
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("age", [0, 1, 65, 129, 130])
def test_validate_age_valid_default_bounds(age):
    assert validate_age(age) == age


def test_validate_age_min_boundary():
    assert validate_age(0) == 0


def test_validate_age_max_boundary():
    assert validate_age(130) == 130


def test_validate_age_custom_bounds():
    assert validate_age(18, minimum=18, maximum=18) == 18
    assert validate_age(50, minimum=10, maximum=60) == 50


@pytest.mark.parametrize("bad", [True, False])
def test_validate_age_rejects_bool(bad):
    with pytest.raises(ValidationError, match="must be an integer"):
        validate_age(bad)


@pytest.mark.parametrize("bad", [None, 1.0, "10", [], 10.5])
def test_validate_age_not_int(bad):
    with pytest.raises(ValidationError, match="must be an integer"):
        validate_age(bad)


def test_validate_age_negative_minimum():
    with pytest.raises(ValidationError, match="minimum must be non-negative"):
        validate_age(5, minimum=-1)


def test_validate_age_min_greater_than_max():
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        validate_age(5, minimum=10, maximum=5)


def test_validate_age_below_minimum():
    with pytest.raises(ValidationError, match="age must be >= 10"):
        validate_age(9, minimum=10)


def test_validate_age_above_maximum():
    with pytest.raises(ValidationError, match="age must be <= 60"):
        validate_age(61, maximum=60)


def test_validate_age_default_below_minimum():
    with pytest.raises(ValidationError, match="age must be >= 0"):
        validate_age(-1)


def test_validate_age_default_above_maximum():
    with pytest.raises(ValidationError, match="age must be <= 130"):
        validate_age(131)
