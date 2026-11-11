use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;

type Match = (String, usize);

/// Levenshtein distance over chars. `row` is a scratch buffer the caller can reuse.
fn distance(a: &[char], b: &[char], row: &mut Vec<usize>) -> usize {
    row.clear();
    row.extend(0..=b.len());
    for (i, ca) in a.iter().enumerate() {
        let mut diag = row[0]; // row[j] from the previous iteration of `i`
        row[0] = i + 1;
        for (j, cb) in b.iter().enumerate() {
            let above = row[j + 1];
            let cost = usize::from(ca != cb);
            row[j + 1] = (above + 1).min(row[j] + 1).min(diag + cost);
            diag = above;
        }
    }
    row[b.len()]
}

fn to_chars(s: &str) -> Vec<char> {
    s.chars().collect()
}

/// Closest candidate to `query`; the first one wins on ties.
/// `chars` holds the candidates already converted by `to_chars`.
fn best_match(query: &str, candidates: &[String], chars: &[Vec<char>], row: &mut Vec<usize>) -> Match {
    let query = to_chars(query);
    let (i, dist) = chars
        .iter()
        .map(|c| distance(&query, c, row))
        .enumerate()
        .min_by_key(|&(_, dist)| dist)
        .expect("candidates are checked to be non-empty");
    (candidates[i].clone(), dist)
}

/// Single-threaded batch: candidates are converted once, the scratch row is reused.
fn match_all(queries: &[String], candidates: &[String]) -> Vec<Match> {
    let chars: Vec<Vec<char>> = candidates.iter().map(|c| to_chars(c)).collect();
    let mut row = Vec::new();
    queries
        .iter()
        .map(|q| best_match(q, candidates, &chars, &mut row))
        .collect()
}

/// Same behaviour as Python's `min()` on an empty sequence.
fn check_not_empty(candidates: &[String]) -> PyResult<()> {
    if candidates.is_empty() {
        return Err(PyValueError::new_err("candidates must not be empty"));
    }
    Ok(())
}

/// Variant 2: one pair per call. Python loops, so we cross the FFI boundary per pair.
#[pyfunction]
fn levenshtein(a: &str, b: &str) -> usize {
    distance(&to_chars(a), &to_chars(b), &mut Vec::new())
}

/// Variant 3: the whole batch in one call, single-threaded, GIL held.
#[pyfunction]
fn best_matches(queries: Vec<String>, candidates: Vec<String>) -> PyResult<Vec<Match>> {
    check_not_empty(&candidates)?;
    Ok(match_all(&queries, &candidates))
}

/// Variant 4: the whole batch in one call, single-threaded, GIL released.
#[pyfunction]
fn best_matches_nogil(
    py: Python<'_>,
    // GIL held: PyO3 converts list[str] -> Vec<String> before the body runs.
    queries: Vec<String>,
    candidates: Vec<String>,
) -> PyResult<Vec<Match>> {
    check_not_empty(&candidates)?;
    // GIL released: pure Rust data only, other Python threads keep running.
    Ok(py.detach(|| match_all(&queries, &candidates)))
    // GIL reacquired: PyO3 converts the Vec back to list[tuple[str, int]].
}

/// Variant 5: the whole batch in one call, GIL released, parallel over queries.
#[pyfunction]
fn best_matches_parallel(
    py: Python<'_>,
    // GIL held: PyO3 converts list[str] -> Vec<String> before the body runs.
    queries: Vec<String>,
    candidates: Vec<String>,
) -> PyResult<Vec<Match>> {
    check_not_empty(&candidates)?;
    // GIL released: pure Rust data only, other Python threads keep running.
    Ok(py.detach(|| {
        let chars: Vec<Vec<char>> = candidates.iter().map(|c| to_chars(c)).collect();
        queries
            .par_iter()
            .map_init(Vec::new, |row, q| best_match(q, &candidates, &chars, row))
            .collect()
    }))
    // GIL reacquired: PyO3 converts the Vec back to list[tuple[str, int]].
}

#[pymodule]
fn fuzzy_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(levenshtein, m)?)?;
    m.add_function(wrap_pyfunction!(best_matches, m)?)?;
    m.add_function(wrap_pyfunction!(best_matches_nogil, m)?)?;
    m.add_function(wrap_pyfunction!(best_matches_parallel, m)?)?;
    Ok(())
}
