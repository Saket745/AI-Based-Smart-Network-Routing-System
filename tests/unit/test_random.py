from __future__ import annotations

from nroute.utils.random import SeededRandom, get_rng


def test_seeded_random_reproducibility() -> None:
    """Verify that same seed produces same sequence of random numbers."""
    seed = 42
    rng1 = SeededRandom(seed)
    rng2 = SeededRandom(seed)

    # Test randint
    assert rng1.randint(0, 100) == rng2.randint(0, 100)
def test_seeded_random_initialization() -> None:
    """Test that SeededRandom can be initialized with and without a seed."""
    rng1 = SeededRandom(seed=42)
    assert rng1.seed == 42
    assert rng1.random is not None
    assert rng1.np_rng is not None

    rng2 = SeededRandom()
    assert rng2.seed is None
    assert rng2.random is not None
    assert rng2.np_rng is not None


def test_seeded_random_reproducibility() -> None:
    """Test that the same seed produces the same sequence of numbers."""
    seed = 123
    rng1 = SeededRandom(seed=seed)
    rng2 = SeededRandom(seed=seed)
    # Test random_float
    assert rng1.random_float() == rng2.random_float()

    # Test uniform
    assert rng1.uniform(0, 1) == rng2.uniform(0, 1)

    # Test choice
    items = ["a", "b", "c", "d"]
    assert rng1.choice(items) == rng2.choice(items)

    # Test choices
    assert rng1.choices(items, k=2) == rng2.choices(items, k=2)
    # Test randint
    assert rng1.randint(1, 100) == rng2.randint(1, 100)

    # Test uniform
    assert rng1.uniform(0.0, 1.0) == rng2.uniform(0.0, 1.0)

    # Test choice
    seq = ["a", "b", "c", "d"]
    assert rng1.choice(seq) == rng2.choice(seq)

    # Test choices
    assert rng1.choices(seq, k=2) == rng2.choices(seq, k=2)

    # Test shuffle
    list1 = [1, 2, 3, 4, 5]
    list2 = [1, 2, 3, 4, 5]
    rng1.shuffle(list1)
    rng2.shuffle(list2)
    assert list1 == list2

    # Test np_rng reproducibility
    assert rng1.np_rng.random() == rng2.np_rng.random()


def test_seeded_random_different_seeds() -> None:
    """Verify that different seeds produce different sequences."""
    rng1 = SeededRandom(42)
    rng2 = SeededRandom(43)

    # Note: There's a tiny chance they could produce the same first number,
    # but highly unlikely for multiple calls.

    # Check that they are likely different
    results1 = [rng1.random_float() for _ in range(10)]
    results2 = [rng2.random_float() for _ in range(10)]
    assert results1 != results2


def test_seeded_random_no_seed() -> None:
    """Verify that no seed produces different sequences (using system entropy)."""
    rng1 = SeededRandom()
    rng2 = SeededRandom()

    # Check that they are different
    """Test that different seeds produce different sequences."""
    rng1 = SeededRandom(seed=42)
    rng2 = SeededRandom(seed=43)

    # It's theoretically possible they produce the same first value,
    # but highly unlikely for multiple calls.
    results1 = [rng1.random_float() for _ in range(10)]
    results2 = [rng2.random_float() for _ in range(10)]
    assert results1 != results2


def test_get_rng() -> None:
    """Verify factory function get_rng."""
    seed = 123
    rng = get_rng(seed)
    assert isinstance(rng, SeededRandom)
    assert rng.seed == seed


def test_randint_range() -> None:
    """Verify randint stays within range."""
    rng = SeededRandom(42)
def test_randint() -> None:
    """Test randint produces values in the correct range."""
    rng = SeededRandom(seed=42)
    for _ in range(100):
        val = rng.randint(5, 10)
        assert 5 <= val <= 10


def test_random_float_range() -> None:
    """Verify random_float stays within [0, 1)."""
    rng = SeededRandom(42)
def test_random_float() -> None:
    """Test random_float produces values in [0.0, 1.0)."""
    rng = SeededRandom(seed=42)
    for _ in range(100):
        val = rng.random_float()
        assert 0.0 <= val < 1.0


def test_uniform_range() -> None:
    """Verify uniform stays within range."""
    rng = SeededRandom(42)
    for _ in range(100):
        val = rng.uniform(10.5, 20.5)
        assert 10.5 <= val <= 20.5


def test_choice_selection() -> None:
    """Verify choice selects from the sequence."""
    rng = SeededRandom(42)
    items = ["apple", "banana", "cherry"]
    for _ in range(20):
        assert rng.choice(items) in items


def test_choices_selection() -> None:
    """Verify choices selects from the sequence with correct size."""
    rng = SeededRandom(42)
    items = ["apple", "banana", "cherry"]
    k = 5
    selected = rng.choices(items, k=k)
    assert len(selected) == k
    for item in selected:
        assert item in items


def test_choices_weights() -> None:
    """Verify choices respects weights (basic check)."""
    rng = SeededRandom(42)
    items = ["a", "b"]
    # If "b" has 0 weight, it should never be picked
    selected = rng.choices(items, weights=[1.0, 0.0], k=100)
    assert all(item == "a" for item in selected)


def test_shuffle_in_place() -> None:
    """Verify shuffle modifies list in place."""
    rng = SeededRandom(42)
    original = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    shuffled = original.copy()
    rng.shuffle(shuffled)
    # Shuffled should have same elements
    assert sorted(shuffled) == sorted(original)
    # Likely different order
    assert shuffled != original
def test_uniform() -> None:
    """Test uniform produces values in the correct range."""
    rng = SeededRandom(seed=42)
    for _ in range(100):
        val = rng.uniform(2.5, 7.5)
        assert 2.5 <= val <= 7.5


def test_choice() -> None:
    """Test choice selects from the sequence."""
    rng = SeededRandom(seed=42)
    seq = [10, 20, 30]
    for _ in range(50):
        assert rng.choice(seq) in seq


def test_choices() -> None:
    """Test choices selects multiple elements with replacement."""
    rng = SeededRandom(seed=42)
    seq = [1, 2, 3]
    result = rng.choices(seq, k=10)
    assert len(result) == 10
    for item in result:
        assert item in seq


def test_shuffle() -> None:
    """Test shuffle reorders the list in-place."""
    rng = SeededRandom(seed=42)
    original = list(range(20))
    shuffled = list(range(20))
    rng.shuffle(shuffled)
    assert sorted(shuffled) == original
    # Very unlikely to be identical after shuffle for 20 elements
    assert shuffled != original


def test_get_rng() -> None:
    """Test get_rng factory function."""
    rng = get_rng(seed=10)
    assert isinstance(rng, SeededRandom)
    assert rng.seed == 10
