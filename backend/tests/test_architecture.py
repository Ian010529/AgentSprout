from __future__ import annotations

import ast
from pathlib import Path

from app.api.errors import ApiError as HttpApiError
from app.api.schemas import ChatRunCreate as HttpChatRunCreate
from app.domain.contracts import ChatRunCreate
from app.domain.errors import ApiError

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _module_name(path: Path) -> str:
    relative = path.relative_to(APP_ROOT.parent).with_suffix("")
    return ".".join(relative.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    return imported


def test_services_do_not_depend_on_http_package() -> None:
    violations = {
        str(path.relative_to(APP_ROOT.parent)): sorted(
            name for name in _imports(path) if name == "app.api" or name.startswith("app.api.")
        )
        for path in (APP_ROOT / "services").glob("*.py")
    }
    assert not {path: imports for path, imports in violations.items() if imports}


def test_api_compatibility_exports_preserve_class_identity() -> None:
    assert HttpApiError is ApiError
    assert HttpChatRunCreate is ChatRunCreate


def test_backend_internal_import_graph_is_acyclic() -> None:
    files = list(APP_ROOT.rglob("*.py"))
    modules = {_module_name(path): path for path in files}
    graph = {
        module: {name for name in _imports(path) if name in modules}
        for module, path in modules.items()
    }
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            start = visiting.index(module)
            raise AssertionError(" -> ".join([*visiting[start:], module]))
        if module in visited:
            return
        visiting.append(module)
        for dependency in graph[module]:
            visit(dependency)
        visiting.pop()
        visited.add(module)

    for module in graph:
        visit(module)
