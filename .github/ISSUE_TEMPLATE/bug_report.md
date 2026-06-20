---
name: Bug report
about: Something doesn't work as documented
title: ""
labels: bug
---

**What happened**
A clear, short description.

**Minimal repro**
The smallest snippet that triggers it:

```python
from distillory import Memory
mem = Memory.open("repro.db", synth="none", embed="hash")
# ...
```

**Expected vs actual**

**Environment** — paste `mem doctor` (or `Memory.open(...).doctor()`):

```json
```

- distillory version:
- Python version / OS:
