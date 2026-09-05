"""The public face of the engine: compile once, match many times."""
from parse import parse
from machine import compile_pattern
import simulate


class Pattern:
    def __init__(self, source):
        self.source = source
        self.start = compile_pattern(parse(source))

    def fullmatch(self, text):
        return simulate.fullmatch(self.start, text)

    def search(self, text):
        return simulate.search(self.start, text)


def compile(source):
    return Pattern(source)


def fullmatch(source, text):
    return Pattern(source).fullmatch(text)


def search(source, text):
    return Pattern(source).search(text)
