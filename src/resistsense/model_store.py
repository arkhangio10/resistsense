from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .modeling import ModelBundle, load_model


def artifact_name(antibiotic: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", antibiotic.lower()).strip("_")
    return f"{safe}.joblib"


@lru_cache(maxsize=32)
def get_model(model_dir: str, antibiotic: str) -> ModelBundle | None:
    path = Path(model_dir) / artifact_name(antibiotic)
    return load_model(path) if path.is_file() else None
