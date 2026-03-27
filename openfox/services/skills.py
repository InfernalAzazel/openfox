"""Agno LocalSkills package handling: validate layouts, list installs, zip → folder + SKILL.md.

Layout rules match ``agno.skills.validator`` and ``LocalSkills``, aligned with runtime
``Skills(loaders=[LocalSkills(...)])``.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from agno.skills import LocalSkills
from agno.skills.validator import validate_metadata, validate_skill_directory

from openfox.schemas.config import Config
from openfox.schemas.skill import SkillInfo

# Upload size cap (matches reasonable browser / API limits).
MAX_SKILL_ZIP_BYTES = 25 * 1024 * 1024

# Zip entries under these top-level names are ignored (archiver junk).
_JUNK_ROOT_SEGMENTS = frozenset({"__MACOSX", ".DS_Store"})


class SkillPackageError(ValueError):
    """Raised when a skill archive or directory fails validation."""


class SkillNotFoundError(SkillPackageError):
    """Raised when a named skill directory is missing on disk."""


class SkillExistsError(SkillPackageError):
    """Raised when install would overwrite an existing skill folder."""


def resolve_skills_root(config: Config) -> Path:
    """Return the absolute skills directory from config (relative paths use process cwd)."""
    raw = Path(config.skills_path).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (Path.cwd() / raw).resolve()


def _agno_validate_dir(skill_dir: Path) -> None:
    """Run Agno directory checks; raise SkillPackageError with joined messages."""
    errors = validate_skill_directory(skill_dir)
    if errors:
        raise SkillPackageError("; ".join(errors))


def validate_skill_folder_name(name: str) -> str:
    """Normalize and validate folder/skill name (same rules as Agno ``validate_metadata``)."""
    name = name.strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise SkillPackageError(
            "Invalid skill name: empty, hidden, or contains path separators",
        )
    # Minimal metadata so validator can check name vs directory rules.
    errs = validate_metadata({"name": name, "description": "-"}, skill_dir=Path(name))
    if errs:
        raise SkillPackageError("; ".join(errs))
    return name


def _skill_info_from_dir(skill_dir: Path) -> SkillInfo:
    """Build SkillInfo using LocalSkills (same loader path as runtime, no re-validation)."""
    loader = LocalSkills(str(skill_dir.resolve()), validate=False)
    loaded = loader.load()
    if len(loaded) != 1:
        raise SkillPackageError(f"Expected exactly one skill in directory: {skill_dir}")
    s = loaded[0]
    return SkillInfo(
        name=s.name,
        description=(s.description or "").strip(),
        license=s.license,
        path=str(Path(s.source_path).resolve()),
    )


def list_installed_skills(config: Config) -> list[SkillInfo]:
    """Scan skills root for subdirectories with valid SKILL.md; skip invalid entries."""
    root = resolve_skills_root(config)
    if not root.is_dir():
        return []
    out: list[SkillInfo] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        if not (p / "SKILL.md").is_file():
            continue
        errs = validate_skill_directory(p)
        if errs:
            continue
        try:
            out.append(_skill_info_from_dir(p))
        except SkillPackageError:
            continue
    return out


def _normalize_zip_members(namelist: list[str]) -> list[str]:
    """Strip unsafe/junk paths; return forward-slash names without leading slashes."""
    normalized: list[str] = []
    for raw in namelist:
        n = raw.replace("\\", "/").strip("/")
        if not n:
            continue
        if n.startswith("..") or n.startswith("/"):
            raise SkillPackageError("Archive contains an illegal path segment")
        parts = n.split("/")
        if parts[0] in _JUNK_ROOT_SEGMENTS or parts[0] == "":
            continue
        normalized.append(n)
    return normalized


def _zip_top_level_folder(namelist: list[str]) -> str:
    """Require exactly one top-level directory containing ``<name>/SKILL.md``."""
    normalized = _normalize_zip_members(namelist)
    if not normalized:
        raise SkillPackageError(
            "Archive is empty or only contains junk entries (e.g. __MACOSX)",
        )
    roots = {p.split("/")[0] for p in normalized}
    if len(roots) != 1:
        raise SkillPackageError(
            "Archive must contain exactly one top-level skill folder",
        )
    root_folder = roots.pop()
    validate_skill_folder_name(root_folder)
    prefix = root_folder + "/"
    for p in normalized:
        if p != root_folder and not p.startswith(prefix):
            raise SkillPackageError(
                "All archive entries must live under the single top-level folder",
            )
    skill_md_key = f"{root_folder}/SKILL.md"
    if skill_md_key not in normalized:
        raise SkillPackageError(f"Missing required file in archive: {skill_md_key}")
    return root_folder


def _safe_extract_skill_zip(
    zf: zipfile.ZipFile,
    dest: Path,
    root_folder: str,
) -> None:
    """Extract only members under ``root_folder/``; mitigates zip-slip; skips junk roots."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    skill_root = (dest / root_folder).resolve()
    prefix = root_folder + "/"
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise SkillPackageError("Archive contains an illegal path segment")
        n = name.strip("/")
        if not n:
            continue
        parts = n.split("/")
        if parts[0] in _JUNK_ROOT_SEGMENTS:
            continue
        if n == root_folder:
            skill_root.mkdir(parents=True, exist_ok=True)
            continue
        if not n.startswith(prefix):
            continue
        rel = n[len(prefix) :]
        target = (skill_root / rel).resolve()
        if not target.is_relative_to(skill_root):
            raise SkillPackageError("Archive path escapes destination (zip-slip)")
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(target, "wb") as out_f:
                shutil.copyfileobj(src, out_f, length=1024 * 64)


