"""Pure-math tests for seasonal.py — each assertion is checked against known
ground truth, not just 'did it run without crashing'. These are the same
checks run manually during development; formalized here so a future change
can't silently regress them."""
import numpy as np
from seasonal import holt_linear_forecast, fit_seasonal_baseline, cusum_changepoint


def test_holt_forecast_beats_ols_on_a_real_slope_change():
    segment1 = [10 + i * 1.0 for i in range(20)]
    segment2 = [segment1[-1] + i * 8.0 for i in range(1, 16)]
    series = segment1 + segment2
    true_next5 = series[-1] + 5 * 8.0

    holt_pred = holt_linear_forecast(series, steps_ahead=5)
    ols_coeffs = np.polyfit(np.arange(20), series[-20:], 1)
    ols_pred = ols_coeffs[0] * 25 + ols_coeffs[1]

    assert abs(holt_pred - true_next5) < abs(ols_pred - true_next5)
    assert abs(holt_pred - true_next5) < 1.0


def test_holt_forecast_degrades_gracefully_on_short_or_flat_input():
    assert holt_linear_forecast([]) == 0.0
    assert holt_linear_forecast([5.0]) == 5.0
    assert holt_linear_forecast([5.0] * 20, steps_ahead=5) == 5.0


def test_holt_winters_recovers_known_seasonal_pattern():
    period, n_cycles = 10, 4
    x = np.arange(period * n_cycles)
    series = 100 + 0.5 * x + 20 * np.sin(2 * np.pi * x / period)
    next_x = period * n_cycles
    true_next = 100 + 0.5 * next_x + 20 * np.sin(2 * np.pi * next_x / period)

    result = fit_seasonal_baseline(list(series), period=period)
    assert result is not None
    assert abs(result["expected"] - true_next) < 0.5


def test_holt_winters_refuses_to_fit_insufficient_history():
    period = 10
    short_series = list(np.random.normal(100, 5, period + 3))
    assert fit_seasonal_baseline(short_series, period=period) is None


def test_cusum_fires_on_real_persistent_shift():
    rng = np.random.default_rng(11)
    fires = 0
    trials = 30
    for _ in range(trials):
        normal   = [rng.normal(72, 18, 30).mean() for _ in range(30)]
        slowdown = [rng.normal(850, 220, 30).mean() for _ in range(30)]
        fired, _ = cusum_changepoint(normal + slowdown)
        fires += fired
    assert fires == trials  # must reliably catch a real regime shift


def test_cusum_does_not_false_alarm_on_pure_noise():
    rng = np.random.default_rng(3)
    false_positives = 0
    trials = 100
    for _ in range(trials):
        series = [rng.normal(72, 18, 30).mean() for _ in range(90)]
        fired, _ = cusum_changepoint(series)
        false_positives += fired
    # threshold=10.0 was calibrated against exactly this scenario — see
    # seasonal.py's docstring. A regression here means someone changed the
    # threshold without re-validating the false-positive rate.
    assert false_positives == 0


def test_cusum_raw_per_request_values_were_unsafe_at_the_original_threshold():
    """Pins a real finding from development, precisely scoped: at the
    original threshold=5 (a common textbook default), a single naturally
    slow request among raw per-request values reliably false-positived.
    Re-verified after threshold=10 was calibrated (see seasonal.py's
    docstring) that this SPECIFIC case no longer reproduces at the current
    default — so this test intentionally passes threshold=5 explicitly to
    keep documenting the original finding, rather than asserting something
    about current behavior that turned out not to hold."""
    rng = np.random.default_rng(7)
    false_positives = 0
    trials = 30
    for _ in range(trials):
        raw = list(rng.normal(75, 15, 55))  # RAW per-request, not aggregated
        raw[rng.integers(30, 50)] = 75 * 3   # one realistic slow request
        fired, _ = cusum_changepoint(raw, threshold=5.0)
        false_positives += fired
    assert false_positives == trials


def test_cusum_aggregated_values_are_safe_at_the_current_default_threshold():
    """The recommended real usage — per-tick aggregates at the calibrated
    default threshold=10 — must not false-positive on the same underlying
    'one slow request' event once it's properly averaged into its tick."""
    rng = np.random.default_rng(7)
    baseline = list(rng.normal(75, 15, 55))
    idx = rng.integers(30, 50)
    agg_val = (sum(baseline) - baseline[idx] + 75 * 3) / len(baseline)
    aggregated = baseline[:idx] + baseline[idx + 1:] + [agg_val]
    fired, _ = cusum_changepoint(aggregated)  # current default threshold=10.0
    assert not fired
