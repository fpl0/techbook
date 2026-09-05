CONSUME, SPLIT, MATCH = "consume", "split", "match"


class Program:
    def __init__(self):
        self.states = []

    def emit(self, kind, **kw):
        self.states.append({"kind": kind, **kw})
        return len(self.states) - 1

    def __len__(self):
        return len(self.states)


def compile_node(node, prog, cont):
    """Emit states for `node`, continuing to state index `cont`. Returns the entry."""
    if node is None:
        return cont
    if isinstance(node, Char):
        return prog.emit(CONSUME, c=node.c, next=cont)
    if isinstance(node, Dot):
        return prog.emit(CONSUME, c=None, next=cont)
    if isinstance(node, Cat):
        right = compile_node(node.right, prog, cont)
        return compile_node(node.left, prog, right)
    if isinstance(node, Alt):
        a = compile_node(node.left, prog, cont)
        b = compile_node(node.right, prog, cont)
        return prog.emit(SPLIT, a=a, b=b)
    if isinstance(node, Star):
        split = prog.emit(SPLIT, a=cont, b=cont)      # placeholder, patched below
        body = compile_node(node.inner, prog, split)
        prog.states[split]["a"] = body
        prog.states[split]["b"] = cont
        return split
    raise TypeError(node)


def compile_pattern(src):
    prog = Program()
    match_state = prog.emit(MATCH)
    entry = compile_node(Parser(src).parse(), prog, match_state)
    return prog, entry


prog, entry = compile_pattern("a*b")
for i, s in enumerate(prog.states):
    print(i, s, "<-- entry" if i == entry else "")
