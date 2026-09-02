#!/usr/bin/env python3
"""Deterministic contract proof for Persistent Host Automation."""

from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.persistent_host_automation_validator import (
    load_cases,
    scan_paths,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/adr/0001-persistent-host-automation.md"
FIXTURES = ROOT / "tests/fixtures/persistent_host_automation_cases.json"
VALIDATOR = ROOT / "tests/persistent_host_automation_validator.py"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PersistentHostAutomationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agents = read_text(ROOT / "AGENTS.md")
        cls.glossary = read_text(ROOT / "GLOSSARY.md")
        cls.contract = read_text(ADR)
        cls.cases = {case["id"]: case["plan"] for case in load_cases(FIXTURES)}

    def test_global_pointer_is_compact_and_routes_each_trigger_branch(self) -> None:
        marker = "- Persistent Host Automation:"
        self.assertEqual(self.agents.count(marker), 1)
        pointer = self.agents.split(marker, 1)[1].split("\n\n", 1)[0]
        pointer = " ".join(f"{marker}{pointer}".split())
        self.assertLessEqual(len(pointer), 280)
        for trigger in (
            "host service",
            "scheduled job",
            "health or recovery automation",
            "`docs/adr/0001-persistent-host-automation.md`",
        ):
            self.assertIn(trigger, pointer)

    def test_glossary_defines_the_boundary_without_becoming_a_spec(self) -> None:
        marker = "**Persistent Host Automation**:"
        self.assertIn(marker, self.glossary)
        entry = self.glossary.split(marker, 1)[1].split("\n\n**", 1)[0]
        for required in (
            "operate beyond the current task",
            "project-local build tooling",
            "one-off diagnostics",
        ):
            self.assertIn(required, entry)
        self.assertNotIn("maintenance", entry.lower())
        self.assertLessEqual(len(entry.strip().splitlines()), 4)

    def test_adr_uses_canonical_status_and_owns_the_portable_contract(self) -> None:
        self.assertTrue(self.contract.startswith("---\nstatus: accepted\n---\n"))
        normalized = " ".join(self.contract.lower().split())
        for required in (
            "issue #31",
            "closer project instructions",
            "user-selected repository",
            "controlled deployed copies",
            "restart only the affected service",
            "live public health seam",
            "canonical and deployed identity",
            "non-secret template references",
            "human gate",
            "issue, branch, implementation, commit, push, pr, merge, release, "
            "installation, deployment, restart, and live verification",
        ):
            self.assertIn(required, normalized)
        for platform_specific in (
            "/Users/",
            "Cavallo",
            "macOS",
            "launchd",
            "systemd",
        ):
            self.assertNotIn(platform_specific, self.contract)
        self.assertNotIn("maintenance", normalized)

    def test_six_representative_plans_pass_the_executable_validator(self) -> None:
        self.assertEqual(
            set(self.cases),
            {
                "privileged-boot-service",
                "user-scheduled-service",
                "service-health-and-recovery",
                "project-local-or-one-off",
                "secret-bearing-service",
                "unrelated-symlink-architecture",
            },
        )
        for case_id, plan in self.cases.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(validate_plan(plan), [])

    def test_validator_rejects_privileged_writable_checkout_symlink(self) -> None:
        plan = copy.deepcopy(self.cases["privileged-boot-service"])
        artifact = plan["artifacts"][0]
        artifact["runtime_model"] = "checkout-symlink"
        artifact["checkout_writable"] = True
        errors = validate_plan(plan)
        self.assertTrue(any("controlled-copy" in error for error in errors))
        self.assertTrue(any("privileged entrypoint" in error for error in errors))

    def test_validator_enforces_closer_precedence_and_human_gate(self) -> None:
        precedence = copy.deepcopy(self.cases["user-scheduled-service"])
        precedence["ownership"]["resolved_repository"] = precedence["ownership"][
            "user_selected_repository"
        ]
        self.assertTrue(
            any("precedence" in error for error in validate_plan(precedence))
        )

        gated = copy.deepcopy(self.cases["user-scheduled-service"])
        gated["external_mutation"]["requested"] = True
        self.assertTrue(any("Human Gate" in error for error in validate_plan(gated)))

    def test_validator_rejects_secret_values_and_missing_template_reference(
        self,
    ) -> None:
        value_plan = copy.deepcopy(self.cases["secret-bearing-service"])
        value_plan["secrets"][0]["secret_value"] = "<redacted>"
        self.assertTrue(
            any("value fields" in error for error in validate_plan(value_plan))
        )

        template_plan = copy.deepcopy(self.cases["secret-bearing-service"])
        del template_plan["secrets"][0]["template_reference"]
        self.assertTrue(
            any("template_reference" in error for error in validate_plan(template_plan))
        )

    def test_validator_requires_service_association_and_complete_state_report(
        self,
    ) -> None:
        recovery = copy.deepcopy(self.cases["service-health-and-recovery"])
        del recovery["artifacts"][0]["associated_service_source"]
        self.assertTrue(
            any("associated service" in error for error in validate_plan(recovery))
        )

        incomplete = copy.deepcopy(self.cases["privileged-boot-service"])
        del incomplete["reported_states"]["merge"]
        self.assertTrue(any("merge" in error for error in validate_plan(incomplete)))

    def test_secret_scanner_covers_fixture_log_issue_and_artifact_surfaces(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assignment = "access_" + "token = " + "A" * 32
            surfaces = {
                "fixture.json",
                "run.log",
                "issue.md",
                "artifact.toml",
            }
            for name in surfaces:
                (root / name).write_text(assignment, encoding="utf-8")
            labels = {
                Path(finding.split(": possible", 1)[0]).name
                for finding in scan_paths([root])
            }
            self.assertEqual(labels, surfaces)

    def test_complete_repository_text_surface_is_secret_clean(self) -> None:
        self.assertEqual(scan_paths([ROOT]), [])

    def test_validator_cli_accepts_fixtures_and_repository_surface(self) -> None:
        for arguments in (
            ["validate-cases", str(FIXTURES)],
            ["scan", str(ROOT)],
        ):
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), *arguments],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            with self.subTest(arguments=arguments):
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
