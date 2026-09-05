"""Time the three matchers on the same family of inputs. Best of three runs."""
import re
import time
import backtrack
import tinyre


def timed(fn, repeats=3):
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000


if __name__ == "__main__":
    pattern = "a*a*a*b"
    compiled = tinyre.compile(pattern)
    print(f"{'n':>6} {'backtrack':>10} {'tinyre':>10} {'re':>10}")
    for n in (40, 80, 160, 320):
        text = "a" * n
        row = (timed(lambda: backtrack.match_here(pattern, text)),
               timed(lambda: compiled.fullmatch(text)),
               timed(lambda: re.fullmatch(pattern, text)))
        print(f"{n:>6} {row[0]:>8.1f}ms {row[1]:>8.2f}ms {row[2]:>8.3f}ms")
