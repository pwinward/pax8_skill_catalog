"""Per-call observability.

The PRD asks for no logging. This exists because PRD §7 asks for responsiveness
without prescribing a threshold, so the requirement is met by measuring rather than
asserting — and a duration per call is what backs the figures reported in the README.

Stdout rather than a table in the catalog: telemetry should not live inside the
system it observes, and both EKS and Lambda collect stdout unchanged.
"""

import json
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator


@contextmanager
def logged(tool: str, **context: Any) -> Iterator[dict]:
    """Time a tool call and emit one JSON line for it.

    The yielded dict is for the caller to record the outcome in; arguments are
    deliberately not logged, since a publish would put whole skill files in the log.
    """
    started = time.perf_counter()
    record: dict[str, Any] = {"tool": tool, **context}
    try:
        yield record
        record.setdefault("outcome", "ok")
    except Exception as error:
        record["outcome"] = "error"
        record["error"] = type(error).__name__
        raise
    finally:
        record["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        print(json.dumps(record), file=sys.stdout, flush=True)
