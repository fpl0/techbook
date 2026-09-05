"""Run the machine over the text, holding every live state at once."""


def add_state(states, s, seen):
    """Add `s`, following split states eagerly; `seen` breaks cycles."""
    if s is None or id(s) in seen:
        return
    seen.add(id(s))
    if s.ch is None and not s.matched:      # a split: take both arms
        add_state(states, s.out, seen)
        add_state(states, s.alt, seen)
    else:
        states.append(s)


def step(current, ch):
    """Every state one character further on. A set, so no path is counted twice."""
    following, seen = [], set()
    for s in current:
        if s.ch is not None and (s.ch == "." or s.ch == ch):
            add_state(following, s.out, seen)
    return following


def fullmatch(start, text):
    current = []
    add_state(current, start, set())
    for ch in text:
        current = step(current, ch)
        if not current:
            return False
    return any(s.matched for s in current)


def search(start, text):
    """Unanchored: re-enter the start state before every character."""
    current, seen = [], set()
    add_state(current, start, seen)
    for ch in text:
        if any(s.matched for s in current):
            return True
        current = step(current, ch)
        add_state(current, start, {id(s) for s in current})
    return any(s.matched for s in current)
