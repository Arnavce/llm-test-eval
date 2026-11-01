"""M3 - Medium-complexity validation helpers (target cyclomatic complexity 3-5).

Covers regular-expression based email/phone validation, explicit type checks,
length boundaries and custom ``ValueError`` subclasses.  The regexes are
deliberately simple and documented so that generated tests can be written
against a precise contract.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "ValidationError",
    "InvalidEmailError",
    "InvalidPhoneError",
    "validate_email",
    "validate_phone",
    "validate_username",
    "validate_age",
]

#: Local part @ domain with at least one dot in the domain, no whitespace.
EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

#: Optional ``+`` prefix followed by 10-15 digits; spaces and dashes allowed.
PHONE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\+?\d{10,15}$")

#: Usernames are 3-20 characters of letters, digits or underscores.
USERNAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_]{3,20}$")


class ValidationError(ValueError):
    """Base class for every validation failure raised by this module."""


class InvalidEmailError(ValidationError):
    """Raised when an email address does not match :data:`EMAIL_PATTERN`."""


class InvalidPhoneError(ValidationError):
    """Raised when a phone number is not 10-15 digits long."""


def validate_email(email: str) -> str:
    """Return ``email`` unchanged when it is a well-formed address.

    The checks are applied in order of cost: type, emptiness, length, shape,
    dot placement, then domain-label hyphens.  Each failure has its own
    message so test suites can pin the exact rejection reason.

    Raises:
        InvalidEmailError: If ``email`` is not a ``str``, is blank, exceeds
            254 characters, does not match :data:`EMAIL_PATTERN`, or violates
            the local-part/domain-label rules.
    """
    if not isinstance(email, str):
        raise InvalidEmailError("email must be a string")
    candidate = email.strip()
    if not candidate:
        raise InvalidEmailError("email must not be empty")
    if len(candidate) > 254:
        raise InvalidEmailError("email exceeds 254 characters")
    if candidate.count("@") != 1 or not EMAIL_PATTERN.match(candidate):
        raise InvalidEmailError(f"invalid email address: {email!r}")
    local, _, domain = candidate.partition("@")
    if "." in (local[0], local[-1]) or ".." in local:
        raise InvalidEmailError("email local part has invalid dot placement")
    for label in domain.split("."):
        if label.startswith("-") or label.endswith("-"):
            raise InvalidEmailError(
                "email domain labels must not start or end with a hyphen"
            )
    return candidate


def validate_phone(phone: str) -> str:
    """Return ``phone`` with spaces and dashes removed when it is valid.

    A valid number is 10-15 digits with an optional leading ``+``.

    Raises:
        InvalidPhoneError: If ``phone`` is not a ``str``, contains characters
            other than digits, spaces, dashes or ``+``, or is not 10-15 digits.
    """
    if not isinstance(phone, str):
        raise InvalidPhoneError("phone must be a string")
    stripped = phone.strip()
    if not stripped:
        raise InvalidPhoneError("phone must not be empty")
    allowed = set("0123456789 -+")
    for character in stripped:
        if character not in allowed:
            raise InvalidPhoneError(f"invalid character in phone number: {character!r}")
        if character == "+" and stripped.index(character) != 0:
            raise InvalidPhoneError("a plus prefix is only allowed at the start")
    digits = stripped.replace(" ", "").replace("-", "")
    if digits.startswith("+"):
        digits_without_plus = digits[1:]
    else:
        digits_without_plus = digits
    if len(digits_without_plus) < 10 or len(digits_without_plus) > 15:
        raise InvalidPhoneError("phone must contain 10-15 digits")
    if not PHONE_PATTERN.match(digits):
        raise InvalidPhoneError(f"invalid phone number: {phone!r}")
    return digits


def validate_username(username: str) -> str:
    """Return ``username`` unchanged when it is 3-20 word characters.

    Usernames must start with a letter, may not contain two consecutive
    underscores and may not be purely numeric.

    Raises:
        ValidationError: If ``username`` is not a ``str`` or violates a rule.
    """
    if not isinstance(username, str):
        raise ValidationError("username must be a string")
    if len(username) < 3 or len(username) > 20:
        raise ValidationError("username must be 3-20 characters long")
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "username must contain only letters, digits or underscores"
        )
    if not username[0].isalpha():
        raise ValidationError("username must start with a letter")
    if "__" in username:
        raise ValidationError("username must not contain consecutive underscores")
    return username


def validate_age(age: int, minimum: int = 0, maximum: int = 130) -> int:
    """Return ``age`` when ``minimum <= age <= maximum``.

    Raises:
        ValidationError: If ``age`` is not an ``int`` (``bool`` is rejected),
            or if the bounds are inconsistent, or if ``age`` is out of range.
    """
    if isinstance(age, bool) or not isinstance(age, int):
        raise ValidationError("age must be an integer")
    if minimum < 0:
        raise ValidationError("minimum must be non-negative")
    if minimum > maximum:
        raise ValidationError("minimum must not exceed maximum")
    if age < minimum:
        raise ValidationError(f"age must be >= {minimum}")
    if age > maximum:
        raise ValidationError(f"age must be <= {maximum}")
    return age
