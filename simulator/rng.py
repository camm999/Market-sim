# simulator/rng.py
"""a single, explicit source of randomness for the simulation loops.

the analysis scripts used to call `random.seed(seed)` and then let every
draw come out of the module-global generator. that works, but reproducibility
then depends on nothing else having touched the global state in between, and
two sweeps can't run side by side. taking a `random.Random` instance instead
makes a run reproducible by construction rather than by convention.

`simulator/gbm_flow.py` already generated its price paths this way; this
extends the same treatment to the order-flow simulators.
"""

import random
from typing import Optional, Protocol, Sequence, TypeVar

_T = TypeVar("_T")


class RandomSource(Protocol):
    """the slice of `random.Random` the simulators actually use.

    written as a Protocol rather than `random.Random` so the module-global
    `random` itself still satisfies it - that keeps `random.seed(...)` + an
    un-passed rng working exactly as it did before.
    """

    def random(self) -> float: ...

    def randint(self, a: int, b: int) -> int: ...

    def choice(self, seq: Sequence[_T]) -> _T: ...


def resolve(rng: Optional[RandomSource]) -> RandomSource:
    """an explicit generator if one was given, else the module-global `random`."""
    return rng if rng is not None else random
