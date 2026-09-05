"""Differential test: every small pattern, every short string, tinyre against re."""
import itertools
import re
import tinyre

ALPHABET = "ab"
PIECES = ["a", "b", ".", "*", "+", "?", "|", "(", ")"]


def patterns(max_len):
    """Every string of PIECES up to max_len that both engines accept."""
    for n in range(1, max_len + 1):
        for parts in itertools.product(PIECES, repeat=n):
            source = "".join(parts)
            try:
                re.compile(source)
                tinyre.compile(source)
            except (re.error, SyntaxError):
                continue
            yield source


def strings(max_len):
    for n in range(max_len + 1):
        for chars in itertools.product(ALPHABET, repeat=n):
            yield "".join(chars)


def run(max_pattern=4, max_string=3):
    cases = mismatches = 0
    for source in patterns(max_pattern):
        ours, theirs = tinyre.compile(source), re.compile(source)
        for text in strings(max_string):
            cases += 1
            if ours.fullmatch(text) != (theirs.fullmatch(text) is not None):
                mismatches += 1
                if mismatches <= 5:
                    print(f"  {source!r} on {text!r}: tinyre says "
                          f"{ours.fullmatch(text)}, re says the opposite")
    return cases, mismatches


if __name__ == "__main__":
    cases, mismatches = run()
    print(f"{cases} cases, {mismatches} mismatches")
