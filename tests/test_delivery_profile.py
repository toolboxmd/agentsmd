#!/usr/bin/env python3
"""Public schema and loader contract for Delivery System v1 profiles."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "bin/delivery-profile"
SCHEMA = ROOT / "schemas/delivery-v1.schema.json"
FIXTURES = ROOT / "tests/fixtures/delivery_profiles"


class DeliveryProfileTests(unittest.TestCase):
    def run_loader(
        self, profile: Path, *, root: Path = ROOT
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(LOADER),
                "load",
                "--root",
                str(root),
                "--profile",
                str(profile),
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_profile_data(
        self, profile_data: dict[str, object]
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            profile = temp / "delivery.json"
            profile.write_text(json.dumps(profile_data), encoding="utf-8")
            return self.run_loader(profile, root=ROOT)

    def test_schema_is_strict_and_keeps_canonical_truth_out_of_profiles(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            schema["$id"],
            "https://raw.githubusercontent.com/toolboxmd/agentsmd/v8.6.0/schemas/delivery-v1.schema.json",
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {"$schema", "schema"},
        )
        self.assertEqual(
            schema["anyOf"],
            [
                {"required": ["commands"]},
                {"required": ["artifact"]},
                {"required": ["website"]},
            ],
        )
        for duplicate in (
            "version",
            "project",
            "projectRecord",
            "release",
            "documentation",
        ):
            self.assertNotIn(duplicate, schema["properties"])

    def test_valid_fixture_loads_through_public_cli(self) -> None:
        result = self.run_loader(FIXTURES / "valid-minimal.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(
            payload["profileData"]["commands"],
            {"changedScope": ["python3 -m unittest tests.test_delivery_profile -v"]},
        )

    def test_invalid_fixtures_fail_closed_with_structured_errors(self) -> None:
        expected = {
            "invalid-canonical-truth.json": "unknown top-level field: version",
            "invalid-empty.json": (
                "profile must declare at least one Project-specific delta"
            ),
            "invalid-artifact.json": "artifact.output must be a relative dist/ path",
            "invalid-command.json": "command executable not found: missing-delivery-command",
        }
        for name, message in expected.items():
            with self.subTest(name=name):
                result = self.run_loader(FIXTURES / name)
                self.assertEqual(result.returncode, 2)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "invalid")
                self.assertIn(message, payload["errors"])
                self.assertNotIn("profileData", payload)

    def test_repository_profile_loads_and_resolves_real_commands(self) -> None:
        profile = ROOT / ".toolboxmd/delivery.json"
        result = self.run_loader(profile)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["profile"], str(profile.resolve()))
        self.assertEqual(payload["root"], str(ROOT.resolve()))
        self.assertEqual(
            payload["profileData"]["website"],
            {
                "repository": "toolboxmd/toolbox.md",
                "baseUrl": "https://toolbox.md",
                "route": "/agentsmd",
            },
        )

    def test_artifact_build_must_resolve_and_use_only_owned_placeholders(self) -> None:
        result = self.run_loader(FIXTURES / "invalid-artifact.json")
        self.assertEqual(result.returncode, 2)
        errors = json.loads(result.stdout)["errors"]
        self.assertIn(
            "artifact build executable not found: missing-artifact-builder",
            errors,
        )

    def test_loader_matches_schema_structural_constraints(self) -> None:
        schema_id = (
            "https://raw.githubusercontent.com/toolboxmd/agentsmd/"
            "v8.6.0/schemas/delivery-v1.schema.json"
        )
        invalid_profiles = (
            (
                {"$schema": schema_id, "schema": True, "commands": {
                    "changedScope": ["python3 --version"]
                }},
                "schema must be 1",
            ),
            (
                {"$schema": schema_id, "schema": 1, "website": {
                    "repository": "toolboxmd/toolbox.md",
                    "baseUrl": "https://toolbox.md/",
                    "route": "/agentsmd",
                }},
                "website.baseUrl must be an HTTPS origin without a path",
            ),
            (
                {"$schema": schema_id, "schema": 1, "website": {
                    "repository": "toolboxmd/toolbox.md",
                    "baseUrl": "https://toolbox.md",
                    "route": "/bad path",
                }},
                "website.route must use URL-path segments",
            ),
            (
                {"$schema": schema_id, "schema": 1, "artifact": {
                    "build": "git archive --output='dist/bad path-{version}.tgz' {sha}",
                    "output": "dist/bad path-{version}.tgz",
                    "digest": "sha256",
                }},
                "artifact.output must match the portable dist/ path contract",
            ),
        )
        for profile, expected in invalid_profiles:
            with self.subTest(expected=expected):
                result = self.run_profile_data(profile)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn(expected, json.loads(result.stdout)["errors"])

    def test_default_profile_is_discovered_from_a_nested_directory(self) -> None:
        nested = ROOT / "skills/delivery-profile"
        result = subprocess.run(
            [str(LOADER), "load", "--root", str(nested), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["root"], str(ROOT.resolve()))
        self.assertEqual(
            payload["profile"], str((ROOT / ".toolboxmd/delivery.json").resolve())
        )

    def test_duplicate_json_keys_and_missing_profiles_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            profile = temp / "delivery.json"
            profile.write_text('{"schema":1,"schema":1}', encoding="utf-8")
            duplicate = self.run_loader(profile, root=temp)
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("duplicate JSON key: schema", duplicate.stdout)

            missing = subprocess.run(
                [str(LOADER), "load", "--root", str(temp), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn("delivery profile not found", missing.stdout)

    def test_loader_is_packaged_and_executable(self) -> None:
        self.assertTrue(LOADER.is_file())
        self.assertTrue(os.access(LOADER, os.X_OK))


if __name__ == "__main__":
    unittest.main(verbosity=2)
