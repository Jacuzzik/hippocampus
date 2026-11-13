"""Files a visitor to the repository expects, and the pre-commit hook that CONTRIBUTING.md names."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_pre_commit_hook_runs_the_format_lint_and_token_checks() -> None:
    hook = ROOT / ".githooks" / "pre-commit"
    text = hook.read_text(encoding="utf-8")
    assert "ruff format --check" in text
    assert "ruff check" in text
    assert "check-tokens.mjs" in text
    if sys.platform != "win32":
        assert os.access(hook, os.X_OK), "the hook must be executable"
    assert "core.hooksPath .githooks" in (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")


def test_the_root_has_the_documents_an_open_source_project_carries() -> None:
    for name in [
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "ARCHITECTURE.md",
        "LICENSE",
        "RELEASE-CHECKLIST.md",
        "design/DESIGN.md",
    ]:
        assert (ROOT / name).is_file(), f"{name} is missing"


def test_the_readme_explains_the_fixed_dev_port() -> None:
    assert "Port 1420 is already in use" in (ROOT / "README.md").read_text(encoding="utf-8")
