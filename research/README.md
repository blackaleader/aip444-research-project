# Research package

The [project overview](../README.md) and [team handoff](../handoff_final.md)
live at the repository root. Run Python commands from this `research/` folder.

```sh
python -m venv .venv
# Activate .venv for your operating system.
python -m pip install -e ".[dev]"
python -m pytest tests/unit -q
```

See [T2 integration](docs/t2_integration.md) for benchmark review, portable Pi
worktree setup, source validation and the handoff to Arman and Rehat.
