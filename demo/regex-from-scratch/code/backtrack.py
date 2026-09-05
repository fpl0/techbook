"""A backtracking matcher for literals, dot and star, in the style of Pike's."""


def match_here(pattern, text):
    """Does `pattern` match at the very start of `text`?"""
    if pattern == "":
        return True
    if len(pattern) > 1 and pattern[1] == "*":
        return match_star(pattern[0], pattern[2:], text)
    if text and pattern[0] in (".", text[0]):
        return match_here(pattern[1:], text[1:])
    return False


def match_star(ch, rest, text):
    """Match zero or more `ch`, then `rest`. Longest run first, then give back."""
    i = 0
    while i < len(text) and (ch == "." or text[i] == ch):
        i += 1
    while i >= 0:
        if match_here(rest, text[i:]):
            return True
        i -= 1
    return False


def search(pattern, text):
    """Does `pattern` match anywhere in `text`?"""
    for start in range(len(text) + 1):
        if match_here(pattern, text[start:]):
            return True
    return False
