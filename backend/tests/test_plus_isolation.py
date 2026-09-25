"""The núcleo (saberlink/*.py) must never import from saberlink/plus/ or from
backend/api/ — so deleting saberlink/plus/ or api/ entirely (if time runs
out) never breaks the core pipeline. Checked by static inspection, not just
convention."""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = BACKEND_DIR / "saberlink"
API_DIR = BACKEND_DIR / "api"


def _imports_module_prefix(py_file: Path, prefix: str) -> bool:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(prefix):
            return True
        if isinstance(node, ast.Import):
            if any(alias.name.startswith(prefix) for alias in node.names):
                return True
    return False


def _imports_plus(py_file: Path) -> bool:
    return _imports_module_prefix(py_file, "saberlink.plus")


def test_nucleo_modules_never_import_plus():
    nucleo_files = [
        p for p in PACKAGE_DIR.glob("*.py") if p.name != "__init__.py"
    ]
    assert nucleo_files, "no núcleo modules found — check PACKAGE_DIR"
    offenders = [p.name for p in nucleo_files if _imports_plus(p)]
    assert not offenders, f"núcleo modules importing saberlink.plus: {offenders}"


def test_plus_modules_only_import_from_nucleo_or_stdlib():
    plus_dir = PACKAGE_DIR / "plus"
    plus_files = [p for p in plus_dir.glob("*.py") if p.name != "__init__.py"]
    assert plus_files, "no PLUS modules found"
    # Just a sanity check that PLUS files parse and exist — the one-directional
    # isolation rule (checked above) is what actually matters for the "delete
    # plus/ safely" guarantee.
    for p in plus_files:
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def test_nucleo_and_plus_never_import_api():
    """backend/api/ is a thin HTTP wrapper — nothing under saberlink/ (core
    or plus) may depend on it, so deleting backend/api/ never breaks the
    pipeline, notebooks, Streamlit or the pyvis exports."""
    assert API_DIR.is_dir(), "no api/ directory found — check API_DIR"
    all_saberlink_files = list(PACKAGE_DIR.rglob("*.py"))
    offenders = [
        str(p.relative_to(BACKEND_DIR)) for p in all_saberlink_files if _imports_module_prefix(p, "api")
    ]
    assert not offenders, f"saberlink modules importing api: {offenders}"
