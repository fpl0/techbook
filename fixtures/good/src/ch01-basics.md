# Chapter 1: Basics

A plain run block with matching output.

```python run
print("hello")
```

```output
hello
```

An env chain. This block defines something...

```python run env=ch1
def double(n):
    return n * 2
```

...and this one uses it, as the reader would experience it.

```python run env=ch1
print(double(21))
```

```output
42
```

A deliberate error demo.

```python expect-error expect="ZeroDivisionError"
1 / 0
```

A compile-only check.

```python check
def unused(a: int) -> int:
    return a + 1
```

Shell works too.

```bash run
echo "from bash"
```

```output
from bash
```

Node works too.

```js run
console.log(2 + 2);
```

```output
4
```

Config fragments are declared, not smuggled in.

```yaml literal why="illustrative config, not executed anywhere"
server:
  port: 8080
```

Something that genuinely cannot run here.

```python norun why="needs a paid API key"
import os
client = os.environ["OPENAI_API_KEY"]
```
