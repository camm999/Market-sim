# simulator/gbm_flow.py
"""
generates synthetic exogenous price paths via geometric Brownian Motion,
also uses GARCH(1,1) variance process with student-t innovations to remove constant sigma.

see the README's 'GBM Priced (GARCH(1,1) implementation)' section.
"""

import math
import random
from typing import List, Sequence, Tuple

from lob.book import Side


def _gbm_next_price(price: float, mu: float, sigma: float, rng: random.Random) -> float:
    """one discretized-GBM step (dt=1): S_(t+1) = S_t * exp((mu - sigma^2/2) + sigma*Z), Z ~ N(0, 1)."""
    return price * math.exp(mu - 0.5 * sigma**2 + sigma * rng.gauss(0, 1))


def generate_gbm_path(steps: int, seed: int, mu: float = 0.0, sigma: float = 0.02, base: float = 100.0) -> List[float]:
    """per step vol in the same ballpark as random_flow.py's,generates orders priced at
    mid + random.randint(-3, 3), this sigma allows similar price movement.

    ssing a fresh, isolated random.Random(seed) instance means generating the price path is fully
    independent, doesnt interact with other seeds"""
    rng = random.Random(seed)
    prices = [base]
    for _ in range(steps - 1):
        prices.append(_gbm_next_price(prices[-1], mu, sigma, rng))
    return prices


def _scheduled_drift(t: int, schedule: Sequence[Tuple[int, int, Side]], drift: float) -> float:
    for start, end, side in schedule:
        if start <= t < end:
            return drift if side == "buy" else -drift
    return 0.0


def generate_scheduled_drift_gbm_path(
    steps: int,
    seed: int,
    schedule: Sequence[Tuple[int, int, Side]],
    drift: float = 0.004,
    sigma: float = 0.02,
    base: float = 100.0,
) -> List[float]:
    """same discretized GBM as generate_gbm_path, but with scheduled drift windows
    allowing for informed trader,

    drift=0.004 default (0.4% per step) is deliberately sized to be comparable
    in magnitude to the informed-trader windows, big enough to 
    show up clearly against the sigma=0.02 noise, but still stochastic."""
    rng = random.Random(seed)
    prices = [base]
    for t in range(steps - 1):
        mu = _scheduled_drift(t, schedule, drift)
        prices.append(_gbm_next_price(prices[-1], mu, sigma, rng))
    return prices


def _student_t_z(nu: float, rng: random.Random) -> float:
    """A standard (var=1) student-t(nu) draw, Z / sqrt(V/nu) with Z ~ N(0, 1) and
    V ~ Chi2(nu) (equivilent to Gamma(nu/2, 2)), then rescaled by sqrt((nu-2)/nu) - raw student-t(nu)
    has variance nu/(nu-2), not 1, GARCH requires variance 1"""
    z = rng.gauss(0, 1)
    v = rng.gammavariate(nu / 2, 2.0)
    t = z / math.sqrt(v / nu)
    return t * math.sqrt((nu - 2) / nu)


def generate_garch_gbm_path(
    steps: int,
    seed: int,
    mu: float = 0.0,
    omega: float = 1.6e-5,
    alpha: float = 0.08,
    beta: float = 0.88,
    nu: float = 5.0,
    base: float = 100.0,
) -> List[float]:
    """similar to generate_gbm_path but with a GARCH(1,1) variance process with student-t innovations 
    rids constant sigma, see read me for parameter choices.
    `alpha + beta` < 1 for stationary process
    initial sigma^2 seeded at stationary (unconditional) variance,
    omega / (1 - alpha - beta), the value the process reverts to on average.

    draws from its own random.Random(seed) for similar reasons as above"""
    rng = random.Random(seed)
    sigma2 = omega / (1 - alpha - beta)
    prices = [base]
    for _ in range(steps - 1):
        sigma = math.sqrt(sigma2)
        eps = sigma * _student_t_z(nu, rng)
        prices.append(prices[-1] * math.exp(mu - 0.5 * sigma2 + eps))
        sigma2 = omega + alpha * eps**2 + beta * sigma2
    return prices


def generate_scheduled_drift_garch_gbm_path(
    steps: int,
    seed: int,
    schedule: Sequence[Tuple[int, int, Side]],
    drift: float = 0.004,
    omega: float = 1.6e-5,
    alpha: float = 0.08,
    beta: float = 0.88,
    nu: float = 5.0,
    base: float = 100.0,
) -> List[float]:
    """combination of above functions involves the above with a drift schedule"""
    rng = random.Random(seed)
    sigma2 = omega / (1 - alpha - beta)
    prices = [base]
    for t in range(steps - 1):
        mu = _scheduled_drift(t, schedule, drift)
        sigma = math.sqrt(sigma2)
        eps = sigma * _student_t_z(nu, rng)
        prices.append(prices[-1] * math.exp(mu - 0.5 * sigma2 + eps))
        sigma2 = omega + alpha * eps**2 + beta * sigma2
    return prices
