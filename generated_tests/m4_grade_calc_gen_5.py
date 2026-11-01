import pytest

from benchmark.m4_grade_calc import (
    GRADE_POINTS,
    letter_grade,
    grade_point,
    weighted_average,
    passing_score,
    describe_score,
)


class TestLetterGrade:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0, "F"),
            (59.99, "F"),
            (60, "D"),
            (69.99, "D"),
            (70, "C"),
            (79.99, "C"),
            (80, "B"),
            (89.99, "B"),
            (90, "A"),
            (100, "A"),
            (95, "A"),
        ],
    )
    def test_boundaries(self, score, expected):
        assert letter_grade(score) == expected

    def test_integer_scores(self):
        assert letter_grade(85) == "B"

    def test_float_scores(self):
        assert letter_grade(72.5) == "C"

    @pytest.mark.parametrize("score", [-0.01, -1, 100.01, 101, 1000])
    def test_out_of_range(self, score):
        with pytest.raises(ValueError):
            letter_grade(score)

    @pytest.mark.parametrize("score", ["90", None, [90], {"a": 1}, True, False])
    def test_non_numeric(self, score):
        with pytest.raises(ValueError):
            letter_grade(score)


class TestGradePoint:
    @pytest.mark.parametrize(
        "letter,expected",
        [
            ("A", 4.0),
            ("B", 3.0),
            ("C", 2.0),
            ("D", 1.0),
            ("F", 0.0),
        ],
    )
    def test_valid_letters(self, letter, expected):
        assert grade_point(letter) == pytest.approx(expected)

    @pytest.mark.parametrize("letter", ["a", "b", "c", "d", "f"])
    def test_lowercase(self, letter):
        assert grade_point(letter) == pytest.approx(GRADE_POINTS[letter.upper()])

    @pytest.mark.parametrize("letter", [" A ", "  b  ", "\tC\n", "d ", " F"])
    def test_whitespace(self, letter):
        assert grade_point(letter) == pytest.approx(GRADE_POINTS[letter.strip().upper()])

    @pytest.mark.parametrize("letter", ["E", "G", "", "AB", "1", "A+"])
    def test_unknown_letters(self, letter):
        with pytest.raises(ValueError):
            grade_point(letter)

    @pytest.mark.parametrize("letter", [None, 1, 4.0, ["A"], {"A": 1}])
    def test_non_string(self, letter):
        with pytest.raises(ValueError):
            grade_point(letter)


class TestWeightedAverage:
    def test_simple(self):
        assert weighted_average([90, 80], [1, 1]) == pytest.approx(85.0)

    def test_weighted(self):
        assert weighted_average([90, 80], [3, 1]) == pytest.approx(87.5)

    def test_rounding(self):
        assert weighted_average([1, 2, 3], [1, 1, 1]) == pytest.approx(2.0)
        assert weighted_average([1, 2], [1, 2]) == pytest.approx(1.67)

    def test_single_element(self):
        assert weighted_average([75.5], [2.0]) == pytest.approx(75.5)

    def test_zero_weight_entries(self):
        assert weighted_average([100, 50], [0, 1]) == pytest.approx(50.0)

    def test_empty_scores(self):
        with pytest.raises(ValueError):
            weighted_average([], [])

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80], [1])
        with pytest.raises(ValueError):
            weighted_average([90], [1, 2])

    def test_all_zero_weights(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80], [0, 0])

    def test_negative_weight(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80], [1, -1])

    def test_negative_weight_after_positive(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80, 70], [1, 1, -0.5])


class TestPassingScore:
    def test_empty_is_failing(self):
        assert passing_score([]) is False

    @pytest.mark.parametrize(
        "scores,expected",
        [
            ([60], True),
            ([59.99], False),
            ([60, 60], True),
            ([59, 60], False),
            ([100, 100], True),
            ([0, 0], False),
            ([0, 100], False),
            ([60, 60, 60], True),
            ([59, 60, 60], False),
        ],
    )
    def test_means(self, scores, expected):
        assert passing_score(scores) is expected

    @pytest.mark.parametrize("scores", [[-0.01], [100.01], [50, 101], [-1, 50]])
    def test_out_of_range(self, scores):
        with pytest.raises(ValueError):
            passing_score(scores)


class TestDescribeScore:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (100, "A - pass (100.0)"),
            (90, "A - pass (90.0)"),
            (89.99, "B - pass (90.0)"),
            (82, "B - pass (82.0)"),
            (80, "B - pass (80.0)"),
            (70, "C - pass (70.0)"),
            (60, "D - pass (60.0)"),
            (59.99, "F - fail (60.0)"),
            (0, "F - fail (0.0)"),
            (72.55, "C - pass (72.5)"),
            (72.56, "C - pass (72.6)"),
        ],
    )
    def test_descriptions(self, score, expected):
        assert describe_score(score) == expected

    @pytest.mark.parametrize("score", [-0.01, 100.01, -10, 200])
    def test_out_of_range(self, score):
        with pytest.raises(ValueError):
            describe_score(score)

    @pytest.mark.parametrize("score", ["90", None, True])
    def test_non_numeric(self, score):
        with pytest.raises(ValueError):
            describe_score(score)


class TestGradePointsMapping:
    def test_mapping_contents(self):
        assert GRADE_POINTS == {
            "A": 4.0,
            "B": 3.0,
            "C": 2.0,
            "D": 1.0,
            "F": 0.0,
        }

    def test_mapping_values_are_floats(self):
        for value in GRADE_POINTS.values():
            assert isinstance(value, float)
