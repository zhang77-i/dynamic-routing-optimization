from __future__ import annotations

import argparse
import os
import sys
import sysconfig
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# On Windows, pandas/pyarrow and OR-Tools can load different protobuf
# runtimes.  Preloading OR-Tools before the data stack keeps the DLL search
# order deterministic and avoids an intermittent WinError 127.
_ORTOOLS_DLL_HANDLE = None
if os.name == "nt":
    _ortools_dll_path = (
        Path(sysconfig.get_paths()["purelib"]) / "ortools" / ".libs"
    )
    if _ortools_dll_path.exists():
        _ORTOOLS_DLL_HANDLE = os.add_dll_directory(str(_ortools_dll_path))

from ortools.sat.python import cp_model as _cp_model_preload

from lade_routing.experiments import run_optimization_experiments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run dynamic greedy, OR-Tools CP-SAT, rolling ALNS and "
            "offline ALNS routing experiments."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "project.yaml",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_optimization_experiments(parse_args().config)
