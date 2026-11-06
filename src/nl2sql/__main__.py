# -*- coding: utf-8 -*-
"""让 `python -m nl2sql ...` 可用。"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
