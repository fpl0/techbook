"""Thompson's construction, continuation style: each node is compiled knowing
what state comes after it, so no dangling pointers ever need patching."""
from dataclasses import dataclass
from nodes import Char, Dot, Concat, Alt, Repeat


@dataclass(eq=False)
class State:
    ch: str | None = None          # None on a split state; "." matches anything
    out: object = None             # next state after consuming ch
    alt: object = None             # second branch, split states only
    matched: bool = False


def compile_node(node, cont):
    """Return the entry state for `node`, wired so that finishing it leads to `cont`."""
    if isinstance(node, Char):
        return State(ch=node.ch, out=cont)
    if isinstance(node, Dot):
        return State(ch=".", out=cont)
    if isinstance(node, Concat):
        return compile_node(node.left, compile_node(node.right, cont))
    if isinstance(node, Alt):
        return State(out=compile_node(node.left, cont), alt=compile_node(node.right, cont))
    if isinstance(node, Repeat):
        if not node.many:                             # ?  one pass, or skip it
            return State(out=compile_node(node.child, cont), alt=cont)
        split = State(alt=cont)                       # * and +: a loop through a split
        split.out = compile_node(node.child, split)   # the child leads back to the split
        return split if node.min == 0 else split.out  # * enters at the split, + at the child
    raise TypeError(node)


def compile_pattern(node):
    return compile_node(node, State(matched=True))
