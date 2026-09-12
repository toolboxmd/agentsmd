"""Portable scoped proof. Import only from a trusted, pinned AgentsMD release."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Callable


class ProofError(ValueError):
    """Scoped delivery is unsupported or its evidence is invalid."""


def require(condition, message):
    if not condition:
        raise ProofError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate key: {key}")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as error:
        raise ProofError(f"invalid JSON: {error}") from error


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    require(result.returncode == 0, f"Git failed: {' '.join(args)}")
    return result.stdout


def exact_commit(root, sha):
    require(isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", sha),
            "source identity must be a full commit SHA")
    require(git(root, "rev-parse", f"{sha}^{{commit}}").decode().strip() == sha,
            "source identity is not an exact commit")


def strings(values, label, *, unique=True):
    require(isinstance(values, list) and bool(values) and
            all(isinstance(v, str) and v.strip() and "\x00" not in v for v in values),
            f"{label} must be nonempty strings")
    require(not unique or len(set(values)) == len(values), f"duplicate {label}")


def patterns(values, label):
    strings(values, label)
    require(all(not p.startswith("/") and ".." not in p.split("/") for p in values),
            f"{label} must use repository-relative patterns")


def policy_id(policy):
    require(isinstance(policy, dict) and set(policy) == {
        "schema", "repository", "policyPath", "blocked", "checks", "rules", "maxAgeSeconds"
    }, "invalid policy fields")
    require(type(policy["schema"]) is int and policy["schema"] == 1, "unsupported policy schema")
    require(isinstance(policy["repository"], str) and policy["repository"], "missing repository")
    patterns([policy["policyPath"]], "policyPath")
    patterns(policy["blocked"], "blocked")
    require(type(policy["maxAgeSeconds"]) is int and policy["maxAgeSeconds"] > 0, "invalid proof lifetime")
    checks = policy["checks"]
    require(isinstance(checks, dict) and checks, "missing checks")
    for name, check in checks.items():
        require(re.fullmatch(r"[a-zA-Z0-9_-]+", name), "invalid check name")
        require(isinstance(check, dict) and set(check) == {"argv", "inputs", "environment", "kind"},
                f"invalid check: {name}")
        strings(check["argv"], f"{name} argv", unique=False)
        patterns(check["inputs"], f"{name} inputs")
        strings(check["environment"], f"{name} environment")
        require(check["kind"] in ("behavior", "artifact"), "invalid check kind")
    require(any(c["kind"] == "behavior" for c in checks.values()), "missing behavioral coverage")
    require(any(c["kind"] == "artifact" for c in checks.values()), "missing artifact coverage")
    require(isinstance(policy["rules"], list) and policy["rules"], "missing scope rules")
    for rule in policy["rules"]:
        require(isinstance(rule, dict) and set(rule) in ({"paths", "checks", "reason"}, {"paths", "exclude"}),
                "invalid scope rule")
        patterns(rule["paths"], "rule paths")
        if "checks" in rule:
            strings(rule["checks"], "rule checks")
            require(set(rule["checks"]) <= set(checks), "rule names unknown checks")
            require(isinstance(rule["reason"], str) and rule["reason"].strip(), "missing affected behavior explanation")
        else:
            require(isinstance(rule["exclude"], str) and rule["exclude"].strip(), "missing exclusion explanation")
    return digest(encode(policy))


def matches(path, globs):
    # Deliberately simple, documented fnmatch semantics; '*' includes '/'.
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in globs)


def source_inputs(root, sha, globs):
    entries = git(root, "ls-tree", "-rz", "--full-tree", sha).split(b"\x00")
    selected = []
    for entry in entries:
        if entry:
            meta, path = entry.split(b"\t", 1)
            name = path.decode("utf-8", errors="strict")
            if matches(name, globs):
                require(meta.split()[1] == b"blob", f"unsupported non-blob input: {name}")
                selected.append(entry.decode())
    require(selected, "check inputs match no tracked files")
    return digest(encode(sorted(selected)))


def select(root, baseline, candidate, policy):
    """Select all cumulative affected checks using policy supplied by trusted control."""
    identity = policy_id(policy)
    exact_commit(root, baseline)
    exact_commit(root, candidate)
    git(root, "merge-base", "--is-ancestor", baseline, candidate)
    for sha in (baseline, candidate):
        require(decode(git(root, "show", f"{sha}:{policy['policyPath']}")) == policy,
                "policy mutation: separately approve policy and establish a complete baseline")
    # No rename heuristic: deletion and addition are each classified.
    changed = sorted(p.decode("utf-8") for p in git(
        root, "diff", "--no-renames", "--name-only", "-z", baseline, candidate, "--"
    ).split(b"\x00") if p)
    classifications, affected = {}, set()
    for path in changed:
        require(path != policy["policyPath"] and not matches(path, policy["blocked"]),
                f"unsupported protected change: {path}")
        rules = [r for r in policy["rules"] if matches(path, r["paths"])]
        require(len(rules) == 1, f"unsupported or ambiguous scope: {path}")
        rule = rules[0]
        affected.update(rule.get("checks", []))
        classifications[path] = {k: v for k, v in rule.items() if k != "paths"}
    baseline_inputs, candidate_inputs = {}, {}
    for name, check in policy["checks"].items():
        baseline_inputs[name] = source_inputs(root, baseline, check["inputs"])
        candidate_inputs[name] = source_inputs(root, candidate, check["inputs"])
        if baseline_inputs[name] != candidate_inputs[name] or check["kind"] == "artifact":
            affected.add(name)
    return {"schema": 1, "repository": policy["repository"], "policy": identity,
            "baseline": baseline, "candidate": candidate, "changes": classifications,
            "execute": sorted(affected), "reuse": sorted(set(policy["checks"]) - affected),
            "baselineInputs": baseline_inputs, "candidateInputs": candidate_inputs}


def environment_for(check, observed):
    require(isinstance(observed, dict), "environment observation must be an object")
    result = {}
    for key in check["environment"]:
        require(key in observed and isinstance(observed[key], str) and observed[key],
                f"missing environment/input observation: {key}")
        result[key] = observed[key]
    return result


def clean_candidate(root, candidate):
    require(git(root, "rev-parse", "HEAD").decode().strip() == candidate, "checkout candidate mismatch")
    require(not git(root, "status", "--porcelain", "--untracked-files=all"), "proof requires a clean checkout")


def run(root, baseline, candidate, policy, *, mode, observe: Callable, output, issuer, checks=None):
    """Execute selected commands. A trusted operator/workflow must transport the result.

    observe(check_name) measures current relevant environment and external input
    identities. It is called before and after execution; credentials are never values.
    """
    require(mode in ("complete", "scoped"), "invalid execution mode")
    require(isinstance(issuer, str) and issuer, "missing issuer label")
    require(mode != "complete" or baseline == candidate, "complete proof must anchor itself")
    plan = select(root, baseline, candidate, policy)
    clean_candidate(root, candidate)
    output = Path(output).resolve()
    require(not output.is_relative_to(Path(root).resolve()), "outputs must be outside the source checkout")
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    allowed = sorted(policy["checks"]) if mode == "complete" else plan["execute"]
    names = allowed if checks is None else checks
    strings(names, "selected checks")
    require(set(names) <= set(allowed), "execution requests checks outside the selected lane")
    results = {}
    for name in names:
        check = policy["checks"][name]
        before = environment_for(check, observe(name))
        check_output = output / name
        check_output.mkdir()
        env = dict(os.environ, SCOPED_PROOF_OUTPUT=str(check_output))
        with (check_output / "stdout").open("wb") as stdout, (check_output / "stderr").open("wb") as stderr:
            process = subprocess.run(check["argv"], cwd=root, env=env, stdout=stdout, stderr=stderr)
        after = environment_for(check, observe(name))
        require(before == after, f"environment changed during execution: {name}")
        clean_candidate(root, candidate)
        results[name] = {"argv": check["argv"], "inputs": plan["candidateInputs"][name],
                         "environment": before, "exitCode": process.returncode,
                         "stdout": digest((check_output / "stdout").read_bytes()),
                         "stderr": digest((check_output / "stderr").read_bytes())}
        if process.returncode:
            break
    record = {"schema": 1, "repository": policy["repository"], "policy": plan["policy"],
              "baseline": baseline, "candidate": candidate, "mode": mode, "issuer": issuer,
              "started": started, "finished": time.time(), "results": results}
    raw = encode(record)
    (output / "proof.json").write_bytes(raw)
    return raw


def authenticated(raw, authenticate, policy, now, *, expire):
    # Authentication is supplied by protected adapter code, never by the record.
    issuer = authenticate(raw)
    require(isinstance(issuer, str) and issuer, "untrusted evidence")
    record = decode(raw)
    require(isinstance(record, dict) and set(record) == {
        "schema", "repository", "policy", "baseline", "candidate", "mode", "issuer", "started", "finished", "results"
    }, "invalid proof record fields")
    require(type(record["schema"]) is int and record["schema"] == 1, "unsupported record schema")
    require(record["issuer"] == issuer, "authenticated issuer mismatch")
    require(record["repository"] == policy["repository"] and record["policy"] == policy_id(policy),
            "proof policy or repository mismatch")
    start, end = record["started"], record["finished"]
    require(type(start) in (int, float) and type(end) in (int, float) and
            0 < start <= end <= now and (not expire or now - start <= policy["maxAgeSeconds"]),
            "stale or invalid proof time")
    require(isinstance(record["results"], dict), "missing execution results")
    return record


def _records(raws, *, mode, baseline, candidate, policy, authenticate, now, expire):
    raws = raws if isinstance(raws, list) else [raws]
    require(bool(raws), "missing proof records")
    combined = {}
    for raw in raws:
        record = authenticated(raw, authenticate, policy, now, expire=expire)
        require(record["mode"] == mode and record["baseline"] == baseline and
                record["candidate"] == candidate,
                "baseline must have direct complete proof" if mode == "complete" else
                "current proof candidate or baseline mismatch")
        require(not (set(combined) & set(record["results"])), "duplicate execution coverage")
        combined.update(record["results"])
    return combined


def _validate_results(results, names, identities, policy, observe, observe_names):
    for name in names:
        result = results[name]
        check = policy["checks"][name]
        require(isinstance(result, dict) and set(result) == {
            "argv", "inputs", "environment", "exitCode", "stdout", "stderr"
        }, f"invalid execution result: {name}")
        require(type(result["exitCode"]) is int and result["exitCode"] == 0, f"failed proof: {name}")
        require(result["argv"] == check["argv"] and result["inputs"] == identities[name],
                f"command or source input mismatch: {name}")
        require(environment_for(check, result["environment"]) == result["environment"],
                f"invalid recorded environment: {name}")
        require(all(isinstance(result[k], str) and re.fullmatch(r"[a-f0-9]{64}", result[k])
                    for k in ("stdout", "stderr")), f"missing execution output identity: {name}")
        if name in observe_names:
            require(result["environment"] == environment_for(check, observe(name)),
                    f"environment/input invalidation: {name}")


def validate(root, baseline, candidate, policy, baseline_raw, current_raw, *, authenticate: Callable,
             observe: Callable, now=None):
    """Validate composed coverage, not permission to promote or fresh external state.

    authenticate(exact_bytes) must independently verify authorized execution provenance
    and return its issuer, or reject. Never implement it by reading a record's issuer
    or digest allowlist supplied by the candidate. observe(name) measures current inputs.
    """
    now = time.time() if now is None else now
    plan = select(root, baseline, candidate, policy)
    base = _records(baseline_raw, mode="complete", baseline=baseline, candidate=baseline,
                    policy=policy, authenticate=authenticate, now=now, expire=False)
    current = _records(current_raw, mode="scoped", baseline=baseline, candidate=candidate,
                       policy=policy, authenticate=authenticate, now=now, expire=True)
    require(set(base) == set(policy["checks"]), "incomplete baseline proof")
    require(set(current) == set(plan["execute"]), "incomplete or unexpected current proof")
    _validate_results(base, sorted(policy["checks"]), plan["baselineInputs"], policy, observe, plan["reuse"])
    _validate_results(current, plan["execute"], plan["candidateInputs"], policy, observe, plan["execute"])
    return {"status": "valid", "candidate": candidate, "baseline": baseline,
            "policy": plan["policy"], "executed": plan["execute"], "reused": plan["reuse"],
            "unverified": ["external-state authorization and freshness", "artifact promotion", "behavioral Live Verification"],
            "changes": plan["changes"]}


def validate_complete(root, candidate, policy, raw, *, authenticate: Callable, observe: Callable, now=None):
    """Reuse direct complete execution on this exact candidate, without running tests.

    Records may partition hosts. All current input/environment assumptions, including
    the artifact digest, must still hold. External-state admission remains separate.
    """
    now = time.time() if now is None else now
    plan = select(root, candidate, candidate, policy)
    results = _records(raw, mode="complete", baseline=candidate, candidate=candidate,
                       policy=policy, authenticate=authenticate, now=now, expire=True)
    names = sorted(policy["checks"])
    require(set(results) == set(names), "incomplete or unexpected complete proof")
    _validate_results(results, names, plan["candidateInputs"], policy, observe, names)
    return {"status": "valid", "candidate": candidate, "policy": plan["policy"],
            "coverage": "complete", "executed": names, "reused": [],
            "unverified": ["external-state authorization and freshness", "artifact promotion", "behavioral Live Verification"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("select",))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--policy", type=Path, required=True,
                        help="policy selected independently by trusted control")
    args = parser.parse_args()
    try:
        print(json.dumps(select(args.root, args.baseline, args.candidate,
                                decode(args.policy.read_bytes())), indent=2))
        return 0
    except (ProofError, OSError, UnicodeError) as error:
        print(json.dumps({"status": "invalid", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
