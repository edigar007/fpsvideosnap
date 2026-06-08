# Technical Debt

## Package Layout Migration

Current packaging keeps the existing `src.*` import surface and uses
`find_namespace_packages(include=["src", "src.*"])` plus `py_modules=["main"]`.
This is the low-risk compatibility path for editable installs and the
`fpsvideosnap` console script.

Long term, migrate to a conventional package layout:

```text
src/
  fpsvideosnap/
    __init__.py
    __main__.py
    cli.py
    ai/
    audio/
    clip/
    config/
    pipeline/
    tools/
    video/
```

Do this separately from pipeline or detection refactors because current tests,
mock paths, scripts, and user-facing imports still depend on `src.*`.
