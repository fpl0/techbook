"""How long does a failing match take as the input grows by one character?"""
import re
import time


def seconds(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


if __name__ == "__main__":
    pattern = re.compile(r"(a+)+b")
    previous = None
    for n in range(18, 25):
        text = "a" * n
        t = seconds(lambda: pattern.fullmatch(text))
        ratio = f"{t / previous:4.1f}x" if previous else "    "
        print(f"n={n}  {t * 1000:8.1f} ms  {ratio}")
        previous = t
