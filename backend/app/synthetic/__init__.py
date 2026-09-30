"""Synthetic ("demo") data: a hand-written world spec + a fixed seed -> CSV export ->
database. Every generated row is marked is_synthetic = true. See docs/SYNTHETIC_DATA_SPEC.md.

    python -m app.cli.synthetic all      # generate + load + validate
"""
