"""
Standalone stub for tau2.utils and tau2.utils.pydantic_utils.
Replaces all tau2 internal utility dependencies.
"""
import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound=BaseModel)


# ── tau2.utils.pydantic_utils ────────────────────────────────────

class BaseModelNoExtra(BaseModel):
    """BaseModel that forbids extra fields (replaces tau2's BaseModelNoExtra)."""
    model_config = ConfigDict(extra="forbid")


# ── tau2.utils ───────────────────────────────────────────────────

def load_file(path: Any) -> Any:
    """Load JSON file from path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_file(path: Any, data: Any, **kwargs: Any) -> None:
    """Dump data to JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_pydantic_hash(obj: BaseModel) -> str:
    """Get a stable hash of a pydantic model."""
    serialized = obj.model_dump_json()
    return hashlib.md5(serialized.encode()).hexdigest()


def get_dict_hash(d: dict) -> str:
    """Get a stable hash of a dict."""
    serialized = json.dumps(d, sort_keys=True)
    return hashlib.md5(serialized.encode()).hexdigest()


def update_pydantic_model_with_dict(model: T, update_data: dict) -> T:
    """Update a pydantic model with a dict of new values."""
    if not update_data:
        return model
    current = model.model_dump()
    current.update(update_data)
    return type(model).model_validate(current)


# ── TOML support (for telecom db.toml) ───────────────────────────
def load_file(path):
    """Load JSON or TOML file from path."""
    import json
    path = str(path)
    if path.endswith('.toml'):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(path, 'rb') as f:
            return tomllib.load(f)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
