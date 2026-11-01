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
        "user@example.com",
        "a.b+c%d-e_f@sub.example.co.uk",
        "USER@EXAMPLE.COM",
        "x@y.z",
        "  user@example.com  ",
    ],
)
def test_validate_email_valid(email):
    result = validate_email(email)
    assert result == email.strip()


def test_validate_email_returns_stripped():
    assert validate_email("  a@b.co  ") == "a@b.co"


@pytest.mark.parametrize("email", [None, 123, 1.5, [], b"a@b.co"])
def test_validate_email_non_string(email):
    with pytest.raises(InvalidEmailError, match="email must be a string"):
        validate_email(email)


@pytest.mark.parametrize("email", ["", "   ", "\t\n"])
def test_validate_email_empty(email):
    with pytest.raises(InvalidEmailError, match="email must not be empty"):
        validate_email(email)


def test_validate_email_too_long():
    local = "a" * 250
    email = local + "@b.co"
    assert len(email) > 254
    with pytest.raises(InvalidEmailError, match="email exceeds 254 characters"):
        validate_email(email)


def test_validate_email_exactly_254_chars():
    # Build a valid email of exactly 254 characters.
    domain = "b.co"
    local_len = 254 - len(domain) - 1
    email = "a" * local_len + "@" + domain
    assert len(email) == 254
    assert validate_email(email) == email


def test_validate_email_255_chars():
    domain = "b.co"
    local_len = 255 - len(domain) - 1
    email = "a" * local_len + "@" + domain
    assert len(email) == 255
    with pytest.raises(InvalidEmailError, match="email exceeds 254 characters"):
        validate_email(email)


@pytest.mark.parametrize(
    "email",
    [
        "no-at-sign.com",
        "two@@example.com",
        "user@example",
        "user@.com",
        "user@example.",
        "@example.com",
        "user@",
        "user name@example.com",
        "user@exa mple.com",
    ],
)
def test_validate_email_invalid_shape(email):
    with pytest.raises(InvalidEmailError, match="invalid email address"):
        validate_email(email)


@pytest.mark.parametrize(
    "email",
    [
        ".user@example.com",
        "user.@example.com",
        "us..er@example.com",
    ],
)
def test_validate_email_invalid_local_dots(email):
    with pytest.raises(
        InvalidEmailError, match="email local part has invalid dot placement"
    ):
        validate_email(email)


@pytest.mark.parametrize(
    "email",
    [
        "user@-example.com",
        "user@example-.com",
        "user@sub.-example.com",
        "user@sub.example-.com",
    ],
)
def test_validate_email_domain_hyphen(email):
    with pytest.raises(
        InvalidEmailError,
        match="email domain labels must not start or end with a hyphen",
    ):
        validate_email(email)


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


@pytest.mark.parametrize("phone", [None, 1234567890, 1.5, [], b"1234567890"])
def test_validate_phone_non_string(phone):
    with pytest.raises(InvalidPhoneError, match="phone must be a string"):
        validate_phone(phone)


@pytest.mark.parametrize("phone", ["", "   ", "\t"])
def test_validate_phone_empty(phone):
    with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
        validate_phone(phone)


@pytest.mark.parametrize(
    "phone",
    [
        "123456789a",
        "1234567890x",
        "(123)4567890",
        "123.456.7890",
        "123_456_7890",
    ],
)
def test_validate_phone_invalid_character(phone):
    with pytest.raises(InvalidPhoneError, match="invalid character in phone number"):
        validate_phone(phone)


@pytest.mark.parametrize(
    "phone",
    [
        "123+4567890",
        "1+234567890",
        "1234567890+",
        "+1+234567890",
    ],
)
def test_validate_phone_plus_not_at_start(phone):
    with pytest.raises(
        InvalidPhoneError, match="a plus prefix is only allowed at the start"
    ):
        validate_phone(phone)


@pytest.mark.parametrize(
    "phone",
    [
        "123456789",          # 9 digits
        "1234567890123456",   # 16 digits
        "+123456789",         # 9 digits with plus
        "+1234567890123456",  # 16 digits with plus
        "1 2 3 4 5 6 7 8 9",  # 9 digits with spaces
    ],
)
def test_validate_phone_wrong_length(phone):
    with pytest.raises(InvalidPhoneError, match="phone must contain 10-15 digits"):
        validate_phone(phone)


