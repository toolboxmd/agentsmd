"""Tests for the native, no-model routing boundary preflight."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


isolation = load("isolation", ROOT / "isolation.py")
preflight = load("routing_v3_preflight", ROOT / "preflight.py")


def prompt_payload(
    candidate: Path,
    *,
    profile_type: str = "managed",
    writes: tuple[Path, ...] | None = None,
    include_skills: bool = False,
) -> list[dict[str, object]]:
    write_entries = "\n".join(
        f'<entry access="write"><path>{path}</path></entry>'
        for path in (writes or (candidate / ".runner-tmp",))
    )
    context = textwrap.dedent(
        f"""\
        <environment_context>
          <cwd>{candidate}</cwd>
          <shell>zsh</shell>
          <filesystem><workspace_roots><root>{candidate}</root></workspace_roots><permission_profile type="{profile_type}"><file_system type="restricted"><entry access="read"><special>:minimal</special></entry><entry access="deny" escalatable="false"><special>:root</special></entry><entry access="deny" escalatable="false"><special>:slash_tmp</special></entry><entry access="read"><path>{candidate}</path></entry>{write_entries}</file_system></permission_profile></filesystem>
        </environment_context>
        """
    )
    items: list[dict[str, object]] = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": context}],
        }
    ]
    if include_skills:
        items.append(
            {
                "type": "message",
                "role": "developer",
                "content": [
                    {"type": "input_text", "text": "<skills_instructions>leak</skills_instructions>"}
                ],
            }
        )
    return items


class ProbeClassificationTests(unittest.TestCase):
    def test_accepts_only_exact_success_and_kernel_policy_denial(self) -> None:
        success = json.dumps({"category": "success", "operation": "read"}).encode() + b"\n"
        denied = json.dumps(
            {"category": "policy_denied", "operation": "read", "errno": 1}
        ).encode() + b"\n"
        wrong_errno = json.dumps(
            {"category": "policy_denied", "operation": "read", "errno": 2}
        ).encode() + b"\n"
        self.assertEqual(preflight._parse_probe(success, 0)[0], "success")
        self.assertEqual(preflight._parse_probe(denied, 77)[0], "policy_denied")
        self.assertEqual(preflight._parse_probe(wrong_errno, 77)[0], "error")
        self.assertEqual(preflight._parse_probe(success, 1)[0], "error")
        self.assertEqual(preflight._parse_probe(success + success, 0)[0], "error")

    def test_real_probe_does_not_misclassify_missing_file(self) -> None:
        result = preflight.run_probe_command(
            [str(ROOT / "boundary_probe.py"), "read", "/definitely/missing/routing-v3"],
            environment={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            cwd=ROOT,
            timeout_seconds=2,
        )
        self.assertEqual(result.category, "error")


class NativePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.controller = self.root / "controller"
        self.memory = self.root / "memory"
        self.memory.mkdir()
        self.memory_marker = self.memory / "memory-summary.marker"
        self.memory_marker.write_text("real-memory-marker\n", encoding="utf-8")
        self.protected = self.root / "protected"
        self.protected.mkdir()
        self.hidden_verifier = self.protected / "hidden.py"
        self.hidden_verifier.write_text("hidden-verifier\n", encoding="utf-8")
        self.answer_artifact = self.protected / "answer.txt"
        self.answer_artifact.write_text("accepted-answer\n", encoding="utf-8")
        self.paths = isolation.CodexPaths(
            candidate_root=self.candidate,
            home=self.root / "home",
            codex_home=self.root / "codex-home",
            codex_sqlite_home=self.root / "codex-sqlite",
            tmpdir=self.candidate / ".runner-tmp",
            auth_target=self.controller / "auth-target.json",
            controller_root=self.controller,
            memory_root=self.memory,
        )
        self.definition = self.root / "definition.json"
        self.fake_codex = self.root / "codex"
        self.fake_codex.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/python3
                import json, os, sys
                from pathlib import Path

                args = sys.argv[1:]
                if args == ["--version"]:
                    print("codex-cli 0.149.1")
                    raise SystemExit(0)
                if args[:2] == ["debug", "prompt-input"]:
                    candidate = os.getcwd()
                    context = (
                        f'<environment_context>\\n'
                        f'  <cwd>{candidate}</cwd>\\n'
                        f'  <shell>zsh</shell>\\n'
                        f'  <filesystem><workspace_roots><root>{candidate}</root></workspace_roots><permission_profile type="managed"><file_system type="restricted"><entry access="read"><special>:minimal</special></entry><entry access="deny" escalatable="false"><special>:root</special></entry><entry access="deny" escalatable="false"><special>:slash_tmp</special></entry><entry access="read"><path>{candidate}</path></entry><entry access="write"><path>{candidate}/.runner-tmp</path></entry></file_system></permission_profile></filesystem>\\n'
                        f'</environment_context>'
                    )
                    print(json.dumps([
                        {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<permissions instructions>managed</permissions instructions>"}]},
                        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": context}]},
                        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "routing-v3-no-model-preflight"}]},
                    ]))
                    raise SystemExit(0)
                if not args or args[0] != "sandbox" or "--" not in args:
                    raise SystemExit(2)
                tail = args[args.index("--") + 1:]
                probe, operation, operands = tail[0], tail[1], tail[2:]
                if operation == "breakaway":
                    os.execve(probe, [probe, operation], dict(os.environ))
                allowed = False
                if operation in {"read", "write"}:
                    allowed = ".runner-tmp" in Path(operands[0]).parts
                    if Path(operands[0]).name == "controller-escape.marker":
                        allowed = False
                elif operation == "env-absent":
                    allowed = True
                if allowed:
                    payload = {"category": "success", "operation": operation}
                    code = 0
                else:
                    payload = {"category": "policy_denied", "operation": operation, "errno": 1}
                    code = 77
                print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
                raise SystemExit(code)
                """
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(0o755)
        self.definition.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "tasks": {"use-grok": {}, "openbot-acp": {}},
                    "pinned_runtime": {
                        "codex_cli_version": "0.149.1",
                        "codex_native_sha256": preflight.sha256_file(self.fake_codex),
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_command_uses_named_profile_candidate_cwd_and_absolute_probe(self) -> None:
        command = preflight.sandbox_command(
            self.fake_codex, self.paths, ROOT / "boundary_probe.py", ("read", "/x")
        )
        self.assertEqual(command[1:7], [
            "sandbox", "-P", "routing_candidate", "-C", str(self.candidate.resolve()), "--"
        ])
        self.assertTrue(Path(command[7]).is_absolute())
        self.assertEqual(command[-2:], ["read", "/x"])

    def test_full_fake_native_preflight_binds_and_passes(self) -> None:
        bindings = preflight.PreflightBindings(
            package_sha256="a" * 64,
            fixture_sha256={"use-grok": "b" * 64, "openbot-acp": "c" * 64},
        )
        with preflight._TcpServer() as external:
            receipt = preflight.run_native_preflight(
                codex_executable=self.fake_codex,
                probe_executable=ROOT / "boundary_probe.py",
                definition_path=self.definition,
                paths=self.paths,
                bindings=bindings,
                real_memory_marker=self.memory_marker,
                expected_codex_sha256=preflight.sha256_file(self.fake_codex),
                protected_read_paths={
                    "hidden_verifier": self.hidden_verifier,
                    "answer_artifact": self.answer_artifact,
                },
                external_candidates=(external.endpoint,),
            )
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["no_model_calls"])
        self.assertEqual(receipt["package_sha256"], "a" * 64)
        self.assertEqual(receipt["fixture_sha256"]["openbot-acp"], "c" * 64)
        self.assertTrue(all(item["passed"] for item in receipt["operations"].values()))
        for name, path in {
            "hidden_verifier": self.hidden_verifier,
            "answer_artifact": self.answer_artifact,
        }.items():
            operation = receipt["operations"][f"denied_protected_read_{name}"]
            self.assertEqual(operation["positive_control"]["category"], "success")
            self.assertEqual(operation["sandboxed"]["category"], "policy_denied")
            self.assertEqual(receipt["protected_reads"][name]["path"], str(path.resolve()))
            self.assertEqual(
                receipt["protected_reads"][name]["sha256"], preflight.sha256_file(path)
            )
        self.assertEqual(receipt["prompt_input"]["effective_permission_profile_type"], "managed")
        self.assertFalse(receipt["prompt_input"]["named_permission_profile_id_exposed"])
        self.assertEqual(
            receipt["prompt_input"]["workspace_roots"], [str(self.candidate.resolve())]
        )
        self.assertEqual(
            receipt["prompt_input"]["write_roots"],
            [str((self.candidate / ".runner-tmp").resolve())],
        )
        self.assertGreaterEqual(receipt["breakaway"]["detected_count"], 1)
        self.assertEqual(receipt["breakaway"]["remaining_count"], 0)
        self.assertEqual(
            Path(receipt["unix_socket_target"]["path"]).parent.parent,
            preflight.SHORT_SOCKET_PARENT,
        )
        self.assertLess(
            len(os.fsencode(receipt["unix_socket_target"]["path"])), 104
        )
        receipt_without_hash = dict(receipt)
        observed_hash = receipt_without_hash.pop("receipt_sha256")
        self.assertEqual(observed_hash, preflight.receipt_sha256(receipt_without_hash))
        self.assertFalse((self.candidate / ".routing-denied-write.marker").exists())
        self.assertFalse(self.paths.tmpdir.exists())
        config = tomllib.loads((self.paths.codex_home / "config.toml").read_text())
        filesystem = config["permissions"]["routing_candidate"]["filesystem"]
        self.assertEqual(
            filesystem[str(preflight.COMMAND_LINE_TOOLS_ROOT.resolve())], "read"
        )
        self.assertNotIn("/Library", filesystem)
        self.assertNotIn(str(Path.home()), filesystem)

    def test_invalid_hash_binding_fails_before_probe(self) -> None:
        with self.assertRaises(preflight.PreflightError):
            preflight.PreflightBindings("short", {}).normalized()

    def test_prompt_parser_requires_exact_managed_profile_semantics(self) -> None:
        (self.candidate / ".runner-tmp").mkdir()
        evidence = preflight._parse_prompt_input(
            prompt_payload(self.candidate.resolve()), self.candidate
        )
        self.assertTrue(evidence["candidate_cwd_bound"])
        self.assertEqual(evidence["minimal_special_access"], "read")
        self.assertEqual(evidence["root_special_access"], "deny")
        self.assertEqual(evidence["slash_tmp_special_access"], "deny")
        with self.assertRaisesRegex(preflight.PreflightError, "managed permission profile"):
            preflight._parse_prompt_input(
                prompt_payload(self.candidate.resolve(), profile_type="legacy"),
                self.candidate,
            )
        with self.assertRaisesRegex(preflight.PreflightError, "exact sole candidate write root"):
            preflight._parse_prompt_input(
                prompt_payload(
                    self.candidate.resolve(),
                    writes=(
                        self.candidate.resolve() / ".runner-tmp",
                        self.candidate.resolve() / "extra-write",
                    ),
                ),
                self.candidate,
            )
        with self.assertRaisesRegex(preflight.PreflightError, "Skills injection"):
            preflight._parse_prompt_input(
                prompt_payload(self.candidate.resolve(), include_skills=True),
                self.candidate,
            )

    def test_protected_reads_must_be_nonempty_ordinary_distinct_and_outside_candidate(self) -> None:
        with self.assertRaisesRegex(preflight.PreflightError, "nonempty mapping"):
            preflight._protected_read_files({}, self.candidate.resolve())
        inside = self.candidate / "answer.txt"
        inside.write_text("answer\n", encoding="utf-8")
        with self.assertRaisesRegex(preflight.PreflightError, "outside the candidate"):
            preflight._protected_read_files({"inside": inside}, self.candidate.resolve())
        alias = self.protected / "hidden-link.py"
        alias.symlink_to(self.hidden_verifier)
        with self.assertRaisesRegex(preflight.PreflightError, "absolute ordinary file"):
            preflight._protected_read_files({"alias": alias}, self.candidate.resolve())
        with self.assertRaisesRegex(preflight.PreflightError, "distinct files"):
            preflight._protected_read_files(
                {"first": self.hidden_verifier, "second": self.hidden_verifier},
                self.candidate.resolve(),
            )


if __name__ == "__main__":
    unittest.main()
