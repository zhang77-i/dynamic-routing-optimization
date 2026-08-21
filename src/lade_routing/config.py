from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    data: dict[str, Path]
    processing: dict[str, Any]
    optimization: dict[str, Any]
    random_seed: int


def load_config(config_path: str | Path) -> ProjectConfig:
    config_file = Path(config_path).resolve()
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    root = config_file.parent.parent
    data = {
        key: (root / relative).resolve()
        for key, relative in payload["data"].items()
    }
    return ProjectConfig(
        root=root,
        data=data,
        processing=payload["processing"],
        optimization=payload.get("optimization", {}),
        random_seed=int(payload["project"]["random_seed"]),
    )
