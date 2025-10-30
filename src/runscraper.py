from __future__ import annotations

import sys
from pathlib import Path

from main import main as cli_main


def run(config_path: Path | None = None) -> int:
    args = []
    if config_path:
        args.extend(["--config", str(config_path)])
    args.append("--run-once")
    return cli_main(args)


if __name__ == "__main__":  # pragma: no cover
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(run(path))
