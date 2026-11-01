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
            (100.0, "A"),
        ],
    )
    def test_boundaries(self, score, expected):
        assert letter_grade(score) == expected

    def test_bool_rejected(self):
        with pytest.raises(ValueError):
            letter_grade(True)

    def test_bool_false_rejected(self):
        with pytest.raises(ValueError):
            letter_grade(False)

    @pytest.mark.parametrize("bad", ["90", None, [], {}, object()])
    def test_non_numeric_rejected(self, bad):
        with pytest.raises(ValueError):
            letter_grade(bad)

    @pytest.mark.parametrize("bad", [-0.01, -1, 100.01, 101, 1000])
    def test_out_of_range_rejected(self, bad):
        with pytest.raises(ValueError):
            letter_grade(bad)


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
    def test_known_letters(self, letter, expected):
        assert grade_point(letter) == pytest.approx(expected)

    @pytest.mark.parametrize("letter", ["a", "b", "c", "d", "f"])
    def test_lowercase(self, letter):
        assert grade_point(letter) == pytest.approx(GRADE_POINTS[letter.upper()])

    @pytest.mark.parametrize("letter", [" A ", "B\t", "\nC", "  d  "])
    def test_whitespace_stripped(self, letter):
        assert grade_point(letter) == pytest.approx(GRADE_POINTS[letter.strip().upper()])

    @pytest.mark.parametrize("bad", ["E", "G", "", "AA", "1", "A+"])
    def test_unknown_letter_rejected(self, bad):
        with pytest.raises(ValueError):
            grade_point(bad)

    @pytest.mark.parametrize("bad", [None, 1, 4.0, [], {}])
    def test_non_string_rejected(self, bad):
        with pytest.raises(ValueError):
            grade_point(bad)


class TestWeightedAverage:
    def test_simple(self):
        assert weighted_average([90, 80], [1, 1]) == pytest.approx(85.0)

    def test_weighted(self):
        assert weighted_average([90, 80], [3, 1]) == pytest.approx(87.5)

    def test_rounding(self):
        assert weighted_average([1, 2, 3], [1, 1, 1]) == pytest.approx(2.0)
        assert weighted_average([1, 2], [1, 2]) == pytest.approx(1.67)

    def test_single(self):
        assert weighted_average([75.5], [2.0]) == pytest.approx(75.5)

    def test_zero_weight_entries(self):
        assert weighted_average([100, 50], [0, 1]) == pytest.approx(50.0)

    def test_empty_scores(self):
        with pytest.raises(ValueError):
            weighted_average([], [])

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80], [1])

    def test_length_mismatch_other_direction(self):
        with pytest.raises(ValueError):
            weighted_average([90], [1, 2])

    def test_all_zero_weights(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80], [0, 0])

    def test_negative_weight(self):
        with pytest.raises(ValueError):
            weighted_average([90, 80], [1, -1])


class TestPassingScore:
    def test_empty_is_false(self):
        assert passing_score([]) is False

    @pytest.mark.parametrize(
        "scores,expected",
        [
            ([60], True),
            ([59.99], False),
            ([60, 60], True),
            ([59, 60], False),
            ([0, 100], True),
            ([0, 0], False),
            ([100, 100], True),
            ([59, 59, 59], False),
            ([60, 60, 60], True),
        ],
    )
    def test_mean_threshold(self, scores, expected):
        assert passing_score(scores) is expected

    @pytest.mark.parametrize("bad", [-0.01, -1, 100.01, 101])
    def test_out_of_range_rejected(self, bad):
        with pytest.raises(ValueError):
            passing_score([50, bad])

    def test_boundary_values_accepted(self):
        assert passing_score([0, 100]) is True


class TestDescribeScore:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (100, "A - pass (100.0)"),
            (90, "A - pass (90.0)"),
            (89.99, "B - pass (90.0)"),
            (80, "B - pass (80.0)"),
            (70, "C - pass (70.0)"),
            (60, "D - pass (60.0)"),
            (59.99, "F - fail (60.0)"),
            (0, "F - fail (0.0)"),
            (82, "B - pass (82.0)"),
            (82.25, "B - pass (82.2)"),
        ],
    )
    def test_descriptions(self, score, expected):
        assert describe_score(score) == expected

    @pytest.mark.parametrize("bad", [-0.01, -1, 100.01, 101])
    def test_out_of_range_rejected(self, bad):
        with pytest.raises(ValueError):
            describe_score(bad)

    @pytest.mark.parametrize("bad", ["90", None, True])
    def test_non_numeric_rejected(self, bad):
        with pytest.raises(ValueError):
            describe_score(bad)


class TestGradePointsMapping:
    def test_mapping_contents(self):
        assert GRADE_POINTS == {
            "A": 4.0,
            "B": 3.0,
            "C": 2.0,
            "D": 1.0,
            "F": 0.0,
        }
