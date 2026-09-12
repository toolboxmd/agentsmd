"""Exercise public proof APIs against real Git commits and executed subprocesses."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scoped_proof", ROOT / "bin/scoped_proof.py")
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


class ScopedProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Proof Test")
        self.git("config", "user.email", "proof@example.invalid")
        self.policy = {
            "schema": 1, "repository": "test/project", "policyPath": "scope.json",
            "maxAgeSeconds": 3600, "blocked": ["infra/*", "requirements*"],
            "checks": {name: {"argv": [sys.executable, "-c", f"print('{name}')"],
                               "inputs": paths, "environment": ["runtime", "fixture"], "kind": kind}
                       for name, paths, kind in (("sharing", ["sharing/*", "fixtures/*"], "behavior"),
                                                  ("funding", ["funding/*", "fixtures/*"], "behavior"),
                                                  ("package", ["*"], "artifact"))},
            "rules": [
                {"paths": ["sharing/*"], "checks": ["sharing"], "reason": "public sharing and callers"},
                {"paths": ["funding/*"], "checks": ["funding"], "reason": "financial behavior"},
                {"paths": ["fixtures/*"], "checks": ["sharing", "funding"], "reason": "all fixture consumers"},
                {"paths": ["docs/*"], "exclude": "prose has no runtime consumers"},
            ],
        }
        self.write("scope.json", json.dumps(self.policy))
        for name in ("sharing/card", "funding/refund", "fixtures/data"):
            self.write(name, "initial")
        self.baseline = self.commit()
        self.observed = {"runtime": "python-test", "fixture": "fixture-v1"}
        self.trusted = {}
        self.counter = 0
        self.base_raw = self.run_record(self.baseline, self.baseline, "complete")
        self.write("sharing/card", "changed")
        self.candidate = self.commit()
        self.current_raw = self.run_record(self.baseline, self.candidate, "scoped")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "test source")
        return self.git("rev-parse", "HEAD")

    def run_record(self, base, candidate, mode):
        self.counter += 1
        raw = proof.run(self.root, base, candidate, self.policy, mode=mode,
                        observe=lambda name: self.observed,
                        output=Path(self.temp.name) / f"run-{self.counter}", issuer="authorized-test-operator")
        # Test substitute for a protected workflow artifact lookup. This map is
        # populated only from this harness's actual executions, never candidate data.
        self.trusted[raw] = "authorized-test-operator"
        return raw

    def validate(self, **changes):
        arguments = dict(root=self.root, baseline=self.baseline, candidate=self.candidate,
                         policy=self.policy, baseline_raw=self.base_raw, current_raw=self.current_raw,
                         authenticate=lambda raw: self.trusted.get(raw), observe=lambda name: self.observed)
        arguments.update(changes)
        return proof.validate(**arguments)

    def test_real_execution_composes_coverage_and_cli_agrees(self):
        result = self.validate()
        self.assertEqual(result["executed"], ["package", "sharing"])
        self.assertEqual(result["reused"], ["funding"])
        self.assertTrue(result["unverified"])
        cli = subprocess.run([str(ROOT / "bin/scoped-proof"), "select", "--root", str(self.root),
                              "--baseline", self.baseline, "--candidate", self.candidate,
                              "--policy", str(self.root / "scope.json")], capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["execute"], result["executed"])

    def test_distinct_host_records_compose_without_duplicate_execution(self):
        records = []
        for name in ("package", "sharing"):
            raw = proof.run(self.root, self.baseline, self.candidate, self.policy, mode="scoped",
                            observe=lambda _: self.observed, checks=[name],
                            output=Path(self.temp.name) / name, issuer="authorized-test-operator")
            self.trusted[raw] = "authorized-test-operator"
            records.append(raw)
        self.assertEqual(self.validate(current_raw=records)["reused"], ["funding"])
        with self.assertRaisesRegex(proof.ProofError, "duplicate execution coverage"):
            self.validate(current_raw=[*records, records[0]])
        with self.assertRaisesRegex(proof.ProofError, "incomplete"):
            self.validate(current_raw=records[:1])

    def test_complete_candidate_execution_is_reused_across_stages_with_current_bindings(self):
        records = []
        for names in (["funding", "sharing"], ["package"]):
            raw = proof.run(self.root, self.candidate, self.candidate, self.policy, mode="complete",
                            observe=lambda _: self.observed, checks=names,
                            output=Path(self.temp.name) / names[0], issuer="authorized-test-operator")
            self.trusted[raw] = "authorized-test-operator"
            records.append(raw)
        def validate(raw=records, **changes):
            arguments = dict(root=self.root, candidate=self.candidate, policy=self.policy, raw=raw,
                             authenticate=lambda data: self.trusted.get(data), observe=lambda _: self.observed)
            arguments.update(changes)
            return proof.validate_complete(**arguments)
        # Both stages inspect the same genuine records; neither invokes execution.
        first = validate()
        self.assertEqual(validate(), first)
        self.assertEqual(first["coverage"], "complete")
        self.assertEqual(first["executed"], ["funding", "package", "sharing"])
        for raw, reason in ((records[:1], "incomplete"), ([*records, records[0]], "duplicate"),
                            (self.current_raw, "direct complete"), (b'{"passed":true}', "untrusted")):
            with self.subTest(reason=reason), self.assertRaisesRegex(proof.ProofError, reason):
                validate(raw=raw)
        with self.assertRaisesRegex(proof.ProofError, "direct complete"):
            validate(candidate=self.baseline)
        with self.assertRaisesRegex(proof.ProofError, "stale"):
            validate(now=proof.decode(records[0])["finished"] + self.policy["maxAgeSeconds"] + 1)
        self.observed["fixture"] = "changed-artifact-or-input"
        with self.assertRaisesRegex(proof.ProofError, "environment/input invalidation"):
            validate()

    def test_immutable_baseline_age_does_not_force_unrelated_reruns(self):
        record = proof.decode(self.base_raw)
        record.update(started=1, finished=2)
        raw = proof.encode(record)
        self.trusted[raw] = "authorized-test-operator"
        self.assertEqual(self.validate(baseline_raw=raw)["reused"], ["funding"])
        policy = copy.deepcopy(self.policy)
        policy["checks"]["sharing"]["argv"] = ["echo", "same", "same"]
        self.assertTrue(proof.policy_id(policy))

    def test_cumulative_changes_and_shared_fixture_consumers(self):
        self.write("funding/refund", "second commit")
        self.write("fixtures/data", "new fixtures")
        self.write("docs/readme", "wording")
        self.candidate = self.commit()
        plan = proof.select(self.root, self.baseline, self.candidate, self.policy)
        self.assertEqual(plan["execute"], ["funding", "package", "sharing"])
        self.assertEqual(set(plan["changes"]), {"funding/refund", "fixtures/data", "sharing/card", "docs/readme"})
        self.assertIn("exclude", plan["changes"]["docs/readme"])
        with self.assertRaisesRegex(proof.ProofError, "candidate or baseline mismatch"):
            self.validate()

    def test_unknown_blocked_and_candidate_policy_changes_stop_scoping(self):
        for path, value, reason in (("unknown", "?", "unsupported or ambiguous"),
                                    ("infra/service", "new", "protected change"),
                                    ("scope.json", json.dumps(dict(self.policy, blocked=["nothing"])), "policy mutation")):
            with self.subTest(path=path):
                self.git("checkout", "-q", self.candidate)
                self.write(path, value)
                candidate = self.commit()
                with self.assertRaisesRegex(proof.ProofError, reason):
                    proof.select(self.root, self.baseline, candidate, self.policy)

    def test_reused_input_and_environment_invalidation(self):
        for key in ("runtime", "fixture"):
            original = self.observed[key]
            self.observed[key] = "different"
            with self.assertRaisesRegex(proof.ProofError, "environment/input invalidation"):
                self.validate()
            self.observed[key] = original
        self.write("funding/refund", "unmapped consumer input")
        candidate = self.commit()
        plan = proof.select(self.root, self.baseline, candidate, self.policy)
        self.assertNotIn("funding", plan["reuse"])

    def test_altered_and_bare_passed_evidence_is_untrusted(self):
        for raw in (b'{"passed":true}', self.current_raw.replace(b'"exitCode":0', b'"exitCode":1'), b""):
            with self.subTest(raw=raw[:30]):
                with self.assertRaisesRegex(proof.ProofError, "untrusted evidence"):
                    self.validate(current_raw=raw)

    def test_authenticated_but_incomplete_failed_stale_or_mismatched_records_rejected(self):
        # Provenance alone is insufficient: authenticated data must satisfy every binding.
        cases = [
            (lambda r: r["results"].pop("sharing"), "incomplete"),
            (lambda r: r["results"]["sharing"].update(exitCode=1), "failed proof"),
            (lambda r: r["results"]["sharing"].update(inputs="0" * 64), "input mismatch"),
            (lambda r: r.update(policy="0" * 64), "policy or repository mismatch"),
            (lambda r: r.update(started=1, finished=2), "stale"),
            (lambda r: r.update(issuer="other"), "issuer mismatch"),
        ]
        for mutate, reason in cases:
            with self.subTest(reason=reason):
                record = proof.decode(self.current_raw)
                mutate(record)
                raw = proof.encode(record)
                self.trusted[raw] = "authorized-test-operator"
                with self.assertRaisesRegex(proof.ProofError, reason):
                    self.validate(current_raw=raw)

    def test_scoped_baseline_chain_is_rejected(self):
        record = proof.decode(self.base_raw)
        record["mode"] = "scoped"
        raw = proof.encode(record)
        self.trusted[raw] = "authorized-test-operator"
        with self.assertRaisesRegex(proof.ProofError, "direct complete proof"):
            self.validate(baseline_raw=raw)

    def test_execution_failure_dirty_checkout_and_output_collision(self):
        self.git("checkout", "-q", self.baseline)
        policy = copy.deepcopy(self.policy)
        policy["checks"]["sharing"]["argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
        self.write("scope.json", json.dumps(policy))
        candidate = self.commit()
        output = Path(self.temp.name) / "failed"
        raw = proof.run(self.root, candidate, candidate, policy, mode="complete", observe=lambda _: self.observed,
                        output=output, issuer="authorized-test-operator")
        self.assertEqual(proof.decode(raw)["results"]["sharing"]["exitCode"], 7)
        with self.assertRaises(FileExistsError):
            proof.run(self.root, candidate, candidate, policy, mode="complete", observe=lambda _: self.observed,
                      output=output, issuer="authorized-test-operator")
        self.write("sharing/card", "dirty")
        with self.assertRaisesRegex(proof.ProofError, "clean checkout"):
            proof.run(self.root, candidate, candidate, policy, mode="complete", observe=lambda _: self.observed,
                      output=Path(self.temp.name) / "dirty", issuer="authorized-test-operator")

    def test_environment_movement_during_execution_never_records_reusable_proof(self):
        observed = iter([self.observed, dict(self.observed, runtime="moved")])
        output = Path(self.temp.name) / "moving"
        with self.assertRaisesRegex(proof.ProofError, "environment changed"):
            proof.run(self.root, self.baseline, self.candidate, self.policy, mode="scoped",
                      observe=lambda _: next(observed), output=output, issuer="authorized-test-operator")
        self.assertFalse((output / "proof.json").exists())


if __name__ == "__main__":
    unittest.main()
