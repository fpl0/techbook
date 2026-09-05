import re

pattern = re.compile(r"(a+)+b")
print(pattern.match("aaaaaaaaaaaaaaaaaaaaaab") is not None)
