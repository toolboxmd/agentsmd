#!/usr/bin/env python3
"""Deliver Muse SessionStart to operations-routing."""
from _adapter import run

if __name__ == "__main__":
    raise SystemExit(run('SessionStart', 'operations-routing'))
