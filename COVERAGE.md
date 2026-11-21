# Test coverage backfill

The project goal was to raise line coverage of `boltons` from 75% to at least
85% by adding behavioural tests, while leaving library code unchanged apart
from minimal fixes for bugs the new tests demonstrated.

## Result

On `main` the suite passes the required gate:

```
$ ./check.sh
pip install -q pytest pytest-cov
python -m pytest -q --cov=boltons --cov-fail-under=85
...
TOTAL                     7522    162    98%
Required test coverage of 85% reached. Total coverage: 97.85%
1050 passed, 24 subtests passed in 3.77s
```

`check.sh` at the repository root is the canonical entry point; it installs
`pytest`/`pytest-cov` and runs the same command the CI workflow uses. The run
takes a few seconds, well under the 30 second budget.

## Layout

Tests for module `boltons/X.py` live in `tests/test_X.py`, so modules were
backfilled independently without workers editing the same file. The tests
assert documented behaviour: return values, raised exceptions, and side
effects. There are no import-only or smoke tests.

The remaining uncovered lines (162 in total) fall into three groups:

- Windows-only code paths (for example `fileutils` `fcntl`/Windows branches).
- Import-time fallbacks that only run when an optional dependency or a newer
  standard-library feature is missing.
- Platform-specific socket and encoding branches that cannot be exercised
  portably on Linux.

## Minimal library fixes

Four small fixes under `boltons/` were required by new behavioural tests. Each
is covered by the test named below.

1. `boltons/mboxutils.py` — `mbox_readonlydir.flush()` compared the binary
   buffer to `''`, which is never true for `bytes`, so the streaming loop did
   not stop at EOF correctly. Changed to `if not buffer`.
   Test: `tests/test_mboxutils.py::test_delete_with_maxmem_streams_in_chunks`.

2. `boltons/setutils.py` — `_ComplementSet.update()`/`discard()` applied
   intersection where set difference was required (and vice versa) for
   complement operands, so results disagreed with ordinary `set` math.
   Test: `tests/test_setutils.py::test_complement_set_identities`.

3. `boltons/timeutils.py` — the `daterange()` error message used `% step`
   instead of `% (step,)`, so an invalid step of the wrong shape raised a
   formatting `TypeError` instead of the intended `ValueError`. Fixed the
   formatting and kept the message minimal.
   Test: `tests/test_timeutils.py::test_daterange_argument_validation`.

4. `boltons/excutils.py` — `_DeferredLine.__str__` returned `None` when
   `linecache` had no source for a frame, but Python requires `__str__` to
   return `str`; formatting a captured traceback over such a frame raised
   `TypeError: __str__ returned non-string`. It now returns `''`, matching the
   "no source available" case.
   Test: `tests/test_excutils.py` (`test_deferred_line_*`).
