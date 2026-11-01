import pytest

from benchmark.m2_string_utils import (
    ELLIPSIS,
    is_palindrome,
    normalise,
    reverse,
    truncate,
    word_count,
)


class TestNormalise:
    def test_collapses_and_trims(self):
        assert normalise("  hello   world  ") == "hello world"

    def test_single_word(self):
        assert normalise("hello") == "hello"

    def test_empty(self):
        assert normalise("") == ""

    def test_only_whitespace(self):
        assert normalise("   \t\n  ") == ""

    def test_tabs_and_newlines(self):
        assert normalise("a\tb\nc\rd") == "a b c d"

    def test_leading_trailing(self):
        assert normalise("   x   ") == "x"

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            normalise(123)
        with pytest.raises(TypeError):
            normalise(None)
        with pytest.raises(TypeError):
            normalise(["a"])


class TestReverse:
    def test_basic(self):
        assert reverse("abc") == "cba"

    def test_empty(self):
        assert reverse("") == ""

    def test_single_char(self):
        assert reverse("a") == "a"

    def test_palindrome(self):
        assert reverse("racecar") == "racecar"

    def test_whitespace_preserved(self):
        assert reverse("a b") == "b a"

    def test_unicode(self):
        assert reverse("héllo") == "olléh"

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            reverse(1)
        with pytest.raises(TypeError):
            reverse(None)


class TestIsPalindrome:
    def test_classic_phrase(self):
        assert is_palindrome("A man, a plan, a canal: Panama") is True

    def test_simple(self):
        assert is_palindrome("racecar") is True

    def test_not_palindrome(self):
        assert is_palindrome("hello") is False

    def test_empty_is_true(self):
        assert is_palindrome("") is True

    def test_single_char_is_true(self):
        assert is_palindrome("a") is True

    def test_single_non_alnum_is_true(self):
        assert is_palindrome("!") is True

    def test_two_chars(self):
        assert is_palindrome("aa") is True
        assert is_palindrome("ab") is False

    def test_case_insensitive(self):
        assert is_palindrome("Aa") is True

    def test_ignores_punctuation(self):
        assert is_palindrome("Was it a car or a cat I saw?") is True

    def test_digits(self):
        assert is_palindrome("12321") is True
        assert is_palindrome("12345") is False

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            is_palindrome(123)
        with pytest.raises(TypeError):
            is_palindrome(None)


class TestWordCount:
    def test_basic(self):
        assert word_count("hello world") == 2

    def test_empty(self):
        assert word_count("") == 0

    def test_only_whitespace(self):
        assert word_count("   \t\n ") == 0

    def test_extra_whitespace(self):
        assert word_count("  a   b  c ") == 3

    def test_single_word(self):
        assert word_count("word") == 1

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            word_count(5)
        with pytest.raises(TypeError):
            word_count(None)


class TestTruncate:
    def test_no_truncation_needed(self):
        assert truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert truncate("hello", 5) == "hello"

    def test_truncation_default_suffix(self):
        assert truncate("hello world", 8) == "hello..."

    def test_truncation_custom_suffix(self):
        assert truncate("hello world", 8, "~") == "hello w~"

    def test_truncation_empty_suffix(self):
        assert truncate("hello world", 5, "") == "hello"

    def test_max_length_equals_suffix_length(self):
        assert truncate("hello world", 3) == "..."

    def test_max_length_equals_custom_suffix_length(self):
        assert truncate("hello world", 2, "!!") == "!!"

    def test_empty_text(self):
        assert truncate("", 5) == ""

    def test_empty_text_zero_length(self):
        assert truncate("", 0, "") == ""

    def test_max_length_too_small_raises(self):
        with pytest.raises(ValueError):
            truncate("hello", 2)

    def test_max_length_too_small_custom_suffix_raises(self):
        with pytest.raises(ValueError):
            truncate("hello", 1, "!!")

    def test_negative_max_length_raises(self):
        with pytest.raises(ValueError):
            truncate("hello", -1)

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            truncate(123, 5)
        with pytest.raises(TypeError):
            truncate(None, 5)

    def test_ellipsis_constant(self):
        assert ELLIPSIS == "..."
        assert truncate("abcdefgh", 5) == "ab" + ELLIPSIS