def test_validate_phone_boundary_10_digits():
    assert validate_phone("1234567890") == "1234567890"


def test_validate_phone_boundary_15_digits():
    assert validate_phone("123456789012345") == "123456789012345"


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "username",
    [
        "abc",
        "a_b",
        "user123",
        "A" * 20,
        "a" + "b" * 19,
        "abc_def",
    ],
)
def test_validate_username_valid(username):
    assert validate_username(username) == username


@pytest.mark.parametrize("username", [None, 123, 1.5, [], b"abc"])
def test_validate_username_non_string(username):
    with pytest.raises(ValidationError, match="username must be a string"):
        validate_username(username)


@pytest.mark.parametrize("username", ["", "a", "ab", "a" * 21])
def test_validate_username_length(username):
    with pytest.raises(
        ValidationError, match="username must be 3-20 characters long"
    ):
        validate_username(username)


def test_validate_username_boundary_3():
    assert validate_username("abc") == "abc"


def test_validate_username_boundary_20():
    username = "a" * 20
    assert validate_username(username) == username


@pytest.mark.parametrize(
    "username",
    [
        "ab-cd",
        "ab cd",
        "ab.cd",
        "abc!",
        "abc@def",
    ],
)
def test_validate_username_invalid_chars(username):
    with pytest.raises(
        ValidationError,
        match="username must contain only letters, digits or underscores",
    ):
        validate_username(username)


@pytest.mark.parametrize("username", ["1abc", "123", "_abc", "9_9"])
def test_validate_username_must_start_with_letter(username):
    with pytest.raises(
        ValidationError, match="username must start with a letter"
    ):
        validate_username(username)


@pytest.mark.parametrize("username", ["ab__cd", "a__b", "abc__"])
def test_validate_username_consecutive_underscores(username):
    with pytest.raises(
        ValidationError, match="username must not contain consecutive underscores"
    ):
        validate_username(username)


# ---------------------------------------------------------------------------
# validate_age
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("age", [0, 1, 50, 129, 130])
def test_validate_age_valid_default_bounds(age):
    assert validate_age(age) == age


def test_validate_age_custom_bounds():
    assert validate_age(18, minimum=18, maximum=65) == 18
    assert validate_age(65, minimum=18, maximum=65) == 65
    assert validate_age(30, minimum=18, maximum=65) == 30


@pytest.mark.parametrize("age", [True, False])
def test_validate_age_rejects_bool(age):
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(age)


@pytest.mark.parametrize("age", [None, 1.5, "10", [], 10.0])
def test_validate_age_non_int(age):
    with pytest.raises(ValidationError, match="age must be an integer"):
        validate_age(age)


def test_validate_age_negative_minimum():
    with pytest.raises(ValidationError, match="minimum must be non-negative"):
        validate_age(5, minimum=-1)


def test_validate_age_minimum_exceeds_maximum():
    with pytest.raises(
        ValidationError, match="minimum must not exceed maximum"
    ):
        validate_age(5, minimum=10, maximum=5)


def test_validate_age_below_minimum():
    with pytest.raises(ValidationError, match="age must be >= 18"):
        validate_age(17, minimum=18, maximum=65)


def test_validate_age_above_maximum():
    with pytest.raises(ValidationError, match="age must be <= 65"):
        validate_age(66, minimum=18, maximum=65)


def test_validate_age_below_default_minimum():
    with pytest.raises(ValidationError, match="age must be >= 0"):
        validate_age(-1)


def test_validate_age_above_default_maximum():
    with pytest.raises(ValidationError, match="age must be <= 130"):
        validate_age(131)


def test_validate_age_minimum_equals_maximum():
    assert validate_age(5, minimum=5, maximum=5) == 5
    with pytest.raises(ValidationError, match="age must be >= 5"):
        validate_age(4, minimum=5, maximum=5)
    with pytest.raises(ValidationError, match="age must be <= 5"):
        validate_age(6, minimum=5, maximum=5)
