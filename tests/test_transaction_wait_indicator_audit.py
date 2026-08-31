from __future__ import annotations

import ast
import inspect
import textwrap

from zonectl.ui.curses_app import CursesApp


class CommitCallAudit(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: list[str] = []
        self.calls: list[ast.Call] = []
        self.unwrapped: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_Call(self, node: ast.Call) -> None:
        is_commit = any(
            keyword.arg == "commit"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
        wrapped = any(
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "_run_with_wait_indicator"
            for call in self.calls
        )
        if is_commit and not wrapped:
            self.unwrapped.append((self.functions[-1], node.lineno))

        self.calls.append(node)
        self.generic_visit(node)
        self.calls.pop()


def test_every_tui_commit_is_wait_wrapped_or_an_internal_dnssec_helper() -> None:
    tree = ast.parse(textwrap.dedent(inspect.getsource(CursesApp)))
    audit = CommitCallAudit()
    audit.visit(tree)

    assert {name for name, _line in audit.unwrapped} == {
        "_dnssec_enable_commit",
        "_dnssec_finalize_commit",
    }


def test_internal_dnssec_commit_helpers_are_invoked_inside_wait_dialogs() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)
    source = "".join(source.split())

    for helper in ("_dnssec_enable_commit", "_dnssec_finalize_commit"):
        helper_at = source.index(f"self.{helper}(zone)")
        wait_at = source.rindex("self._run_with_wait_indicator", 0, helper_at)
        assert wait_at < helper_at
