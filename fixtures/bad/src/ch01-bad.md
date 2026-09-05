# Chapter 1: Bad

Untagged code block (should be a lint error).

```python
print("untagged")
```

Literal with no why (should be a lint error).

```json literal
{"a": 1}
```

norun with no why (should be a lint error).

```python norun
print("x")
```

Two modes at once (should be a lint error).

```python run check
print("x")
```

Hallucinated dependency (should be caught before execution).

```python run
import quantumflux_helper
print(quantumflux_helper.go())
```

Unknown language for an executable mode.

```cobol run
DISPLAY "HI".
```

Bad nondet value.

```python run nondet=maybe
print("x")
```

Orphan output block.

```output
nothing precedes me
```
