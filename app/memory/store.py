import os
from pathlib import Path

from app.memory.schemas import MemoryContext
from app.database.connection import SessionLocal
from app.database.models import PatientMemoryModel, SysUserModel

_DATA_ROOT = Path("data/memory/users")

_FILES = {
    "profile": "profile.md",
    "preferences": "preferences.md",
    "care_context": "care_context.md",
}

_DEFAULTS = {
    "profile": "# User Profile\n\n(no profile yet)\n",
    "preferences": "# User Preferences\n\n(no preferences yet)\n",
    "care_context": "# Care Context\n\n(no care context yet)\n",
}


def _user_dir(user_id: str) -> Path:
    d = _DATA_ROOT / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(user_id: str, key: str) -> str:
    with SessionLocal() as db:
        if db.get(SysUserModel, user_id) is not None:
            memory = db.get(PatientMemoryModel, user_id)
            return getattr(memory, key) if memory else _DEFAULTS[key]
    path = _user_dir(user_id) / _FILES[key]
    if not path.exists():
        return _DEFAULTS[key]
    return path.read_text(encoding="utf-8")


def _write(user_id: str, key: str, content: str) -> None:
    with SessionLocal() as db:
        if db.get(SysUserModel, user_id) is not None:
            memory = db.get(PatientMemoryModel, user_id)
            if memory is None:
                memory = PatientMemoryModel(user_id=user_id)
                db.add(memory)
            setattr(memory, key, content)
            memory.version = (memory.version or 0) + 1
            db.commit()
            return
    path = _user_dir(user_id) / _FILES[key]
    path.write_text(content, encoding="utf-8")


def read_all(user_id: str) -> MemoryContext:
    return MemoryContext(
        profile=_read(user_id, "profile"),
        preferences=_read(user_id, "preferences"),
        care_context=_read(user_id, "care_context"),
    )


def append_to(user_id: str, key: str, note: str) -> None:
    existing = _read(user_id, key)
    updated = existing.rstrip() + f"\n- {note}\n"
    _write(user_id, key, updated)
