"""Pytest bootstrap.

Its mere presence at the repo root makes pytest insert the root onto
``sys.path`` (rootdir insertion), so tests can ``import config`` and ``import
src`` under a bare ``pytest`` invocation — as CI runs it — not only under
``python -m pytest`` (which adds the cwd itself). No fixtures needed here.
"""
