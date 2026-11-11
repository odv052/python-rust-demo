import random

import pytest

import fuzzy_rs
import py_impl

DISTANCES = [py_impl.levenshtein, fuzzy_rs.levenshtein]

BATCH_VARIANTS = [
    fuzzy_rs.best_matches,
    fuzzy_rs.best_matches_nogil,
    fuzzy_rs.best_matches_parallel,
]

KNOWN_PAIRS = [
    ("kitten", "sitting", 3),
    ("", "", 0),
    ("", "abc", 3),
    ("abc", "", 3),
    ("same", "same", 0),
    ("café", "cafe", 1),  # one character, even though "é" is two bytes in UTF-8
    ("İstanbul", "Istanbul", 1),
    ("🐍🦀", "🦀", 1),
]


@pytest.mark.parametrize("distance", DISTANCES)
@pytest.mark.parametrize("a, b, expected", KNOWN_PAIRS)
def test_known_pairs(distance, a, b, expected):
    assert distance(a, b) == expected
    assert distance(b, a) == expected


def random_word(rng):
    return "".join(rng.choices("abcçşğıöü", k=rng.randint(0, 8)))


def test_all_variants_agree_on_random_inputs():
    rng = random.Random(42)
    for _ in range(50):
        queries = [random_word(rng) for _ in range(rng.randint(1, 20))]
        candidates = [random_word(rng) for _ in range(rng.randint(1, 20))]

        expected = py_impl.best_matches(queries, candidates)
        assert py_impl.best_matches(queries, candidates, fuzzy_rs.levenshtein) == expected
        for batch in BATCH_VARIANTS:
            assert batch(queries, candidates) == expected


def test_ties_go_to_the_first_candidate():
    candidates = ["ab", "ac", "ad"]
    for batch in BATCH_VARIANTS:
        assert batch(["aa"], candidates) == [("ab", 1)]


def test_empty_candidates_raise_value_error_everywhere():
    with pytest.raises(ValueError):
        py_impl.best_matches(["a"], [])
    with pytest.raises(ValueError):
        py_impl.best_matches(["a"], [], fuzzy_rs.levenshtein)
    for batch in BATCH_VARIANTS:
        with pytest.raises(ValueError):
            batch(["a"], [])
