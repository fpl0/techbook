from dataclasses import dataclass


@dataclass
class Char:  c: str
@dataclass
class Dot:   pass
@dataclass
class Star:  inner: object
@dataclass
class Cat:   left: object; right: object
@dataclass
class Alt:   left: object; right: object


class Parser:
    def __init__(self, src):
        self.src, self.i = src, 0

    def peek(self):
        return self.src[self.i] if self.i < len(self.src) else None

    def parse(self):
        node = self.alternation()
        if self.i != len(self.src):
            raise SyntaxError(f"unexpected {self.peek()!r} at {self.i}")
        return node

    def alternation(self):
        node = self.concatenation()
        while self.peek() == "|":
            self.i += 1
            node = Alt(node, self.concatenation())
        return node

    def concatenation(self):
        node = None
        while self.peek() not in (None, "|", ")"):
            atom = self.repeat()
            node = atom if node is None else Cat(node, atom)
        return node

    def repeat(self):
        node = self.atom()
        while self.peek() == "*":
            self.i += 1
            node = Star(node)
        return node

    def atom(self):
        c = self.peek()
        if c == "(":
            self.i += 1
            node = self.alternation()
            if self.peek() != ")":
                raise SyntaxError("unclosed (")
            self.i += 1
            return node
        self.i += 1
        return Dot() if c == "." else Char(c)


print(Parser("a*b").parse())
print(Parser("a|b").parse())
