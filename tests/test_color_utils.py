from src.ai.color_utils import get_hsv_bounds


def test_explicit_hsv_bounds_win_over_tolerance():
    lower, upper = get_hsv_bounds({
        "hsv": [10, 100, 100],
        "hsv_lower": [1, 2, 3],
        "hsv_upper": [4, 5, 6],
        "tolerance": 20,
    })

    assert lower == [1, 2, 3]
    assert upper == [4, 5, 6]


def test_center_hsv_with_numeric_tolerance():
    lower, upper = get_hsv_bounds({"hsv": [10, 100, 100], "tolerance": 5})

    assert lower == [5, 90, 90]
    assert upper == [15, 110, 110]


def test_center_hsv_with_triplet_tolerance_clamps_bounds():
    lower, upper = get_hsv_bounds({"hsv": [2, 250, 5], "tolerance": [10, 20, 30]})

    assert lower == [0, 230, 0]
    assert upper == [12, 255, 35]


def test_invalid_tolerance_returns_empty_bounds():
    assert get_hsv_bounds({"hsv": [10, 100, 100], "tolerance": [1, 2]}) == (None, None)
