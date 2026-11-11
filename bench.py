"""Benchmark: pure Python vs several flavours of the Rust module."""

import argparse
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor

import fuzzy_rs
import py_impl

FIRST = ["Ahmet", "Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Emre", "Selin",
         "Anna", "James", "María", "Lukas", "Sofia", "Noah", "Chloé", "Dmitry"]
LAST = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Öztürk", "Aydın", "Doğan",
        "Smith", "García", "Müller", "Rossi", "Novak", "Dubois", "Ivanova", "Kim"]
LETTERS = "abcdefghijklmnopqrstuvwxyzçğıöşü"


IMPLEMENTATIONS = {
    "Pure Python": py_impl.best_matches,
    "Rust, per pair": lambda q, c: py_impl.best_matches(q, c, fuzzy_rs.levenshtein),
    "Rust, batch": fuzzy_rs.best_matches,
    "Rust, batch + rayon (all cores)": fuzzy_rs.best_matches_parallel,
}

# Same Rust code, single-threaded; the only difference is whether the GIL is held
THREADING_VARIANTS = {
    "Rust, GIL held": fuzzy_rs.best_matches,
    "Rust, GIL released": fuzzy_rs.best_matches_nogil,
}


def add_typo(word, rng):
    """Insert, delete or substitute one random character."""
    i = rng.randrange(len(word))
    kind = rng.choice(["insert", "delete", "substitute"])
    if kind == "insert":
        return word[:i] + rng.choice(LETTERS) + word[i:]
    if kind == "delete":
        return word[:i] + word[i + 1:]
    return word[:i] + rng.choice(LETTERS) + word[i + 1:]


def random_name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)} {rng.randint(1, 999)}"


def random_short_word(rng):
    return "".join(rng.choices(LETTERS, k=rng.randint(3, 6)))


def make_data(n_queries, n_candidates, seed, short=False):
    """Candidates are names (or short words); queries are candidates with 1-3 typos."""
    rng = random.Random(seed)
    make_candidate = random_short_word if short else random_name
    candidates = [make_candidate(rng) for _ in range(n_candidates)]
    queries = []
    for _ in range(n_queries):
        query = rng.choice(candidates)
        for _ in range(rng.randint(1, 3)):
            query = add_typo(query, rng)
        queries.append(query)
    return queries, candidates


def timed(fn, *args):
    start = time.perf_counter()
    fn(*args)
    return time.perf_counter() - start


def verify(queries, candidates):
    """Check that all implementations returns same results"""
    sample = queries[:50]
    expected = py_impl.best_matches(sample, candidates)
    for name, fn in {**IMPLEMENTATIONS, **THREADING_VARIANTS}.items():
        assert fn(sample, candidates) == expected, f"{name} disagrees"


def run_benchmark(queries, candidates):
    print(f"{'Implementation':<33} {'Time':>9} {'Speedup':>9}")
    print("-" * 53)
    baseline = None
    for name, fn in IMPLEMENTATIONS.items():
        seconds = timed(fn, queries, candidates)
        baseline = baseline or seconds
        print(f"{name:<33} {seconds:>8.3f}s {baseline / seconds:>8.1f}x")


def run_in_threads(fn, queries, candidates, workers):
    """Split queries into chunks and process them from a thread pool"""
    chunks = [queries[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda chunk: fn(chunk, candidates), chunks))


def run_threading_demo(queries, candidates, workers):
    """Only the GIL-free variant lets Python threads run Rust code concurrently"""
    print(f"{'From Python threads':<22} {'1 thread':>9} {f'{workers} threads':>11} {'Scaling':>8}")
    print("-" * 53)
    for name, fn in THREADING_VARIANTS.items():
        one = timed(run_in_threads, fn, queries, candidates, 1)
        many = timed(run_in_threads, fn, queries, candidates, workers)
        print(f"{name:<22} {one:>8.3f}s {many:>10.3f}s {one / many:>7.1f}x")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=int, default=800)
    parser.add_argument("--candidates", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    parser.add_argument("--short", action="store_true",
                        help="short words (3-6 chars): FFI overhead matters more")
    args = parser.parse_args()

    queries, candidates = make_data(args.queries, args.candidates, args.seed, args.short)
    print(f"CPU cores: {os.cpu_count()}")
    print(f"Data: {len(queries):,} queries x {len(candidates):,} candidates\n")

    verify(queries, candidates)
    run_benchmark(queries, candidates)
    print()
    run_threading_demo(queries, candidates, args.workers)


if __name__ == "__main__":
    main()
