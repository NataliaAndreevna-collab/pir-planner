import pytest
from app.services.cost_estimator import _eval_ab_intervals


def test_extrapolation_normal_interval():
    # Таблица с интервалом 3.0 .. 20.0, a = 3235.8, b = 612.655
    ivs = [{"x_min": 3.0, "x_max": 20.0, "a": 3235.8, "b": 612.655}]
    val, a, b, expr = _eval_ab_intervals(ivs, 10.0)
    assert round(val, 2) == round(3235.8 + 612.655 * 10.0, 2)
    assert "[экстрап." not in expr


def test_extrapolation_half_to_min():
    # 0.5 * X_min <= X < X_min (1.5 <= 2.0 < 3.0) -> формула (8.2)
    ivs = [{"x_min": 3.0, "x_max": 20.0, "a": 3235.8, "b": 612.655}]
    val, a, b, expr = _eval_ab_intervals(ivs, 2.0)
    expected_x_eff = 0.4 * 3.0 + 0.6 * 2.0
    expected_val = 3235.8 + 612.655 * expected_x_eff
    assert round(val, 2) == round(expected_val, 2)
    assert "ф. 8.2" in expr


def test_extrapolation_less_than_half_min_k_eks_limit():
    # X < 0.5 * X_min (X = 0.0125 < 1.5) -> формулы (8.4) и (8.5) с K_экс >= 0.1
    ivs = [{"x_min": 3.0, "x_max": 20.0, "a": 3235.8, "b": 612.655}]
    val, a, b, expr = _eval_ab_intervals(ivs, 0.0125)
    # 0.0125 / 1.5 = 0.0083 < 0.1 -> K_экс = 0.1
    c_half = 3235.8 + 612.655 * (0.4 * 3.0 + 0.6 * 1.5)
    expected_val = c_half * 0.1
    assert round(val, 2) == round(expected_val, 2)
    assert "ф. 8.4-8.5" in expr
    assert "K_экс=0,1" in expr


def test_extrapolation_max_to_double():
    # X_max < X <= 2.0 * X_max (20.0 < 25.0 <= 40.0) -> формула (8.3)
    ivs = [{"x_min": 3.0, "x_max": 20.0, "a": 3235.8, "b": 612.655}]
    val, a, b, expr = _eval_ab_intervals(ivs, 25.0)
    expected_x_eff = 0.4 * 20.0 + 0.6 * 25.0
    expected_val = 3235.8 + 612.655 * expected_x_eff
    assert round(val, 2) == round(expected_val, 2)
    assert "ф. 8.3" in expr


def test_extrapolation_greater_than_double_max():
    # X > 2.0 * X_max (X = 50.0 > 40.0) -> формулы (8.6) и (8.7)
    ivs = [{"x_min": 3.0, "x_max": 20.0, "a": 3235.8, "b": 612.655}]
    val, a, b, expr = _eval_ab_intervals(ivs, 50.0)
    x_double = 40.0
    c_double = 3235.8 + 612.655 * (0.4 * 20.0 + 0.6 * x_double)
    k_eks = round(50.0 / x_double, 4)
    expected_val = c_double * k_eks
    assert round(val, 2) == round(expected_val, 2)
    assert "ф. 8.6-8.7" in expr
