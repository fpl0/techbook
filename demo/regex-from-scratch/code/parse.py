"""Recursive descent, one method per precedence level: alt < concat < repeat < atom."""
from nodes import Char, Dot, Concat, Alt, Repeat


class Parser:
    def __init__(self, pattern):
        self.src = pattern
        self.pos = 0

    def peek(self):
        return self.src[self.pos] if self.pos < len(self.src) else None

    def take(self):
        ch = self.peek()
        self.pos += 1
        return ch

    def parse(self):
        node = self.alt()
        if self.peek() is not None:
            raise SyntaxError(f"unexpected {self.peek()!r} at {self.pos}")
        return node

    def alt(self):
        node = self.concat()
        while self.peek() == "|":
            self.take()
            node = Alt(node, self.concat())
        return node

    def concat(self):
        node = self.repeat()
        while self.peek() not in (None, "|", ")"):
            node = Concat(node, self.repeat())
        return node

    def repeat(self):
        node = self.atom()
        if self.peek() in ("*", "+", "?"):
            op = self.take()
            node = Repeat(node, min=1 if op == "+" else 0, many=op != "?")
        if self.peek() in ("*", "+", "?"):
            raise SyntaxError(f"multiple repeat at {self.pos}")
        return node

    def atom(self):
        ch = self.take()
        if ch == "(":
            node = self.alt()
            if self.take() != ")":
                raise SyntaxError("missing )")
            return node
        if ch == ".":
            return Dot()
        if ch is None or ch in "|)*+?":
            raise SyntaxError(f"expected a character, got {ch!r} at {self.pos - 1}")
        return Char(ch)


def parse(pattern):
    return Parser(pattern).parse()
