import pytest

from benchmark.m1_arithmetic import (
    DEFAULT_TOLERANCE,
    add,
    subtract,
    multiply,
    divide,
    average,
    is_close,
)


class TestAdd:
    def test_positive(self):
        assert add(2, 3) == 5

    def test_negative(self):
        assert add(-2, -3) == -5

    def test_mixed(self):
        assert add(-2, 3) == 1

    def test_zero(self):
        assert add(0, 0) == 0

    def test_floats(self):
        assert add(0.1, 0.2) == pytest.approx(0.3)


class TestSubtract:
    def test_positive(self):
        assert subtract(5, 3) == 2

    def test_negative_result(self):
        assert subtract(3, 5) == -2

    def test_zero(self):
        assert subtract(0, 0) == 0

    def test_floats(self):
        assert subtract(0.3, 0.1) == pytest.approx(0.2)


class TestMultiply:
    def test_positive(self):
        assert multiply(2, 3) == 6

    def test_negative(self):
        assert multiply(-2, 3) == -6

    def test_both_negative(self):
        assert multiply(-2, -3) == 6

    def test_zero(self):
        assert multiply(5, 0) == 0

    def test_floats(self):
        assert multiply(0.5, 0.5) == pytest.approx(0.25)


class TestDivide:
    def test_positive(self):
        assert divide(6, 3) == 2

    def test_float_result(self):
        assert divide(1, 4) == pytest.approx(0.25)

    def test_negative(self):
        assert divide(-6, 3) == -2

    def test_zero_numerator(self):
        assert divide(0, 5) == 0

    def test_divide_by_int_zero(self):
        with pytest.raises(ValueError):
            divide(1, 0)

    def test_divide_by_float_zero(self):
        with pytest.raises(ValueError):
            divide(1, 0.0)

    def test_divide_by_negative_zero(self):
        with pytest.raises(ValueError):
            divide(1, -0.0)


class TestAverage:
    def test_single_value(self):
        assert average([5]) == 5

    def test_multiple_values(self):
        assert average([1, 2, 3, 4]) == pytest.approx(2.5)

    def test_negative_values(self):
        assert average([-1, -2, -3]) == pytest.approx(-2)

    def test_floats(self):
        assert average([0.1, 0.2, 0.3]) == pytest.approx(0.2)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            average([])


class TestIsClose:
    def test_equal(self):
        assert is_close(1.0, 1.0) is True

    def test_within_default_tolerance(self):
        assert is_close(1.0, 1.0 + DEFAULT_TOLERANCE / 2) is True

    def test_exactly_at_default_tolerance(self):
        assert is_close(0.0, DEFAULT_TOLERANCE) is True

    def test_outside_default_tolerance(self):
        assert is_close(0.0, DEFAULT_TOLERANCE * 2) is False

    def test_custom_tolerance(self):
        assert is_close(0.0, 0.5, tolerance=1.0) is True

    def test_custom_tolerance_exceeded(self):
        assert is_close(0.0, 1.5, tolerance=1.0) is False

    def test_zero_tolerance_equal(self):
        assert is_close(2.0, 2.0, tolerance=0.0) is True

    def test_zero_tolerance_unequal(self):
        assert is_close(2.0, 2.1, tolerance=0.0) is False

    def test_negative_tolerance_raises(self):
        with pytest.raises(ValueError):
            is_close(1.0, 1.0, tolerance=-0.1)

    def test_default_tolerance_value(self):
        assert DEFAULT_TOLERANCE == pytest.approx(1e-9)
