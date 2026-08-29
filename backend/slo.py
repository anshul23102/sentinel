"""Pure SLO accounting: error budget and burn rate.

Given a service-level objective (SLO) target and observed traffic, these
functions compute how much of the allowed error budget remains and how fast it
is being spent — the canonical Google SRE quantities. They are deliberately
free of I/O so they can be unit-tested against known ground truth, matching the
pure-math style of ``seasonal.py``.
"""


def error_budget_remaining(slo_target: float, success_ratio: float) -> float:
    """Fraction of the allowed error budget still unspent.

    ``allowed = 1 - slo_target`` is the share of requests permitted to fail;
    ``consumed = 1 - success_ratio`` is the share that actually failed. Returns
    ``1 - consumed / allowed``: 1.0 when nothing has failed, 0.0 when the budget
    is exactly exhausted, and negative once the SLO is breached.

    A ``slo_target`` of 1.0 (or above) leaves zero budget, so 0.0 is returned to
    avoid dividing by zero — mirroring the zero-variance guards in ``seasonal``.
    """
    allowed = 1.0 - slo_target
    if allowed <= 0:
        return 0.0
    return 1.0 - (1.0 - success_ratio) / allowed


def burn_rate(slo_target: float, observed_error_rate: float) -> float:
    """How fast the error budget is being spent, relative to sustainable pace.

    Returns ``observed_error_rate / (1 - slo_target)``: 1.0 means the budget is
    being spent exactly on pace to last the SLO window, >1 means too fast, and
    0 means no errors. Returns 0.0 when the target leaves no budget.
    """
    allowed = 1.0 - slo_target
    if allowed <= 0:
        return 0.0
    return observed_error_rate / allowed
