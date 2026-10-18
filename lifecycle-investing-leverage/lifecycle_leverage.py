"""Leveraged lifecycle investing: Ayres and Nalebuff's target rule and benchmarks.

Pure functions over monthly real returns. Used by ``backtest.py``; the
Summitward Learn calculator runs the same equations in the browser.

A worker contributes a planned amount each month for a fixed career. Each
month the policy picks the share ``lam`` of current wealth held in stock:

* ``lam > 1`` borrows ``lam - 1`` of wealth at the borrowing rate.
* ``lam < 1`` holds ``1 - lam`` in bonds.

Policies:

* **Target** (Ayres and Nalebuff 2008, "single-target" when the two targets
  are equal). The desired stock exposure is ``lam_lev`` times total wealth,
  where total wealth is current savings plus the present value of planned
  future contributions. While that exposure exceeds current wealth the worker
  is leveraged, capped at ``cap`` times wealth, and future contributions are
  discounted at the borrowing rate ``r_lev``. Once it does not, the target is
  ``lam_unlev`` of total wealth discounted at the bond rate ``r_unlev``,
  capped at 100%. ``cap=1`` gives the same rule with no borrowing.
* **Constant**: a fixed share of current wealth.
* **Glide**: a share that moves linearly from ``start`` to ``end`` over the
  career (the "90/50" age-based rule).

Timing follows the papers: month ``t``'s contribution arrives, the allocation
is set on wealth including it, then month ``t``'s return accrues. An annual
``fee`` is charged on net wealth. Wealth is floored at zero (a wipeout);
later contributions start rebuilding it.

Arrays are shaped ``(n_paths, n_months)`` so every historical cohort or
bootstrap path runs at once.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GAMMAS = (1, 2, 4, 8)


@dataclass(frozen=True)
class Target:
    lam_lev: float
    cap: float = 2.0
    lam_unlev: float | None = None
    name: str = "target"


@dataclass(frozen=True)
class Constant:
    share: float
    name: str = "constant"


@dataclass(frozen=True)
class Glide:
    start: float
    end: float
    name: str = "glide"


Policy = Target | Constant | Glide


@dataclass
class SimResult:
    wealth: np.ndarray  # terminal wealth, shape (n_paths,)
    share: np.ndarray  # stock share each month, shape (n_paths, n_months)
    exposure: np.ndarray  # dollars in stock each month, same shape


def pv_remaining(contrib: np.ndarray, rate: float) -> np.ndarray:
    """Present value at month ``t`` of contributions ``t`` onward (inclusive).

    ``rate`` is a monthly rate. Shape follows ``contrib`` (1-D).
    """
    pv = np.empty(len(contrib))
    acc = 0.0
    for t in range(len(contrib) - 1, -1, -1):
        acc = contrib[t] + acc / (1.0 + rate)
        pv[t] = acc
    return pv


def simulate(
    stock: np.ndarray,
    bond: np.ndarray,
    borrow: np.ndarray,
    planned: np.ndarray,
    policy: Policy,
    r_lev: float = 0.0,
    r_unlev: float = 0.0,
    fee: float = 0.0,
    actual: np.ndarray | None = None,
) -> SimResult:
    """Run ``policy`` over every path.

    ``stock``, ``bond``, ``borrow``: monthly real simple returns, (n, T).
    ``planned``: planned monthly contributions, (T,). The target rule sizes
    exposure from these. ``actual``: contributions actually made, (n, T);
    defaults to ``planned`` (a contribution pause sets some to zero while the
    worker keeps planning on them). ``r_lev``/``r_unlev``: monthly discount
    rates for the target rule's present values. ``fee``: annual, on net wealth.
    """
    stock = np.atleast_2d(stock)
    n, T = stock.shape
    bond = np.broadcast_to(bond, (n, T))
    borrow = np.broadcast_to(borrow, (n, T))
    if actual is None:
        actual = np.broadcast_to(planned, (n, T))
    fee_m = fee / 12.0

    if isinstance(policy, Target):
        pv_lev = pv_remaining(planned, r_lev)
        pv_unlev = pv_remaining(planned, r_unlev)
        lam_unlev = policy.lam_lev if policy.lam_unlev is None else policy.lam_unlev

    wealth = np.zeros(n)
    shares = np.empty((n, T))
    exposure = np.empty((n, T))
    for t in range(T):
        x = wealth + actual[:, t]
        safe_x = np.where(x > 0.0, x, 1.0)
        if isinstance(policy, Target):
            desired = policy.lam_lev * (wealth + pv_lev[t]) / safe_x
            unlev = np.minimum(1.0, lam_unlev * (wealth + pv_unlev[t]) / safe_x)
            lam = np.where(desired > 1.0, np.minimum(policy.cap, desired), unlev)
        elif isinstance(policy, Constant):
            lam = np.full(n, policy.share)
        else:
            frac = t / (T - 1) if T > 1 else 0.0
            lam = np.full(n, policy.start + (policy.end - policy.start) * frac)
        lam = np.where(x > 0.0, lam, 0.0)
        other = np.where(lam > 1.0, borrow[:, t], bond[:, t])
        ret = lam * stock[:, t] + (1.0 - lam) * other - fee_m
        shares[:, t] = lam
        exposure[:, t] = lam * x
        wealth = np.maximum(x * (1.0 + ret), 0.0)
    return SimResult(wealth=wealth, share=shares, exposure=exposure)


def certainty_equivalent(wealth: np.ndarray, gamma: float) -> float:
    """CRRA certainty equivalent of a set of equally likely outcomes."""
    w = np.asarray(wealth, dtype=float)
    if gamma == 0:
        return float(w.mean())
    if np.any(w <= 0.0):
        return 0.0
    if gamma == 1:
        return float(np.exp(np.log(w).mean()))
    return float(np.mean(w ** (1.0 - gamma)) ** (1.0 / (1.0 - gamma)))


def summarize(wealth: np.ndarray) -> dict:
    """Distribution statistics and CRRA certainty equivalents."""
    w = np.asarray(wealth, dtype=float)
    q = np.percentile(w, [1, 5, 10, 25, 50, 75, 90])
    out = {
        "mean": float(w.mean()),
        "median": float(q[4]),
        "std": float(w.std(ddof=1)) if len(w) > 1 else 0.0,
        "min": float(w.min()),
        "p1": float(q[0]),
        "p5": float(q[1]),
        "p10": float(q[2]),
        "p25": float(q[3]),
        "p75": float(q[5]),
        "p90": float(q[6]),
        "max": float(w.max()),
    }
    for g in GAMMAS:
        out[f"ce{g}"] = certainty_equivalent(w, g)
    return out


def effective_years(exposure: np.ndarray, discount: float) -> np.ndarray:
    """Inverse Herfindahl index of discounted stock exposure by career year.

    Ayres and Nalebuff's measure of how evenly a strategy spreads its market
    exposure over the working life: 44 means equal present-value dollars in
    stock every year. ``discount`` is an annual real rate. Returns one value
    per path.
    """
    n, T = exposure.shape
    years = T // 12
    months = np.arange(T)
    pv = exposure * (1.0 + discount) ** (-months / 12.0)
    by_year = pv[:, : years * 12].reshape(n, years, 12).sum(axis=2)
    total = by_year.sum(axis=1, keepdims=True)
    share = np.divide(by_year, total, out=np.zeros_like(by_year), where=total > 0)
    hhi = (share**2).sum(axis=1)
    return np.divide(1.0, hhi, out=np.zeros_like(hhi), where=hhi > 0)


def optimal_share(
    gross_stock: np.ndarray,
    gross_safe: np.ndarray,
    gamma: float,
    grid: np.ndarray | None = None,
) -> float:
    """Single-period CRRA-optimal stock share, Ayres and Nalebuff's Table IV.

    Maximizes the mean of ``u(s * z + (1 - s) * R)`` over the empirical
    distribution of gross annual real returns ``z`` (stock) and ``R`` (the
    opportunity cost: the borrowing rate for the leveraged target, the bond
    rate for the unleveraged one).
    """
    if grid is None:
        grid = np.arange(0.0, 3.0001, 0.001)
    z = np.asarray(gross_stock)[None, :]
    r = np.asarray(gross_safe)[None, :]
    port = grid[:, None] * z + (1.0 - grid[:, None]) * r
    with np.errstate(divide="ignore", invalid="ignore"):
        if gamma == 1:
            util = np.where(port > 0, np.log(np.where(port > 0, port, 1.0)), -np.inf)
        else:
            util = np.where(
                port > 0,
                np.where(port > 0, port, 1.0) ** (1.0 - gamma) / (1.0 - gamma),
                -np.inf,
            )
    return float(grid[int(np.argmax(util.mean(axis=1)))])


def block_bootstrap_indices(
    n_months: int, horizon: int, n_paths: int, block: int, seed: int
) -> np.ndarray:
    """Month indices for circular block-bootstrap paths, shape (n_paths, horizon).

    Each path strings together blocks of ``block`` consecutive months whose
    start months are drawn uniformly, wrapping at the end of the sample, so
    serial dependence within a block is kept and every month is equally
    likely to appear.
    """
    rng = np.random.default_rng(seed)
    n_blocks = -(-horizon // block)
    starts = rng.integers(0, n_months, size=(n_paths, n_blocks))
    offsets = np.arange(block)
    idx = (starts[:, :, None] + offsets[None, None, :]) % n_months
    return idx.reshape(n_paths, n_blocks * block)[:, :horizon]


def margin_call_months(
    share: np.ndarray, month_min_relative: np.ndarray, maintenance: float
) -> np.ndarray:
    """Boolean (n, T): months in which a position opened at ``share`` would
    have breached ``maintenance`` intra-month.

    ``month_min_relative[n, t]`` is the lowest close in month ``t`` relative to
    the prior month-end (1.0 = unchanged). With leverage ``L``, equity over
    exposure falls below ``m`` when the price relative drops below
    ``(L - 1) / (L * (1 - m))``. Loan interest within the month is ignored.
    """
    lev = share > 1.0
    threshold = np.where(
        lev, (share - 1.0) / (np.where(lev, share, 1.0) * (1.0 - maintenance)), 0.0
    )
    return lev & (month_min_relative < threshold)
