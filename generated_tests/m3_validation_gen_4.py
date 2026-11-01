import pytest

from benchmark.m3_validation import (
    InvalidEmailError,
    InvalidPhoneError,
    ValidationError,
    validate_age,
    validate_email,
    validate_phone,
    validate_username,
)


class TestExceptionHierarchy:
    def test_invalid_email_error_is_validation_error(self):
        assert issubclass(InvalidEmailError, ValidationError)

    def test_invalid_phone_error_is_validation_error(self):
        assert issubclass(InvalidPhoneError, ValidationError)

    def test_validation_error_is_value_error(self):
        assert issubclass(ValidationError, ValueError)


class TestValidateEmail:
    def test_valid_simple(self):
        assert validate_email("user@example.com") == "user@example.com"

    def test_valid_with_subdomain(self):
        assert validate_email("a.b+c@mail.example.co.uk") == "a.b+c@mail.example.co.uk"

    def test_valid_strips_whitespace(self):
        assert validate_email("  user@example.com  ") == "user@example.com"

    def test_valid_local_with_percent_and_underscore(self):
        assert validate_email("a_b%c@example.com") == "a_b%c@example.com"

    def test_valid_domain_with_hyphen_inside_label(self):
        assert validate_email("user@my-domain.com") == "user@my-domain.com"

    def test_non_string_raises(self):
        with pytest.raises(InvalidEmailError, match="email must be a string"):
            validate_email(123)

    def test_none_raises(self):
        with pytest.raises(InvalidEmailError, match="email must be a string"):
            validate_email(None)

    def test_empty_raises(self):
        with pytest.raises(InvalidEmailError, match="email must not be empty"):
            validate_email("")

    def test_whitespace_only_raises(self):
        with pytest.raises(InvalidEmailError, match="email must not be empty"):
            validate_email("   ")

    def test_too_long_raises(self):
        local = "a" * 240
        email = local + "@example.com"
        assert len(email) > 254
        with pytest.raises(InvalidEmailError, match="email exceeds 254 characters"):
            validate_email(email)

    def test_exactly_254_chars_allowed(self):
        domain = "example.com"
        local = "a" * (254 - len(domain) - 1)
        email = local + "@" + domain
        assert len(email) == 254
        assert validate_email(email) == email

    def test_missing_at_raises(self):
        with pytest.raises(InvalidEmailError, match="invalid email address"):
            validate_email("userexample.com")

    def test_multiple_at_raises(self):
        with pytest.raises(InvalidEmailError, match="invalid email address"):
            validate_email("a@b@example.com")

    def test_no_dot_in_domain_raises(self):
        with pytest.raises(InvalidEmailError, match="invalid email address"):
            validate_email("user@example")

    def test_whitespace_inside_raises(self):
        with pytest.raises(InvalidEmailError, match="invalid email address"):
            validate_email("us er@example.com")

    def test_local_leading_dot_raises(self):
        with pytest.raises(
            InvalidEmailError, match="email local part has invalid dot placement"
        ):
            validate_email(".user@example.com")

    def test_local_trailing_dot_raises(self):
        with pytest.raises(
            InvalidEmailError, match="email local part has invalid dot placement"
        ):
            validate_email("user.@example.com")

    def test_local_consecutive_dots_raises(self):
        with pytest.raises(
            InvalidEmailError, match="email local part has invalid dot placement"
        ):
            validate_email("us..er@example.com")

    def test_domain_label_leading_hyphen_raises(self):
        with pytest.raises(
            InvalidEmailError,
            match="email domain labels must not start or end with a hyphen",
        ):
            validate_email("user@-example.com")

    def test_domain_label_trailing_hyphen_raises(self):
        with pytest.raises(
            InvalidEmailError,
            match="email domain labels must not start or end with a hyphen",
        ):
            validate_email("user@example-.com")

    def test_domain_sub_label_hyphen_raises(self):
        with pytest.raises(
            InvalidEmailError,
            match="email domain labels must not start or end with a hyphen",
        ):
            validate_email("user@sub.-example.com")


