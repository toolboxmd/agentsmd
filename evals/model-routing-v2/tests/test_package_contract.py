from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackageContractTests(unittest.TestCase):
    def test_python_files_expose_no_paid_model_command(self) -> None:
        paid_executables = {"codex", "grok"}
        for path in ROOT.rglob("*.py"):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                function_name = ""
                if isinstance(call.func, ast.Name):
                    function_name = call.func.id
                elif isinstance(call.func, ast.Attribute):
                    function_name = call.func.attr
                if function_name not in {
                    "run",
                    "Popen",
                    "check_call",
                    "check_output",
                    "run_command",
                } or not call.args:
                    continue
                argument = call.args[0]
                head = None
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    head = argument.value
                elif (
                    isinstance(argument, (ast.List, ast.Tuple))
                    and argument.elts
                    and isinstance(argument.elts[0], ast.Constant)
                    and isinstance(argument.elts[0].value, str)
                ):
                    head = argument.elts[0].value
                if head is not None:
                    with self.subTest(path=path.name, executable=head):
                        self.assertNotIn(Path(head).name.lower(), paid_executables)

    def test_readiness_cli_has_only_no_model_subcommands(self) -> None:
        source = (ROOT / "readiness.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="readiness.py")
        subcommands = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        self.assertEqual(subcommands, {"check", "validate-report"})

    def test_definition_has_no_dynamic_route_claim(self) -> None:
        definition = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
        self.assertEqual(
            definition["routes"]["adaptive"]["meaning"],
            "fixed_predeclared_assignment_not_dynamic_routing",
        )
        self.assertFalse(definition["execution_surface"]["model_runner_in_this_package"])

    def test_model_stage_timeout_contract_is_exact_and_does_not_enable_repair(self) -> None:
        definition = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
        lifecycle = definition["lifecycle"]
        self.assertEqual(
            lifecycle["model_stage_timeout"],
            {
                "maximum_seconds": 600,
                "applies_to": [
                    "implementation",
                    "initial_review",
                    "repair",
                    "rereview",
                ],
                "clock": "trusted_controller_monotonic",
                "terminal_duration_field": "actual_terminal_duration_seconds",
                "terminal_duration_required_for_every_terminal_outcome": True,
                "reaching_maximum_is_timeout": True,
                "timeout_action": "STOP_CELL",
                "timeout_triggers_automatic_retry": False,
                "timeout_triggers_replacement_run": False,
            },
        )
        self.assertNotIn("implementation_timeout_seconds", lifecycle)
        self.assertNotIn("review_timeout_seconds", lifecycle)
        self.assertFalse(lifecycle["automatic_retry"])
        self.assertFalse(lifecycle["automatic_repair"])
        self.assertEqual(definition["reviewer"]["repair_calls"], 0)
        self.assertEqual(definition["reviewer"]["rereview_calls"], 0)

    def test_quota_guard_has_one_user_owned_numeric_gate(self) -> None:
        definition = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
        quota = definition["quota_guard"]
        self.assertEqual(
            set(quota),
            {"max_used_basis_points", "required_windows", "source"},
        )
        self.assertIsNone(quota["max_used_basis_points"])
        self.assertEqual(quota["source"], "user_authorized_exact_ceiling_required")

    def test_remaining_cells_require_an_independent_exact_canary_audit(self) -> None:
        definition = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
        self.assertEqual(
            definition["lifecycle"]["remaining_cells_require"],
            {
                "decision": "ACCEPT",
                "audit_kind": "independent",
                "auditor_must_differ_from": [
                    "candidate",
                    "implementation_controller",
                    "boundary_issuer",
                ],
                "exact_canary_evidence_bound": True,
            },
        )

    def test_task_paths_match_definition(self) -> None:
        definition = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
        for task in definition["tasks"].values():
            for field in ("known_good_patch", "task_packet", "public_verifier", "hidden_verifier"):
                with self.subTest(task=task["workspace_name"], field=field):
                    self.assertTrue((ROOT / task[field]).is_file())


if __name__ == "__main__":
    unittest.main()
