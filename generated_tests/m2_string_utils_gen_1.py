import pytest

from benchmark.m2_string_utils import (
    ELLIPSIS,
    normalise,
    reverse,
    is_palindrome,
    word_count,
    truncate,
)


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------

def test_normalise_collapses_and_trims():
    assert normalise("  hello   world  ") == "hello world"


def test_normalise_empty_string():
    assert normalise("") == ""


def test_normalise_only_whitespace():
    assert normalise("   \t\n  ") == ""


def test_normalise_single_word():
    assert normalise("word") == "word"


def test_normalise_leading_trailing():
    assert normalise("\t\n hello \n\t") == "hello"


def test_normalise_type_error():
    with pytest.raises(TypeError):
        normalise(123)


def test_normalise_type_error_none():
    with pytest.raises(TypeError):
        normalise(None)


# ---------------------------------------------------------------------------
# reverse
# ---------------------------------------------------------------------------

def test_reverse_basic():
    assert reverse("abc") == "cba"


def test_reverse_empty():
    assert reverse("") == ""


def test_reverse_single_char():
    assert reverse("a") == "a"


def test_reverse_palindrome():
    assert reverse("racecar") == "racecar"


def test_reverse_unicode():
    assert reverse("héllo") == "olléh"


def test_reverse_type_error():
    with pytest.raises(TypeError):
        reverse(42)


def test_reverse_type_error_list():
    with pytest.raises(TypeError):
        reverse(["a", "b"])


# ---------------------------------------------------------------------------
# is_palindrome
# ---------------------------------------------------------------------------

def test_is_palindrome_classic():
    assert is_palindrome("A man, a plan, a canal: Panama") is True


def test_is_palindrome_simple():
    assert is_palindrome("racecar") is True


def test_is_palindrome_not_palindrome():
    assert is_palindrome("hello") is False


def test_is_palindrome_empty():
    assert is_palindrome("") is True


def test_is_palindrome_single_char():
    assert is_palindrome("a") is True


def test_is_palindrome_only_punctuation():
    assert is_palindrome("!!!") is True


def test_is_palindrome_two_chars_same():
    assert is_palindrome("aa") is True


def test_is_palindrome_two_chars_different():
    assert is_palindrome("ab") is False


def test_is_palindrome_case_insensitive():
    assert is_palindrome("AbBa") is True


def test_is_palindrome_with_digits():
    assert is_palindrome("12321") is True


def test_is_palindrome_mixed_alnum():
    assert is_palindrome("A1b2b1a") is True


def test_is_palindrome_type_error():
    with pytest.raises(TypeError):
        is_palindrome(123)


def test_is_palindrome_type_error_none():
    with pytest.raises(TypeError):
        is_palindrome(None)


# ---------------------------------------------------------------------------
# word_count
# ---------------------------------------------------------------------------

def test_word_count_basic():
    assert word_count("hello world") == 2


def test_word_count_empty():
    assert word_count("") == 0


def test_word_count_only_whitespace():
    assert word_count("   \t\n ") == 0


def test_word_count_extra_spaces():
    assert word_count("  a   b   c  ") == 3


def test_word_count_single_word():
    assert word_count("word") == 1


def test_word_count_type_error():
    with pytest.raises(TypeError):
        word_count(3.14)


def test_word_count_type_error_bytes():
    with pytest.raises(TypeError):
        word_count(b"bytes")


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------

def test_truncate_no_truncation_needed():
    assert truncate("hello", 10) == "hello"


def test_truncate_exact_length():
    assert truncate("hello", 5) == "hello"


def test_truncate_basic():
    assert truncate("hello world", 8) == "hello..."


def test_truncate_default_suffix_is_ellipsis():
    assert ELLIPSIS == "..."
    result = truncate("abcdefghij", 6)
    assert result == "abc..."
    assert result.endswith(ELLIPSIS)


def test_truncate_custom_suffix():
    assert truncate("hello world", 8, suffix="~") == "hello w~"


def test_truncate_empty_suffix():
    assert truncate("hello world", 5, suffix="") == "hello"


def test_truncate_empty_text():
    assert truncate("", 5) == ""


def test_truncate_max_length_equals_suffix_length():
    assert truncate("hello world", 3) == "..."


def test_truncate_max_length_equals_suffix_length_custom():
    assert truncate("hello world", 2, suffix="!!") == "!!"


def test_truncate_max_length_too_small():
    with pytest.raises(ValueError):
        truncate("hello", 2)


def test_truncate_max_length_too_small_custom_suffix():
    with pytest.raises(ValueError):
        truncate("hello", 1, suffix="...")


def test_truncate_negative_max_length():
    with pytest.raises(ValueError):
        truncate("hello", -1)


def test_truncate_type_error_text():
    with pytest.raises(TypeError):
        truncate(123, 5)


def test_truncate_type_error_text_none():
    with pytest.raises(TypeError):
        truncate(None, 5)
