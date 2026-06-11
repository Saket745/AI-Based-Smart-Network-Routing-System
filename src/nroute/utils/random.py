"""Seeded random number generator for reproducibility."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence

import numpy as np

T = TypeVar("T")


class SeededRandom:
    """
    Wraps standard library random and NumPy generator to ensure consistent seeding.
    """

    def __init__(self, seed: int | None = None) -> None:
        """
        Initialize the SeededRandom instance.

        Args:
            seed: Optional integer seed. If None, system entropy is used.
        """
        self.seed = seed
        self.random = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

    def randint(self, a: int, b: int) -> int:
        """Return a random integer in range [a, b] inclusive."""
        return self.random.randint(a, b)

    def random_float(self) -> float:
        """Return a random float in range [0.0, 1.0)."""
        return self.random.random()

    def uniform(self, a: float, b: float) -> float:
        """Return a random float in range [a, b] inclusive."""
        return self.random.uniform(a, b)

    def choice(self, seq: Sequence[T]) -> T:
        """Choose a random element from a non-empty sequence."""
        return self.random.choice(seq)

    def choices(
        self,
        population: Sequence[T],
        weights: Sequence[float] | None = None,
        k: int = 1,
    ) -> list[T]:
        """Return a k sized list of population elements chosen with replacement."""
        return self.random.choices(population, weights=weights, k=k)

    def shuffle(self, x: list[Any]) -> None:
        """Shuffle list x in place."""
        self.random.shuffle(x)


def get_rng(seed: int | None = None) -> SeededRandom:
    """
    Factory function to get a SeededRandom instance.

    Args:
        seed: Optional integer seed.
    """
    return SeededRandom(seed)