def validate_skill_zip(path: Path) -> tuple[str, Path]:
    """Extract to a temp dir and validate with Agno; returns (folder_name, temp_dir).

    Caller must remove ``temp_dir`` when done (including on failure after return).
    """
    if not path.is_file():
        raise SkillPackageError("ZIP file does not exist")
    if path.stat().st_size > MAX_SKILL_ZIP_BYTES:
        max_mib = MAX_SKILL_ZIP_BYTES // (1024 * 1024)
        raise SkillPackageError(f"ZIP too large (max {max_mib} MiB)")

    tmp = Path(tempfile.mkdtemp(prefix="openfox-skill-"))
    try:
        with zipfile.ZipFile(path, "r") as zf:
            folder = _zip_top_level_folder(zf.namelist())
            _safe_extract_skill_zip(zf, tmp, folder)
        skill_dir = tmp / folder
        _agno_validate_dir(skill_dir)
        return folder, tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def install_skill_from_zip(path: Path, config: Config) -> SkillInfo:
    """Install a new skill from ZIP; fails if the target folder already exists."""
    root = resolve_skills_root(config)
    with zipfile.ZipFile(path, "r") as zf:
        folder = _zip_top_level_folder(zf.namelist())
    if (root / folder).exists():
        raise SkillExistsError(
            f'Skill "{folder}" already exists; delete it or use the replace API — upload does not overwrite',
        )
    folder, tmp = validate_skill_zip(path)
    skill_dir = tmp / folder
    target = root / folder
    try:
        root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(skill_dir), str(target))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _agno_validate_dir(target)
    return _skill_info_from_dir(target)


def replace_skill_from_zip(path: Path, expected_name: str, config: Config) -> SkillInfo:
    """Remove an existing skill directory and install from ZIP.

    The top-level folder name inside the ZIP must equal ``expected_name``.
    """
    validate_skill_folder_name(expected_name)
    root = resolve_skills_root(config)
    target = root / expected_name
    if not target.is_dir():
        raise SkillNotFoundError(f'Skill "{expected_name}" not found; cannot update')
    folder, tmp = validate_skill_zip(path)
    if folder != expected_name:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SkillPackageError(
            f'Update ZIP top-level folder must be "{expected_name}", got "{folder}"',
        )
    skill_dir = tmp / folder
    try:
        shutil.rmtree(target)
        root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(skill_dir), str(target))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _agno_validate_dir(target)
    return _skill_info_from_dir(target)


def delete_skill(name: str, config: Config) -> None:
    """Delete the skill directory named ``name`` under the configured skills root."""
    validate_skill_folder_name(name)
    root = resolve_skills_root(config)
    target = root / name
    if not target.is_dir():
        raise SkillNotFoundError(f'Skill "{name}" not found')
    shutil.rmtree(target)
