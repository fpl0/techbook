def match_here(pattern, text):
    if not pattern:
        return True
    if pattern[0] == "." or (text and pattern[0] == text[0]):
        return match_here(pattern[1:], text[1:])
    return False

print(match_here("a.c", "abc"), match_here("a.c", "axc"), match_here("a.c", "ab"))
