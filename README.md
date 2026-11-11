# Turning a Python Bottleneck into a Rust Module

The problem: **fuzzy matching**. For each string in `queries`, find the
closest string in `candidates` by
[Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance),
counted in Unicode characters (not bytes). Returns a list of `(best_match, distance)`.

Five implementations, which all return identical results:

| # | Implementation | Where | Idea |
|---|---|---|---|
| 1 | Pure Python | `py_impl.py` | The "before": standard two-row DP |
| 2 | Rust, per pair | `src/lib.rs` (`levenshtein`) | Python loop, one FFI call per pair |
| 3 | Rust, batch | `src/lib.rs` (`best_matches`) | Whole batch in one call, GIL held |
| 4 | Rust, batch, GIL released | `src/lib.rs` (`best_matches_nogil`) | Same, single-threaded, but other Python threads can run |
| 5 | Rust, batch + rayon | `src/lib.rs` (`best_matches_parallel`) | GIL released, `rayon` over queries |

The batch variants (3-5) convert every string to `Vec<char>` once per call and
reuse one DP buffer. Variant 2 has to redo that work for every pair.

Stack: [PyO3](https://pyo3.rs) 0.30 (`Python::detach` releases the GIL),
[maturin](https://www.maturin.rs), [rayon](https://docs.rs/rayon). The wheel is
built for the stable ABI (`abi3`), so one wheel covers Python 3.12+.

## Layout

```
src/lib.rs        Rust module (variants 2-5)
py_impl.py        Pure Python baseline (variant 1)
bench.py          Benchmark + threading demo
tests/            pytest suite
```

## Build

You need Rust (stable) and Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install maturin pytest
maturin develop --release
pytest
```

(With [uv](https://docs.astral.sh/uv/): `uv venv && uv pip install maturin pytest`.)

## Run the benchmark

```bash
python bench.py                               # ~10-20 s, mostly pure Python
python bench.py --queries 200 --candidates 500  # quick run
python bench.py --workers 4                   # threads for the threading demo
python bench.py --short                       # short words: FFI overhead matters more
```

The benchmark checks that all variants agree before timing them. The first
table is one call from the main thread. The second table calls variants 3 and 4
from a `ThreadPoolExecutor`, with the queries split into chunks.
Example output (Apple Silicon, 14 cores, Python 3.14):

```
CPU cores: 14
Data: 800 queries x 1,000 candidates

Implementation                         Time   Speedup
-----------------------------------------------------
Pure Python                         13.713s      1.0x
Rust, per pair                       0.321s     42.8x
Rust, batch                          0.147s     93.1x
Rust, batch + rayon (all cores)      0.015s    941.5x

From Python threads     1 thread  14 threads  Scaling
-----------------------------------------------------
Rust, GIL held            0.147s      0.147s     1.0x
Rust, GIL released        0.146s      0.020s     7.5x
```

**Where the rayon speedup comes from.** It is two effects multiplied: compiled
code (13.7 s -> 0.147 s on one core, about 93x) times multiple cores
(0.147 s -> 0.015 s, about 10x on this 14-core machine), roughly 940x in total.

**The threading demo.** Both rows run the same single-threaded Rust code. With
the GIL held, 14 Python threads take turns and nothing gets faster (1.0x). With
the GIL released, they run truly in parallel (7.5x here). Rayon is not used
here on purpose: it would saturate all cores from one thread and hide the effect.

**Short words.** `python bench.py --short` uses 3-6 character words. Each call
now does very little work, so the FFI overhead of per-pair calls dominates:

```
Implementation                         Time   Speedup
-----------------------------------------------------
Pure Python                          1.713s      1.0x
Rust, per pair                       0.123s     14.0x
Rust, batch                          0.015s    116.3x
Rust, batch + rayon (all cores)      0.002s    952.0x
```
