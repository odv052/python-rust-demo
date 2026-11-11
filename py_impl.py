"""Pure Python baseline"""


def levenshtein(a: str, b: str) -> int:
    """Levenshtein distance over Unicode characters"""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = ca != cb
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def best_match(query, candidates, distance):
    """Closest candidate to `query`; the first one wins on ties"""
    scored = ((c, distance(query, c)) for c in candidates)
    return min(scored, key=lambda pair: pair[1])


def best_matches(queries, candidates, distance=levenshtein):
    """For each query, return (best_match, distance)"""
    return [best_match(q, candidates, distance) for q in queries]
