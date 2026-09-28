#!/usr/bin/env python3
"""Run serial Go tests without inheriting the owner's global guidance or skills."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile


def main() -> int:
    # Resolve before changing HOME, preserving the existing dependency/build caches.
    caches = json.loads(
        subprocess.check_output(
            ["go", "env", "-json", "GOCACHE", "GOMODCACHE", "GOPATH"], text=True
        )
    )
    with tempfile.TemporaryDirectory(prefix="shelley-go-tests-") as home:
        return subprocess.call(
            ["go", "test", "-parallel", "1", "./..."],
            env=os.environ | caches | {"HOME": home},
        )


if __name__ == "__main__":
    raise SystemExit(main())
