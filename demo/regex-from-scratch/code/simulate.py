def add_state(prog, i, current, seen):
    """Add state i to the set, expanding splits so the set holds no split states."""
    if i in seen:
        return
    seen.add(i)
    state = prog.states[i]
    if state["kind"] == SPLIT:
        add_state(prog, state["a"], current, seen)
        add_state(prog, state["b"], current, seen)
    else:
        current.add(i)


def simulate(prog, entry, text):
    current = set()
    add_state(prog, entry, current, set())
    for ch in text:
        nxt, seen = set(), set()
        for i in current:
            state = prog.states[i]
            if state["kind"] == CONSUME and (state["c"] is None or state["c"] == ch):
                add_state(prog, state["next"], nxt, seen)
        current = nxt
        if not current:
            return False
    return any(prog.states[i]["kind"] == MATCH for i in current)


def full_match(pattern, text):
    prog, entry = compile_pattern(pattern)
    return simulate(prog, entry, text)


for p, t in [("a*b", "aaab"), ("a*b", "aaac"), ("a|b", "b"), ("(ab)*", "ababab"),
             ("a.c", "axc"), ("a*", "")]:
    print(f"{p:8} {t!r:10} {full_match(p, t)}")
