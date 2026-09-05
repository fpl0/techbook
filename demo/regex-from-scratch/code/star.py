def match_here(pattern, text):
    if not pattern:
        return True
    if len(pattern) >= 2 and pattern[1] == "*":
        return match_star(pattern[0], pattern[2:], text)
    if pattern[0] == "." or (text and pattern[0] == text[0]):
        return match_here(pattern[1:], text[1:])
    return False


def match_star(c, pattern, text):
    i = 0
    while True:
        if match_here(pattern, text[i:]):
            return True
        if i < len(text) and (c == "." or text[i] == c):
            i += 1
        else:
            return False


def match(pattern, text):
    return any(match_here(pattern, text[i:]) for i in range(len(text) + 1))


for p, t in [("a*b", "aaab"), ("a*b", "b"), ("a.*z", "abcz"), ("a*b", "aaac")]:
    print(f"{p!r:8} {t!r:8} {match(p, t)}")