class TestValidatePhone:
    def test_valid_plain_digits(self):
        assert validate_phone("1234567890") == "1234567890"

    def test_valid_with_plus(self):
        assert validate_phone("+1234567890") == "+1234567890"

    def test_valid_with_spaces_and_dashes(self):
        assert validate_phone("+1 234-567-8901") == "+12345678901"

    def test_valid_strips_outer_whitespace(self):
        assert validate_phone("  1234567890  ") == "1234567890"

    def test_valid_15_digits(self):
        assert validate_phone("123456789012345") == "123456789012345"

    def test_valid_plus_15_digits(self):
        assert validate_phone("+123456789012345") == "+123456789012345"

    def test_non_string_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must be a string"):
            validate_phone(1234567890)

    def test_none_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must be a string"):
            validate_phone(None)

    def test_empty_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
            validate_phone("")

    def test_whitespace_only_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must not be empty"):
            validate_phone("   ")

    def test_invalid_character_raises(self):
        with pytest.raises(
            InvalidPhoneError, match="invalid character in phone number"
        ):
            validate_phone("12345abc90")

    def test_plus_not_at_start_raises(self):
        with pytest.raises(
            InvalidPhoneError, match="a plus prefix is only allowed at the start"
        ):
            validate_phone("123+4567890")

    def test_too_few_digits_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must contain 10-15 digits"):
            validate_phone("123456789")

    def test_too_many_digits_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must contain 10-15 digits"):
            validate_phone("1234567890123456")

    def test_plus_only_raises(self):
        with pytest.raises(InvalidPhoneError, match="phone must contain 10-15 digits"):
            validate_phone("+")

    def test_digits_with_plus_and_spaces_counted(self):
        assert validate_phone("+1 2 3 4 5 6 7 8 9 0") == "+1234567890"


class TestValidateUsername:
    def test_valid_simple(self):
        assert validate_username("abc") == "abc"

    def test_valid_with_digits_and_underscore(self):
        assert validate_username("user_123") == "user_123"

    def test_valid_max_length(self):
        name = "a" + "b" * 19
        assert len(name) == 20
        assert validate_username(name) == name

    def test_valid_min_length(self):
        assert validate_username("abc") == "abc"

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="username must be a string"):
            validate_username(123)

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="username must be a string"):
            validate_username(None)

    def test_too_short_raises(self):
        with pytest.raises(
            ValidationError, match="username must be 3-20 characters long"
        ):
            validate_username("ab")

    def test_empty_raises(self):
        with pytest.raises(
            ValidationError, match="username must be 3-20 characters long"
        ):
            validate_username("")

    def test_too_long_raises(self):
        with pytest.raises(
            ValidationError, match="username must be 3-20 characters long"
        ):
            validate_username("a" * 21)

    def test_invalid_character_raises(self):
        with pytest.raises(
            ValidationError,
            match="username must contain only letters, digits or underscores",
        ):
            validate_username("user-name")

    def test_space_raises(self):
        with pytest.raises(
            ValidationError,
            match="username must contain only letters, digits or underscores",
        ):
            validate_username("user name")

    def test_starts_with_digit_raises(self):
        with pytest.raises(
            ValidationError, match="username must start with a letter"
        ):
            validate_username("1abc")

    def test_starts_with_underscore_raises(self):
        with pytest.raises(
            ValidationError, match="username must start with a letter"
        ):
            validate_username("_abc")

    def test_consecutive_underscores_raises(self):
        with pytest.raises(
            ValidationError,
            match="username must not contain consecutive underscores",
        ):
            validate_username("ab__cd")

    def test_purely_numeric_raises(self):
        with pytest.raises(
            ValidationError, match="username must start with a letter"
        ):
            validate_username("12345")


class TestValidateAge:
    def test_valid_default_bounds(self):
        assert validate_age(30) == 30

    def test_valid_minimum_boundary(self):
        assert validate_age(0) == 0

    def test_valid_maximum_boundary(self):
        assert validate_age(130) == 130

    def test_valid_custom_bounds(self):
        assert validate_age(10, minimum=5, maximum=15) == 10

    def test_valid_custom_min_boundary(self):
        assert validate_age(5, minimum=5, maximum=15) == 5

    def test_valid_custom_max_boundary(self):
        assert validate_age(15, minimum=5, maximum=15) == 15

    def test_bool_raises(self):
        with pytest.raises(ValidationError, match="age must be an integer"):
            validate_age(True)

    def test_false_raises(self):
        with pytest.raises(ValidationError, match="age must be an integer"):
            validate_age(False)

    def test_float_raises(self):
        with pytest.raises(ValidationError, match="age must be an integer"):
            validate_age(30.0)

    def test_string_raises(self):
        with pytest.raises(ValidationError, match="age must be an integer"):
            validate_age("30")

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="age must be an integer"):
            validate_age(None)

    def test_negative_minimum_raises(self):
        with pytest.raises(ValidationError, match="minimum must be non-negative"):
            validate_age(10, minimum=-1)

    def test_minimum_exceeds_maximum_raises(self):
        with pytest.raises(
            ValidationError, match="minimum must not exceed maximum"
        ):
            validate_age(10, minimum=20, maximum=15)

    def test_age_below_minimum_raises(self):
        with pytest.raises(ValidationError, match="age must be >= 5"):
            validate_age(4, minimum=5, maximum=15)

    def test_age_above_maximum_raises(self):
        with pytest.raises(ValidationError, match="age must be <= 15"):
            validate_age(16, minimum=5, maximum=15)

    def test_age_below_default_minimum_raises(self):
        with pytest.raises(ValidationError, match="age must be >= 0"):
            validate_age(-1)

    def test_age_above_default_maximum_raises(self):
        with pytest.raises(ValidationError, match="age must be <= 130"):
            validate_age(131)
