#!/usr/bin/env python3
"""Behavioral contracts for the AgentsMD-owned workflow Skills."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def scalar(value: str) -> str | bool | int:
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdigit():
        return int(value)
    return value.strip('"')


def frontmatter_fields(relative: str) -> dict[str, str | bool | int]:
    metadata = read_text(relative).split("---\n", 2)[1]
    fields = {}
    for line in metadata.splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if value.strip():
            fields[key] = scalar(value.strip())
    return fields


def frontmatter_metadata(relative: str) -> dict[str, str | bool | int]:
    metadata = read_text(relative).split("---\n", 2)[1]
    fields = {}
    in_metadata = False
    for line in metadata.splitlines():
        if line == "metadata:":
            in_metadata = True
            continue
        if in_metadata and not line.startswith("  "):
            break
        if in_metadata and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            fields[key] = scalar(value.strip())
    return fields


def nested_yaml_value(
    relative: str, section: str, key: str
) -> str | bool | int:
    in_section = False
    for line in read_text(relative).splitlines():
        if line == f"{section}:":
            in_section = True
            continue
        if in_section and not line.startswith("  "):
            break
        if in_section and line.startswith(f"  {key}:"):
            return scalar(line.split(":", 1)[1].strip())
    raise KeyError(f"{relative}: {section}.{key}")


def workspace_isolation_decision(case: dict[str, object]) -> str:
    if case["work_kind"] == "read-only":
        if case.get("can_mutate") or case.get("interferes_with_writer"):
            return "stop-affected-work"
        return "share-read-only"

    if not case.get("selected_ownership_known"):
        return "stop-affected-writer"
    if case.get("base_moved") or case.get("unsafe_overlap"):
        return "stop-affected-writer"
    if not case.get("fresh_workspace") or not case.get("exclusive_branch"):
        return "stop-affected-writer"

    record = case.get("start_record")
    required = {
        "intended-base",
        "branch",
        "workspace-path",
        "ownership",
        "starting-head",
    }
    if not isinstance(record, dict) or set(record) != required:
        return "stop-affected-writer"
    if any(not isinstance(value, str) or not value for value in record.values()):
        return "stop-affected-writer"

    existing_state = case.get("existing_state")
    if existing_state in {"dirty", "active", "ambiguous"} and (
        case.get("reuse_existing") or not case.get("preserved_and_reported")
    ):
        return "stop-affected-writer"

    if case.get("parallel"):
        if (
            case.get("independence") != "known-independent"
            or not case.get("separate_workspaces")
        ):
            return "stop-affected-writer"

    claims = case.get("ownership_claims")
    if not isinstance(claims, list) or not claims:
        return "stop-affected-writer"
    resources = ("branch", "workspace", "file-set")
    owners_by_resource = {resource: {} for resource in resources}
    selected_claim_found = False
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {
            "owner",
            *resources,
        }:
            return "stop-affected-writer"
        if any(not isinstance(value, str) or not value for value in claim.values()):
            return "stop-affected-writer"
        selected_claim_found |= (
            claim["owner"] == record["ownership"]
            and claim["branch"] == record["branch"]
            and claim["workspace"] == record["workspace-path"]
        )
        for resource in resources:
            owners = owners_by_resource[resource]
            existing_owner = owners.get(claim[resource])
            if existing_owner is not None and existing_owner != claim["owner"]:
                return "stop-affected-writer"
            owners[claim[resource]] = claim["owner"]
    if not selected_claim_found:
        return "stop-affected-writer"
    return "continue-exclusive"


def review_ready_stack_decision(case: dict[str, object]) -> str:
    if case["work-kind"] == "independent":
        if case.get("native-blocked") or case.get("stack-review-blocks-work"):
            return "stop-invalid-independent-block"
        return "continue-independent"

    predecessor = case.get("predecessor")
    if not isinstance(predecessor, dict):
        return "remain-native-blocked"
    head = predecessor.get("exact-head")
    pull_request = predecessor.get("pull-request")
    if (
        not case.get("native-blocked")
        or not predecessor.get("review-ready")
        or predecessor.get("proof-state") != "passed"
        or not isinstance(pull_request, str)
        or not pull_request
        or not isinstance(head, str)
        or re.fullmatch(r"[0-9a-f]{40}", head) is None
    ):
        if case.get("blocker-cleared"):
            return "stop-premature-blocker-clear"
        return "remain-native-blocked"

    record = case.get("transition-record")
    if not isinstance(record, dict) or set(record) != {
        "predecessor-pr",
        "exact-head",
        "proof-state",
        "dependency-state",
    }:
        if case.get("blocker-cleared"):
            return "stop-premature-blocker-clear"
        return "remain-native-blocked"
    if record != {
        "predecessor-pr": pull_request,
        "exact-head": head,
        "proof-state": "passed",
        "dependency-state": "native-blocked",
    }:
        if case.get("blocker-cleared"):
            return "stop-premature-blocker-clear"
        return "remain-native-blocked"
    if not case.get("blocker-cleared"):
        return "remain-native-blocked"

    ancestry = case.get("ancestry")
    expected_mode = (
        "native-stack"
        if case.get("native-stacking-available")
        else "fallback-branch"
    )
    if (
        not isinstance(ancestry, dict)
        or ancestry.get("mode") != expected_mode
        or ancestry.get("base") != head
        or not ancestry.get("verified")
    ):
        return "stop-invalid-ancestry"

    review_fix = case.get("review-fix")
    if review_fix is not None and (
        not isinstance(review_fix, dict)
        or review_fix.get("applied-layer")
        != review_fix.get("earliest-owning-layer")
    ):
        return "stop-wrong-fix-layer"

    cascade = case.get("lower-layer-change")
    if cascade is not None:
        if not isinstance(cascade, dict):
            return "stop-stale-dependent"
        affected = cascade.get("affected-dependents")
        if (
            not isinstance(affected, list)
            or cascade.get("rebased") != affected
            or cascade.get("revalidated") != affected
        ):
            return "stop-stale-dependent"

    merge = case.get("merge")
    if merge is not None:
        if not isinstance(merge, dict):
            return "stop-stale-upper-layer"
        if merge.get("actual-order") != merge.get("dependency-order"):
            return "stop-out-of-order-merge"
        if merge.get("events") != [
            "merge-layer-1",
            "automatic-retarget-layer-2",
            "verify-retarget-layer-2",
            "mark-layer-2-current",
            "merge-layer-2",
        ]:
            return "stop-stale-upper-layer"
        if (
            not merge.get("retarget-verified")
            or merge.get("upper-current-base") != merge.get("merged-head")
        ):
            return "stop-stale-upper-layer"

    recovery = case.get("recovery")
    if recovery is not None:
        required = {
            "issue",
            "branch",
            "pull-request",
            "layers",
            "exact-heads",
            "exact-bases",
            "proof-state",
            "delivery-states",
            "blockers",
            "next-action",
        }
        if (
            not isinstance(recovery, dict)
            or recovery.get("context") not in {"interruption", "fresh-context"}
            or recovery.get("recorded-on") != ["issue", "pull-request"]
            or set(recovery.get("exact-stack-state", {})) != required
            or any(
                value in (None, "")
                for value in recovery.get("exact-stack-state", {}).values()
            )
        ):
            return "stop-incomplete-recovery"

    return "continue-stacked"


TERMINAL_DISPOSITIONS = {
    "merged",
    "approved-alternative-delivery",
    "cancelled",
    "duplicated",
    "superseded",
    "equivalent-conclusive-closure",
}

TRANSIENT_RESOURCE_TYPES = {
    "local-branch",
    "remote-branch",
    "worktree",
    "disposable-checkout",
    "temporary-file",
    "task-process",
    "container",
    "image",
    "socket",
    "port",
    "lock",
    "pid",
    "disposable-credential",
    "test-account",
    "preview",
}


def terminal_finalization_decision(case: dict[str, object]) -> str:
    if (
        not case.get("review-complete")
        or not case.get("disposition-verified")
        or case.get("disposition") not in TERMINAL_DISPOSITIONS
    ):
        return "do-not-finalize"
    return "begin-finalization"


def resource_finalization_decision(case: dict[str, object]) -> str:
    if not case.get("finalization-started"):
        return "do-not-touch"
    if not case.get("ownership-known") or case.get("ambiguous"):
        handoff = case.get("reconciliation-handoff")
        required = {"path", "branch", "head", "files", "reason", "next-action"}
        if not isinstance(handoff, dict) or set(handoff) != required:
            return "stop-incomplete-reconciliation-handoff"
        if any(value in (None, "") for value in handoff.values()):
            return "stop-incomplete-reconciliation-handoff"
        if (
            not isinstance(handoff["files"], list)
            or not handoff["files"]
            or re.fullmatch(r"[0-9a-f]{40}", handoff["head"]) is None
        ):
            return "stop-incomplete-reconciliation-handoff"
        return "reconcile"

    preserve_when_true = {
        "dirty",
        "active",
        "unique",
        "shared",
        "persistent",
        "production",
        "materially-changed",
        "protected",
        "gated",
        "user-owned",
        "needed-by-remaining-layer",
    }
    if any(case.get(field) for field in preserve_when_true):
        return "preserve"
    if (
        not case.get("clean")
        or not case.get("exact-task-owned")
        or not case.get("transient")
        or case.get("resource-type") not in TRANSIENT_RESOURCE_TYPES
        or case.get("teardown-authority")
        not in {"explicit", "creation-of-explicitly-disposable"}
    ):
        return "preserve"
    return "remove"


def issue_closure_decision(case: dict[str, object]) -> str:
    kind = case.get("kind")
    if kind == "complete":
        return (
            "close-native-link"
            if case.get("fully-resolves") and case.get("native-closing-link")
            else "keep-open-reference"
        )
    if kind == "partial":
        return (
            "keep-open-reference"
            if case.get("durable-reference")
            else "stop-missing-reference"
        )
    if kind == "parent":
        return (
            "close-parent"
            if case.get("criteria-satisfied")
            and case.get("required-children-terminal")
            else "keep-open-parent"
        )
    if kind in {"proof", "experiment"}:
        return (
            f"close-{kind}"
            if case.get("evidence-or-decision-recorded")
            else f"keep-open-{kind}"
        )
    if kind in {"duplicate", "superseded"}:
        return (
            f"close-{kind}-link"
            if case.get("durable-link")
            else f"keep-open-{kind}"
        )
    if kind == "deferred":
        return "keep-open-deferred"
    return "keep-open-unknown"


def finalization_report(case: dict[str, object]) -> str:
    if not case.get("outcome-closed"):
        return "outcome-open"
    if "reconcile" in case.get("resource-actions", []):
        return "closed-not-fully-finalized"
    return "closed-finalized"


RECONCILIATION_MANIFEST_FIELDS = {
    "id",
    "exact-identity",
    "evidence",
    "classification",
    "proposed-action",
    "reversibility",
    "reason",
    "next-action",
}

RECONCILIATION_PRESERVE_FLAGS = {
    "unknown",
    "dirty",
    "active",
    "shared",
    "persistent",
    "unique",
    "user-owned",
    "ambiguous",
    "protected",
    "materially-changed",
}


def repository_reconciliation_decision(case: dict[str, object]) -> str:
    if not case.get("orientation-drift-detected"):
        return "no-op-no-drift"

    manifest = case.get("manifest")
    if (
        not isinstance(manifest, dict)
        or set(manifest) != RECONCILIATION_MANIFEST_FIELDS
        or any(value in (None, "") for value in manifest.values())
    ):
        return "stop-incomplete-manifest"

    flags = set(case.get("state-flags", []))
    if flags & RECONCILIATION_PRESERVE_FLAGS:
        return "preserve"

    classification = manifest["classification"]
    if classification == "preserve":
        return "preserve"
    if classification == "no-op/already-resolved":
        return "no-op-already-resolved"
    if classification == "blocked/needs-next-action":
        return "blocked-needs-next-action"
    if classification != "proposed-cleanup/change":
        return "stop-invalid-classification"

    approved_ids = case.get("approved-ids", [])
    if manifest["id"] not in approved_ids:
        return (
            "stop-unapproved-action"
            if case.get("mutation-attempted")
            else "await-batch-approval"
        )

    sequence = case.get("sequence", [])
    if sequence != [
        "inspect",
        "propose",
        "approve",
        "recheck",
        "mutate",
        "verify",
    ]:
        return "stop-invalid-sequence"

    recheck = case.get("immediate-recheck")
    if (
        not isinstance(recheck, dict)
        or recheck.get("exact-identity") != manifest["exact-identity"]
        or not recheck.get("issue-current")
        or not recheck.get("pull-request-current")
        or not recheck.get("resource-current")
    ):
        return "preserve-material-change"

    after = case.get("after-verification")
    if (
        not isinstance(after, dict)
        or after.get("target") != manifest["exact-identity"]
        or after.get("observed-state") != after.get("expected-state")
    ):
        return "stop-unverified-after-state"
    return "reconciled"


class SkillContractTests(unittest.TestCase):
    def test_project_direction_skill_owns_all_repair_and_review_triggers(self) -> None:
        skill = read_text("skills/project-direction/SKILL.md")
        metadata = skill.split("---\n", 2)[1]
        normalized_metadata = " ".join(metadata.split())
        for required in (
            "missing",
            "blank",
            "unreadable",
            "oversized",
            "unresolved placeholders",
            "contradict",
            "stale",
            "achieved",
            "invalidated",
            "abandoned",
            "reprioritized",
            "define, review, or update",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized_metadata)
        self.assertNotIn("disable-model-invocation", metadata)
        self.assertIn("Do not invoke merely to reread", normalized_metadata)

    def test_project_direction_skill_preserves_user_owned_strategy(self) -> None:
        skill = read_text("skills/project-direction/SKILL.md")
        normalized = " ".join(skill.split())
        for required in (
            "coherent unit",
            "unsupported strategic claims unknown",
            "Ask only for unresolved strategic decisions",
            "explicit user confirmation before writing",
            "Do not require repeated confirmation",
            "modify only the files whose meaning changed",
            "reread all three files in full",
            "deliberate detour",
            "advance the current Objective",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)

    def test_objective_is_milestone_level_across_public_contract(self) -> None:
        for relative in (
            "AGENTS.md",
            "GLOSSARY.md",
            "README.md",
            "skills/project-direction/SKILL.md",
            "skills/project-direction/references/file-contracts.md",
        ):
            normalized = " ".join(read_text(relative).split())
            with self.subTest(relative=relative):
                self.assertIn("milestone-level", normalized)
                self.assertIn("narrower than the Mission", normalized)
                self.assertIn(
                    "broader than an individual request, task, Issue, commit, or PR",
                    normalized,
                )

        template = " ".join(
            read_text("skills/project-direction/templates/OBJECTIVE.md").split()
        )
        self.assertIn("milestone-level outcome", template)
        self.assertIn("not one task's delivery state", template)

    def test_project_direction_evals_cover_task_to_objective_regression(self) -> None:
        payload = json.loads(
            read_text("skills/project-direction/evals/evals.json")
        )
        cases = " ".join(
            f"{case['prompt']} {case['expected_output']}"
            for case in payload["evals"]
        )
        for required in (
            "active task as evidence",
            "broader milestone",
            "several contributing Issues",
            "task-level Objective",
            "genuinely off-Objective",
        ):
            with self.subTest(required=required):
                self.assertIn(required, cases)

    def test_vision_and_mission_have_distinct_directional_roles(self) -> None:
        for relative in (
            "AGENTS.md",
            "GLOSSARY.md",
            "README.md",
            "skills/project-direction/SKILL.md",
            "skills/project-direction/references/file-contracts.md",
        ):
            normalized = " ".join(read_text(relative).split())
            with self.subTest(relative=relative):
                self.assertIn("grand and visionary", normalized)
                self.assertIn("strategic", normalized)
                self.assertIn("grounded in what the project does now", normalized)

        vision_template = " ".join(
            read_text("skills/project-direction/templates/VISION.md").split()
        )
        mission_template = " ".join(
            read_text("skills/project-direction/templates/MISSION.md").split()
        )
        self.assertIn("grand and visionary future", vision_template)
        self.assertIn("strategic present purpose", mission_template)
        self.assertIn("grounded in what the project does now", mission_template)

    def test_project_direction_evals_cover_vision_and_mission_quality(
        self,
    ) -> None:
        payload = json.loads(
            read_text("skills/project-direction/evals/evals.json")
        )
        cases = " ".join(
            f"{case['prompt']} {case['expected_output']}"
            for case in payload["evals"]
        )
        self.assertIn("tactical Vision", cases)
        self.assertIn("ungrounded Mission", cases)

    def test_global_contract_requires_complete_current_project_direction(self) -> None:
        agents = read_text("AGENTS.md")
        normalized = " ".join(agents.split())
        for required in (
            "Project Direction",
            "`VISION.md`, `MISSION.md`, and `OBJECTIVE.md`",
            "at every task start, resume, clear, handoff, post-compaction continuation, and subagent start",
            "locate and read all three files in full before any other work",
            "Only the repository and tracker inspection required by that Skill may proceed",
            "reported as oversized",
            "Treat the current request as the immediate instruction",
            "Surface material drift before proceeding",
            "Every proposed Spec and Issue must state how its outcome advances the current Objective",
            "Other Skills follow their own trigger and approval contracts",
            "own current Project Direction",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)

    def test_project_direction_currentness_contract_is_consistent(self) -> None:
        agents = " ".join(read_text("AGENTS.md").split())
        skill = " ".join(read_text("skills/project-direction/SKILL.md").split())
        loader = read_text("bin/project-direction")

        for contract in (agents, skill):
            with self.subTest(contract=contract[:20]):
                for required in (
                    "after the complete local triad is loaded",
                    "intended base",
                    "`HEAD`",
                    "configured upstream",
                    "ahead/behind",
                    "`potentially_stale`",
                    "reread all three",
                ):
                    self.assertIn(required, contract)
        for required in (
            '"status": "potentially_stale"',
            '"branch"',
            '"head"',
            '"upstream"',
            '"divergence"',
            '"project_direction_diff"',
        ):
            with self.subTest(loader_contract=required):
                self.assertIn(required, loader)

    def test_root_direction_files_are_present_and_bounded(self) -> None:
        expected_headings = {
            "VISION.md": "# Vision\n",
            "MISSION.md": "# Mission\n",
            "OBJECTIVE.md": "# Objective\n",
        }
        total = 0
        for relative, heading in expected_headings.items():
            payload = (ROOT / relative).read_bytes()
            total += len(payload)
            self.assertTrue(payload.decode("utf-8").startswith(heading), relative)
            self.assertLessEqual(len(payload), 8192, relative)
        self.assertLessEqual(total, 16384)

    def test_global_contract_uses_new_glossary_names(self) -> None:
        agents = read_text("AGENTS.md")
        self.assertIn("`GLOSSARY.md`", agents)
        self.assertIn("`GLOSSARY-MAP.md`", agents)
        self.assertIn("read-only", agents)
        self.assertNotIn("create a root `CONTEXT.md`", agents)
        self.assertNotIn("update the appropriate `CONTEXT.md`", agents)
        self.assertNotIn("ASD-STE100-style", agents)
        self.assertIn("AgentsMD workflow Skills", agents)

    def test_global_contract_defines_independent_partnership(self) -> None:
        agents = read_text("AGENTS.md")
        for required in (
            "Align on ends. Think independently about means.",
            "Optimize for mission and valuable outcome",
            "Form and state an independent view",
            "Dissent when it can materially change",
            "Use initiative within authority",
            "lead with it",
        ):
            self.assertIn(required, agents)

    def test_global_contract_routes_material_algorithm_work(self) -> None:
        agents = read_text("AGENTS.md")
        normalized = " ".join(agents.split())
        for required in (
            "After Project Direction is loaded",
            "invoke the model-invoked `algorithm` Skill",
            "material requirement",
            "solution design",
            "process design",
            "recurring-loop automation",
            "small direct microfix",
            "stays direct",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)
        self.assertNotIn("Question every requirement.", agents)
        self.assertNotIn("Run the Algorithm inside a closed evidence loop.", agents)

    def test_algorithm_skill_preserves_order_and_completion_contract(self) -> None:
        skill = read_text("skills/algorithm/SKILL.md")
        normalized = " ".join(skill.split())
        stages = (
            "Question every requirement.",
            "Delete the unnecessary part or process.",
            "Simplify or optimize only what survives deletion.",
            "Accelerate cycle time through the active constraint.",
            "Automate last.",
        )
        positions = [normalized.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions))
        evidence_gate = normalized.index("Before step 4")
        self.assertLess(positions[2], evidence_gate)
        self.assertLess(evidence_gate, positions[3])
        for required in (
            "The fixed order is binding",
            "all five steps again for every material requirement, solution, process, and recurring loop",
            "It prevents perfect execution of the wrong requirement",
            "Requirements from experts and inherited process need scrutiny",
            "question the proposed interpretation and path",
            "Complete this step when outcome, ownership, constraints, "
            "acceptance, and proof are explicit.",
            "Test whether the requirement, scope, code, test, dependency, "
            "artifact, handoff, or ceremony should exist at all.",
            "Deletion is stronger than cleanup",
            "Make deletion risk-scaled and reversible.",
            "Use committed Git history to recover in-scope tracked work.",
            "Keep uncommitted user work, user data, credentials, legal controls",
            "Required proof and unique regression tests survive",
            "Restore work only when evidence proves it is required.",
            "Complete this step when every survivor has an evidence-linked "
            "reason to exist.",
            "Addback maps the boundary; it is not a quota.",
            "Prefer fewer states, narrower interfaces, direct paths, clear ownership",
            "Simplicity must preserve necessary behavior, error handling, proof, safety",
            "It is a design result, not a reason to hide complexity that still exists.",
            "Complete this step when the surviving path is the simplest one "
            "known to meet the requirement.",
            "Speed means faster validated learning after the right work and structure",
            "Use direct source inspection, smaller checks, fewer handoffs, cached work",
            "Keep proof and single-writer boundaries intact.",
            "Complete this step when the next unit of effort follows the "
            "shortest safe feedback path through the current constraint.",
            "Automation magnifies the process chosen before it.",
            "Automate only a necessary, stable, proven, recurring semantic loop",
            "Keep one-off or ambiguous work explicit until evidence makes it repeatable.",
            "Complete this step when automation preserves the proven semantics "
            "and exposes failures.",
            "return to the earliest affected step",
            "Resolve every earlier step before optimizing, accelerating, or automating.",
            "Run the Algorithm inside a closed evidence loop.",
            "Start from the useful outcome and inspect the exact source, work, state, or user surface.",
            "Identify the active constraint.",
            "Make the smallest meaningful reversible change or experiment",
            "the fastest check that can falsify the current assumption",
            "inspect the result, correct the model and implementation, expose bad news, and repeat",
            "Scale failure tolerance to consequence",
            "feedback, not final Proof",
            "highest practical Proof seam",
            "exact delivery state must remain explicit",
            "Human Gates",
            "Project Direction",
            "user-owned dirty work",
            "explicit user constraints",
            "current material-work artifact or evidence",
            "questioned requirement and its supporting evidence",
            "Keep a small direct microfix direct",
            "Do not narrate the Algorithm as ceremony.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)

    def test_algorithm_is_model_invoked_with_material_branches(self) -> None:
        skill = read_text("skills/algorithm/SKILL.md")
        metadata = skill.split("---\n", 2)[1]
        normalized_metadata = " ".join(metadata.split())
        self.assertNotIn("disable-model-invocation", metadata)
        for required in (
            "material requirements",
            "solution design",
            "process design",
            "recurring-loop automation",
            "small direct microfixes direct",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized_metadata)

        host_metadata = read_text("skills/algorithm/agents/openai.yaml")
        self.assertIn("allow_implicit_invocation: true", host_metadata)

    def test_algorithm_trigger_fixture_covers_positive_and_negative_branches(
        self,
    ) -> None:
        payload = json.loads(
            read_text("skills/algorithm/evals/trigger-evals.json")
        )
        self.assertEqual(payload["skill_name"], "algorithm")
        cases = payload["queries"]
        branches = {
            case["branch"]: case["should_trigger"] for case in cases
        }
        self.assertEqual(
            branches,
            {
                "material-requirement": True,
                "solution-design": True,
                "process-design": True,
                "recurring-loop-automation": True,
                "direct-microfix": False,
                "read-only-status": False,
            },
        )

    def test_algorithm_records_real_marketplace_regression(self) -> None:
        evidence = " ".join(
            read_text(
                "skills/algorithm/references/marketplace-project-record-regression.md"
            ).split()
        )
        for required in (
            "toolboxmd/agentsmd#32",
            "toolboxmd/marketplace#6",
            "comprehensive schema",
            "accepted-record snapshot",
            "provenance lock",
            "three-release design",
            "separate snapshot",
            "separate lock",
            "registry state",
            "duplicated release and manifest facts",
            "automatic reconciliation",
            "minimal neutral index over existing released sources",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)

    def test_domain_modeling_owns_lazy_glossary_behavior(self) -> None:
        skill = read_text("skills/domain-modeling/SKILL.md")
        for required in (
            "`GLOSSARY.md`",
            "`GLOSSARY-MAP.md`",
            "read-only fallback",
            "Create files lazily",
            "|-- GLOSSARY.md",
            "|-- GLOSSARY-MAP.md",
            "system-wide decisions",
            "domain-specific decisions",
        ):
            self.assertIn(required, skill)
        self.assertNotIn("[CONTEXT-FORMAT.md]", skill)
        self.assertFalse((ROOT / "skills/domain-modeling/CONTEXT-FORMAT.md").exists())

    def test_grill_with_docs_does_not_precreate_documents(self) -> None:
        skill = read_text("skills/grill-with-docs/SKILL.md")
        self.assertIn("grilling", skill)
        self.assertIn("domain-modeling", skill)
        self.assertIn("lazily", skill)
        self.assertNotIn("setup-matt-pocock-skills", skill)

    def test_to_spec_publishes_a_ready_github_parent_issue(self) -> None:
        skill = read_text("skills/to-spec/SKILL.md")
        normalized = " ".join(skill.split())
        for required in (
            "GitHub parent Issue",
            "current state of the codebase",
            "Prefer an existing testing seam",
            "highest public seam",
            "ideally one",
            "Confirm the proposed seam",
            "## Outcome",
            "## Acceptance criteria",
            "## Non-goals",
            "## Blockers",
            "## Required proof",
            "technical clarifications",
            "schema or API contracts",
            "external behavior",
        ):
            self.assertIn(required, normalized)
        for forbidden in (
            "setup-matt-pocock-skills",
            "ready-for-agent",
            "local file",
            "configured tracker",
        ):
            self.assertNotIn(forbidden, skill)

    def test_specify_workflow_metadata_matches_state_contract(self) -> None:
        contract = json.loads(
            read_text("tests/fixtures/specify_workflow_cases.json")
        )["contract"]
        spec = frontmatter_metadata("skills/to-spec/SKILL.md")
        tickets = frontmatter_metadata("skills/to-tickets/SKILL.md")

        self.assertEqual(spec["workflow"], contract["workflow"])
        self.assertEqual(
            spec["default-completion"], contract["default_completion"]
        )
        self.assertEqual(
            spec["parent-publication-approval"],
            contract["parent_publication_approval"],
        )
        self.assertEqual(spec["next-skill"], "to-tickets")
        self.assertEqual(spec["invocation"], contract["entry_invocation"])
        self.assertEqual(
            spec["parent-only-opt-out"], contract["parent_only_opt_out"]
        )
        self.assertEqual(
            spec["implementation-authority-source"],
            contract["implementation_authority_source"],
        )
        self.assertEqual(tickets["workflow"], contract["workflow"])
        self.assertEqual(
            tickets["default-completion"], contract["default_completion"]
        )
        self.assertEqual(
            tickets["ticket-publication-approval"],
            contract["ticket_publication_approval"],
        )
        self.assertEqual(tickets["invocation"], contract["entry_invocation"])
        self.assertEqual(
            tickets["implementation-target"], contract["implementation_target"]
        )
        self.assertEqual(
            tickets["implementation-context"],
            contract["implementation_context"],
        )
        self.assertEqual(
            tickets["implementation-authority-source"],
            contract["implementation_authority_source"],
        )
        self.assertEqual(
            tickets["missing-authority-prompt-limit"],
            contract["missing_authority_prompt_limit"],
        )

        spec_fields = frontmatter_fields("skills/to-spec/SKILL.md")
        tickets_fields = frontmatter_fields("skills/to-tickets/SKILL.md")
        self.assertEqual(spec_fields["name"], contract["entry_skill"])
        self.assertNotIn("disable-model-invocation", spec_fields)
        self.assertNotIn("disable-model-invocation", tickets_fields)
        self.assertTrue(
            nested_yaml_value(
                "skills/to-spec/agents/openai.yaml",
                "policy",
                "allow_implicit_invocation",
            )
        )
        self.assertTrue(
            nested_yaml_value(
                "skills/to-tickets/agents/openai.yaml",
                "policy",
                "allow_implicit_invocation",
            )
        )

    def test_specify_workflow_state_fixture_covers_every_decision_branch(
        self,
    ) -> None:
        payload = json.loads(
            read_text("tests/fixtures/specify_workflow_cases.json")
        )
        self.assertEqual(payload["schema"], 1)
        contract = payload["contract"]
        cases = {case["branch"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "planning-only",
                "pre-authorized-implementation",
                "explicit-parent-only",
                "revised-drafts",
                "rejected-parent-draft",
                "rejected-ticket-draft",
            },
        )

        for branch, case in cases.items():
            transitions = case["transitions"]
            with self.subTest(branch=branch):
                self.assertEqual(transitions[0], "draft-parent")
                if branch == "rejected-parent-draft":
                    self.assertNotIn("publish-and-verify-parent", transitions)
                    continue
                self.assertLess(
                    transitions.index("approve-parent"),
                    transitions.index("publish-and-verify-parent"),
                )
                if case["parent_only"]:
                    self.assertNotIn("draft-tickets", transitions)
                else:
                    self.assertLess(
                        transitions.index("publish-and-verify-parent"),
                        transitions.index("draft-tickets"),
                    )
                    if branch == "rejected-ticket-draft":
                        self.assertNotIn(
                            "publish-and-verify-tickets", transitions
                        )
                        continue
                    self.assertLess(
                        transitions.index("approve-ticket-graph"),
                        transitions.index("publish-and-verify-tickets"),
                    )

        planning = cases["planning-only"]
        self.assertEqual(
            planning["implementation_authority_prompts"],
            contract["missing_authority_prompt_limit"],
        )
        self.assertTrue(planning["names_first_unblocked_issue"])
        self.assertFalse(planning["starts_implementation"])

        authorized = cases["pre-authorized-implementation"]
        self.assertTrue(authorized["implementation_authorized"])
        self.assertEqual(authorized["implementation_authority_prompts"], 0)
        self.assertTrue(authorized["starts_implementation"])
        self.assertTrue(authorized["starts_in_fresh_context"])
        for case in cases.values():
            if not case["starts_implementation"]:
                self.assertFalse(case["starts_in_fresh_context"])

        parent_only = cases["explicit-parent-only"]
        self.assertEqual(parent_only["terminal_state"], "parent-only-complete")
        self.assertEqual(parent_only["implementation_authority_prompts"], 0)

        revised = cases["revised-drafts"]["transitions"]
        for transition in (
            "revise-parent-draft",
            "revise-ticket-draft",
        ):
            self.assertIn(transition, revised)

        rejected_parent = cases["rejected-parent-draft"]
        self.assertEqual(
            rejected_parent["terminal_state"], "parent-draft-rejected"
        )
        self.assertEqual(rejected_parent["implementation_authority_prompts"], 0)

        rejected_tickets = cases["rejected-ticket-draft"]
        self.assertEqual(
            rejected_tickets["terminal_state"], "ticket-draft-rejected"
        )
        self.assertEqual(rejected_tickets["implementation_authority_prompts"], 0)

    def test_to_tickets_publishes_github_issues_and_native_edges(self) -> None:
        skill = read_text("skills/to-tickets/SKILL.md")
        for required in (
            "GitHub Issues",
            "native sub-Issue",
            "native blocking",
            "fresh context",
            "## Non-goals",
            "## Required proof",
            "user approves",
        ):
            self.assertIn(required, skill)
        for forbidden in (
            "setup-matt-pocock-skills",
            "ready-for-agent",
            "Local files",
            ".scratch/",
            "configured tracker",
        ):
            self.assertNotIn(forbidden, skill)

    def test_repository_capability_setup_is_inspected_and_authorized_once(
        self,
    ) -> None:
        agents = read_text("AGENTS.md")
        contract = " ".join(
            agents.split("## Authority and continuation", 1)[1]
            .split("\n## ", 1)[0]
            .split()
        )

        for required in (
            "inspect the exact repository read-only before relying on its delivery capabilities",
            "default branch",
            "applicable requirements",
            "native Issue dependencies and dependent work",
            "branch creation and push",
            "closing linkage",
            "authorized ready-PR merge path",
            "local and remote branch retirement",
            "Verify each capability from current evidence",
            "one complete setup bundle",
            "exact current state",
            "proposed settings",
            "expected effect, risks, and rollback path",
            "one scoped user approval",
            "without another prompt",
            "Reuse that authority while the exact settings and risk remain unchanged",
            "settings, target, or risk changes materially",
            "unsupported",
            "zero-mutation bundle",
            "no approval",
            "no repository setting changed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

        states = (
            "inspection",
            "proposed setup",
            "approval",
            "settings mutation",
            "verification",
        )
        positions = [contract.index(state) for state in states]
        self.assertEqual(positions, sorted(positions))

    def test_mutating_issues_own_exclusive_workspaces(self) -> None:
        agents = read_text("AGENTS.md")
        contract = " ".join(
            agents.split("## Authority and continuation", 1)[1]
            .split("\n## ", 1)[0]
            .split()
        )

        for required in (
            "Before tracked mutation, give each implementation Issue one fresh "
            "exclusive branch and workspace",
            "intended base, branch, workspace path, ownership, and exact "
            "starting `HEAD`",
            "canonical checkout as the stable coordination and integration view",
            "Read-only work may share repository state only when it cannot mutate "
            "or interfere with a writer",
            "separate workspaces with disjoint ownership",
            "A branch, workspace, and file set each has one writer",
            "Preserve and report dirty, active, or ambiguous state",
            "unknown ownership or independence",
            "moving base or unsafe overlap stops only the affected writer",
            "unrelated independent work continues",
            "fresh-context and durable-handoff rules in this section",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

    def test_review_ready_pull_request_stacks_preserve_dependency_truth(
        self,
    ) -> None:
        agents = read_text("AGENTS.md")
        glossary = " ".join(read_text("GLOSSARY.md").split())
        contract = " ".join(
            agents.split("## Authority and continuation", 1)[1]
            .split("\n## ", 1)[0]
            .split()
        )

        for required in (
            "Keep a dependent Issue natively blocked until its predecessor "
            "publishes a complete review-ready pull request at an exact SHA",
            "predecessor pull request, exact head, proof state, and dependency "
            "state before clearing only that native blocker",
            "native stacked pull request from that exact predecessor",
            "ordinary dependent branch with equivalent exact-base, review, "
            "rebase, revalidation, retarget, and dependency-ordered merge "
            "invariants",
            "Independent work remains free",
            "earliest layer that owns the broken acceptance criterion",
            "Cascade rebase and revalidation through every affected dependent "
            "layer",
            "verify automatic rebase or retarget before treating an upper layer "
            "as current",
            "exact stack state across interruption, fresh context, and durable "
            "handoff",
            "review-ready, blocker-cleared, stacked, rebased, revalidated, "
            "retargeted, and merged as separate states",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

        self.assertIn("**Review-ready pull request stack**:", glossary)
        self.assertIn(
            "A dependency-ordered set of pull request layers whose exact heads, "
            "bases, proof, review, revalidation, retarget, and merge states are "
            "recorded independently",
            glossary,
        )

    def test_review_ready_stack_cases_cover_every_delivery_branch(self) -> None:
        payload = json.loads(
            read_text("tests/fixtures/review_ready_stack_cases.json")
        )
        cases = {
            case["id"]: {**payload["case-defaults"], **case}
            for case in payload["cases"]
        }

        self.assertEqual(payload["schema"], 1)
        self.assertEqual(
            set(cases),
            {
                "incomplete-predecessor",
                "native-transition",
                "native-stack",
                "fallback-ancestry",
                "independent",
                "lower-layer-fix-cascade",
                "dependency-order-merge-retarget",
                "interruption-recovery",
                "fresh-context-recovery",
            },
        )
        self.assertEqual(
            payload["contract"]["separate-reporting-states"],
            [
                "issue",
                "branch",
                "pull-request",
                "stacked",
                "review",
                "review-ready",
                "blocker-cleared",
                "rebased",
                "revalidated",
                "retargeted",
                "merged",
                "behavioral-live-verification",
            ],
        )

        for case in cases.values():
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    review_ready_stack_decision(case),
                    case["expected-decision"],
                )

        native = cases["native-stack"]
        fallback = cases["fallback-ancestry"]
        self.assertEqual(native["ancestry"]["mode"], "native-stack")
        self.assertEqual(fallback["ancestry"]["mode"], "fallback-branch")
        self.assertEqual(
            native["ancestry"]["base"], native["predecessor"]["exact-head"]
        )
        self.assertEqual(
            fallback["ancestry"]["base"],
            fallback["predecessor"]["exact-head"],
        )

        mismatched_record = dict(cases["native-transition"])
        mismatched_record["transition-record"] = dict(
            mismatched_record["transition-record"],
            **{"exact-head": "f" * 40},
        )
        self.assertEqual(
            review_ready_stack_decision(mismatched_record),
            "stop-premature-blocker-clear",
        )

        premature_clear = dict(cases["incomplete-predecessor"])
        premature_clear["blocker-cleared"] = True
        self.assertEqual(
            review_ready_stack_decision(premature_clear),
            "stop-premature-blocker-clear",
        )

        missing_predecessor_pr = dict(cases["native-transition"])
        missing_predecessor_pr["predecessor"] = dict(
            missing_predecessor_pr["predecessor"], **{"pull-request": ""}
        )
        missing_predecessor_pr["transition-record"] = dict(
            missing_predecessor_pr["transition-record"],
            **{"predecessor-pr": ""},
        )
        self.assertEqual(
            review_ready_stack_decision(missing_predecessor_pr),
            "stop-premature-blocker-clear",
        )

        missing_native_before_state = dict(cases["native-transition"])
        missing_native_before_state["native-blocked"] = False
        self.assertEqual(
            review_ready_stack_decision(missing_native_before_state),
            "stop-premature-blocker-clear",
        )

        unverified_ancestry = dict(cases["fallback-ancestry"])
        unverified_ancestry["ancestry"] = dict(
            unverified_ancestry["ancestry"], verified=False
        )
        self.assertEqual(
            review_ready_stack_decision(unverified_ancestry),
            "stop-invalid-ancestry",
        )

        fallback_despite_native_support = dict(cases["fallback-ancestry"])
        fallback_despite_native_support["native-stacking-available"] = True
        self.assertEqual(
            review_ready_stack_decision(fallback_despite_native_support),
            "stop-invalid-ancestry",
        )

        wrong_fix_layer = dict(cases["lower-layer-fix-cascade"])
        wrong_fix_layer["review-fix"] = dict(
            wrong_fix_layer["review-fix"], **{"applied-layer": "layer-2"}
        )
        self.assertEqual(
            review_ready_stack_decision(wrong_fix_layer),
            "stop-wrong-fix-layer",
        )

        missing_revalidation = dict(cases["lower-layer-fix-cascade"])
        missing_revalidation["lower-layer-change"] = dict(
            missing_revalidation["lower-layer-change"], revalidated=[]
        )
        self.assertEqual(
            review_ready_stack_decision(missing_revalidation),
            "stop-stale-dependent",
        )

        wrong_merge_order = dict(cases["dependency-order-merge-retarget"])
        wrong_merge_order["merge"] = dict(
            wrong_merge_order["merge"],
            **{"actual-order": ["layer-2", "layer-1"]},
        )
        self.assertEqual(
            review_ready_stack_decision(wrong_merge_order),
            "stop-out-of-order-merge",
        )

        unverified_retarget = dict(cases["dependency-order-merge-retarget"])
        unverified_retarget["merge"] = dict(
            unverified_retarget["merge"], **{"retarget-verified": False}
        )
        self.assertEqual(
            review_ready_stack_decision(unverified_retarget),
            "stop-stale-upper-layer",
        )

        self.assertEqual(
            cases["dependency-order-merge-retarget"]["merge"]["events"],
            [
                "merge-layer-1",
                "automatic-retarget-layer-2",
                "verify-retarget-layer-2",
                "mark-layer-2-current",
                "merge-layer-2",
            ],
        )

        premature_upper_merge = dict(
            cases["dependency-order-merge-retarget"]
        )
        premature_upper_merge["merge"] = dict(
            premature_upper_merge["merge"],
            events=[
                "merge-layer-1",
                "merge-layer-2",
                "automatic-retarget-layer-2",
                "verify-retarget-layer-2",
                "mark-layer-2-current",
            ],
        )
        self.assertEqual(
            review_ready_stack_decision(premature_upper_merge),
            "stop-stale-upper-layer",
        )

        for case_id in ("interruption-recovery", "fresh-context-recovery"):
            with self.subTest(durable_recovery=case_id):
                self.assertEqual(
                    cases[case_id]["recovery"]["recorded-on"],
                    ["issue", "pull-request"],
                )

        incomplete_recovery = dict(cases["fresh-context-recovery"])
        incomplete_recovery["recovery"] = {
            **incomplete_recovery["recovery"],
            "exact-stack-state": {
                key: value
                for key, value in incomplete_recovery["recovery"][
                    "exact-stack-state"
                ].items()
                if key != "next-action"
            },
        }
        self.assertEqual(
            review_ready_stack_decision(incomplete_recovery),
            "stop-incomplete-recovery",
        )

    def test_delivery_finalization_contract_is_concise_and_host_neutral(
        self,
    ) -> None:
        agents = " ".join(read_text("AGENTS.md").split())
        glossary = " ".join(read_text("GLOSSARY.md").split())

        for required in (
            "Delivery Finalization starts only after review and a verified "
            "terminal disposition",
            "An open pull request or review-ready candidate is not terminal",
            "Remove only clean, exact, task-owned transient resources that no "
            "remaining stack layer needs",
            "Authority to create an explicitly disposable resource includes its "
            "teardown",
            "Age or cleanliness alone never proves ownership or removal "
            "eligibility",
            "Preserve Issues, pull requests, commits, tags, releases, proof",
            "persistent, shared, production, materially changed, protected, gated, "
            "dirty, active, unique, user-owned, or ambiguous resources",
            "until applicable authority exists",
            "Repository Reconciliation with its exact path, branch, `HEAD`, files, "
            "reason, and next action",
            "closed but not fully finalized",
            "native closing linkage only for a pull request that fully resolves "
            "the Issue, and use references for partial work",
            "Close parents only after their acceptance criteria are satisfied and "
            "required children are terminal",
            "Close proof or experiment Issues after recording their evidence or "
            "decision",
            "Close duplicate or superseded Issues with a durable link",
            "keep deferred work open, and never delete Issues",
            "outcome, review, merge, closure, cleanup, finalization, and behavioral "
            "Live Verification separately",
        ):
            with self.subTest(required=required):
                self.assertIn(required, agents)

        self.assertIn("**Delivery Finalization**:", glossary)
        self.assertIn(
            "The post-review lifecycle step for a verified terminal outcome",
            glossary,
        )

    def test_repository_reconciliation_contract_is_bounded_and_approval_gated(
        self,
    ) -> None:
        agents = " ".join(read_text("AGENTS.md").split())
        glossary = " ".join(read_text("GLOSSARY.md").split())

        for required in (
            "Repository Reconciliation is a bounded repair path triggered when "
            "orientation detects drift",
            "Refresh exact repository, tracker, settings, workspace, process, "
            "temporary-resource, dependency, and ownership evidence",
            "exact identity, evidence, classification, proposed action, "
            "reversibility, reason, and next action",
            "one scoped batch approval before mutating legacy resources",
            "Verify every exact after-state",
            "Preserve unknown, dirty, active, shared, persistent, unique, "
            "user-owned, ambiguous, protected, and materially changed state",
            "inspected, proposed, approved, cleaned, closed, preserved, "
            "reconciled, released, and Live Verified states separately",
        ):
            with self.subTest(required=required):
                self.assertIn(required, agents)

        self.assertIn("**Repository Reconciliation**:", glossary)
        self.assertIn(
            "A bounded repair path triggered when repository orientation "
            "detects drift",
            glossary,
        )

    def test_repository_reconciliation_cases_fail_closed_and_preserve_state(
        self,
    ) -> None:
        payload = json.loads(
            read_text("tests/fixtures/repository_reconciliation_cases.json")
        )
        cases = {}
        for item in payload["cases"]:
            case = {**payload["case-defaults"], **item}
            case["manifest"] = {
                **payload["manifest-defaults"],
                **item.get("manifest", {}),
            }
            cases[case["id"]] = case

        self.assertEqual(payload["schema"], 1)
        self.assertFalse(payload["contract"]["real-resource-actions"])
        self.assertEqual(
            payload["contract"]["evidence-scope"],
            [
                "repository",
                "tracker",
                "settings",
                "workspace",
                "process",
                "temporary-resource",
                "dependency",
                "ownership",
            ],
        )
        self.assertEqual(
            payload["contract"]["separate-reporting-states"],
            [
                "inspected",
                "proposed",
                "approved",
                "cleaned",
                "closed",
                "preserved",
                "reconciled",
                "released",
                "live-verified",
            ],
        )
        self.assertEqual(
            set(payload["contract"]["manifest-fields"]),
            RECONCILIATION_MANIFEST_FIELDS,
        )
        self.assertEqual(
            set(payload["contract"]["preserve-flags"]),
            RECONCILIATION_PRESERVE_FLAGS,
        )
        self.assertEqual(
            set(cases),
            {
                "no-drift",
                "await-approval",
                "approved-exact-action",
                "unapproved-action",
                "changed-issue-before-mutation",
                "changed-pull-request-before-mutation",
                "changed-resource-before-mutation",
                "unverified-after-state",
                "already-resolved",
                "blocked-next-action",
                "unknown",
                "dirty",
                "active",
                "shared",
                "persistent",
                "unique",
                "user-owned",
                "ambiguous",
                "protected",
                "materially-changed",
            },
        )
        for case in cases.values():
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    repository_reconciliation_decision(case),
                    case["expected-decision"],
                )

        approved = cases["approved-exact-action"]
        self.assertEqual(
            approved["sequence"],
            [
                "inspect",
                "propose",
                "approve",
                "recheck",
                "mutate",
                "verify",
            ],
        )
        missing_field = dict(approved)
        missing_field["manifest"] = {
            key: value
            for key, value in approved["manifest"].items()
            if key != "next-action"
        }
        self.assertEqual(
            repository_reconciliation_decision(missing_field),
            "stop-incomplete-manifest",
        )

    def test_delivery_finalization_cases_cover_every_required_branch(self) -> None:
        payload = json.loads(
            read_text("tests/fixtures/delivery_finalization_cases.json")
        )
        terminal_cases = {case["id"]: case for case in payload["terminal-cases"]}
        resource_cases = {
            case["id"]: {**payload["resource-defaults"], **case}
            for case in payload["resource-cases"]
        }
        issue_cases = {case["id"]: case for case in payload["issue-cases"]}
        durable_cases = {
            case["id"]: case for case in payload["durable-truth-cases"]
        }
        reports = {case["id"]: case for case in payload["report-cases"]}

        self.assertEqual(payload["schema"], 1)
        self.assertEqual(
            payload["contract"]["separate-reporting-states"],
            [
                "outcome",
                "review",
                "merge",
                "closure",
                "cleanup",
                "finalization",
                "behavioral-live-verification",
            ],
        )
        self.assertEqual(
            set(terminal_cases),
            {
                "merged",
                "approved-alternative-delivery",
                "cancelled",
                "duplicated",
                "superseded",
                "equivalent-conclusive-closure",
                "open",
                "review-ready",
            },
        )
        self.assertFalse(payload["contract"]["real-resource-actions"])
        for case in terminal_cases.values():
            with self.subTest(terminal=case["id"]):
                self.assertEqual(
                    terminal_finalization_decision(case),
                    case["expected-decision"],
                )
        incomplete_review = dict(
            terminal_cases["merged"], **{"review-complete": False}
        )
        self.assertEqual(
            terminal_finalization_decision(incomplete_review),
            "do-not-finalize",
        )
        unverified_disposition = dict(
            terminal_cases["cancelled"], **{"disposition-verified": False}
        )
        self.assertEqual(
            terminal_finalization_decision(unverified_disposition),
            "do-not-finalize",
        )

        clean_cases = {
            case["resource-type"]
            for case in resource_cases.values()
            if case["id"].startswith("clean-")
        }
        self.assertEqual(clean_cases, TRANSIENT_RESOURCE_TYPES)
        premature_cleanup = dict(
            resource_cases["clean-worktree"],
            **{"finalization-started": False},
        )
        self.assertEqual(
            resource_finalization_decision(premature_cleanup),
            "do-not-touch",
        )
        required_preservation_cases = {
            "dirty",
            "active",
            "unique",
            "shared",
            "persistent",
            "user-owned",
            "ambiguous",
            "protected",
            "materially-changed",
            "still-needed-stack",
        }
        self.assertTrue(required_preservation_cases <= set(resource_cases))
        for case in resource_cases.values():
            with self.subTest(resource=case["id"]):
                decision = resource_finalization_decision(case)
                self.assertEqual(decision, case["expected-decision"])
                if decision == "remove":
                    self.assertEqual(case["before-state"], "present")
                    self.assertEqual(case["after-state"], "absent")
                elif decision in {"preserve", "reconcile"}:
                    self.assertEqual(case["before-state"], case["after-state"])

        ambiguous = resource_cases["ambiguous"]
        self.assertEqual(
            set(ambiguous["reconciliation-handoff"]),
            {"path", "branch", "head", "files", "reason", "next-action"},
        )
        incomplete_handoff = dict(ambiguous)
        incomplete_handoff["reconciliation-handoff"] = {
            key: value
            for key, value in ambiguous["reconciliation-handoff"].items()
            if key != "next-action"
        }
        self.assertEqual(
            resource_finalization_decision(incomplete_handoff),
            "stop-incomplete-reconciliation-handoff",
        )

        self.assertEqual(
            set(issue_cases),
            {
                "complete",
                "partial",
                "parent",
                "proof",
                "experiment",
                "duplicate",
                "superseded",
                "deferred",
            },
        )
        for case in issue_cases.values():
            with self.subTest(issue=case["id"]):
                decision = issue_closure_decision(case)
                self.assertEqual(decision, case["expected-decision"])
                self.assertNotIn("delete", decision)

        missing_partial_reference = dict(
            issue_cases["partial"], **{"durable-reference": False}
        )
        self.assertEqual(
            issue_closure_decision(missing_partial_reference),
            "stop-missing-reference",
        )
        parent_not_ready = dict(
            issue_cases["parent"], **{"required-children-terminal": False}
        )
        self.assertEqual(
            issue_closure_decision(parent_not_ready), "keep-open-parent"
        )
        proof_not_recorded = dict(
            issue_cases["proof"], **{"evidence-or-decision-recorded": False}
        )
        self.assertEqual(
            issue_closure_decision(proof_not_recorded), "keep-open-proof"
        )

        self.assertEqual(
            set(durable_cases),
            {"issue", "pull-request", "commit", "tag", "release", "proof"},
        )
        for case in durable_cases.values():
            with self.subTest(durable_truth=case["id"]):
                self.assertEqual(case["decision"], "preserve")
                self.assertEqual(case["before-state"], case["after-state"])

        for case in reports.values():
            with self.subTest(report=case["id"]):
                self.assertEqual(
                    finalization_report(case), case["expected-report"]
                )

    def test_workspace_isolation_cases_cover_every_selection_branch(
        self,
    ) -> None:
        payload = json.loads(
            read_text("tests/fixtures/workspace_isolation_cases.json")
        )
        cases = {
            case["id"]: {**payload["case_defaults"], **case}
            for case in payload["cases"]
        }

        self.assertEqual(payload["schema"], 1)
        self.assertEqual(
            set(cases),
            {
                "mutating",
                "read-only",
                "independent",
                "overlapping",
                "dirty",
                "active",
                "ambiguous",
                "moving-base",
            },
        )
        self.assertEqual(
            set(payload["contract"]["start_record_fields"]),
            {
                "intended-base",
                "branch",
                "workspace-path",
                "ownership",
                "starting-head",
            },
        )

        for case in cases.values():
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    workspace_isolation_decision(case),
                    case["expected_decision"],
                )

        for case_id in ("overlapping", "moving-base"):
            with self.subTest(unrelated_continuation=case_id):
                self.assertEqual(
                    cases[case_id]["unrelated_work_decision"], "continue"
                )

        unsafe_reuse = dict(cases["ambiguous"], reuse_existing=True)
        self.assertEqual(
            workspace_isolation_decision(unsafe_reuse),
            "stop-affected-writer",
        )

        unknown_independence = dict(
            cases["independent"], independence="unknown"
        )
        self.assertEqual(
            workspace_isolation_decision(unknown_independence),
            "stop-affected-writer",
        )

        unknown_ownership = dict(
            cases["mutating"], selected_ownership_known=False
        )
        self.assertEqual(
            workspace_isolation_decision(unknown_ownership),
            "stop-affected-writer",
        )

        interfering_reader = dict(
            cases["read-only"], interferes_with_writer=True
        )
        self.assertEqual(
            workspace_isolation_decision(interfering_reader),
            "stop-affected-work",
        )

        missing_record = dict(cases["mutating"])
        del missing_record["start_record"]
        self.assertEqual(
            workspace_isolation_decision(missing_record),
            "stop-affected-writer",
        )

        missing_claim = dict(cases["mutating"])
        missing_claim["ownership_claims"] = []
        self.assertEqual(
            workspace_isolation_decision(missing_claim),
            "stop-affected-writer",
        )

        independent_claims = cases["independent"]["ownership_claims"]
        self.assertEqual(len(independent_claims), 2)
        for resource in ("branch", "workspace", "file-set"):
            duplicate = dict(cases["independent"])
            duplicate["ownership_claims"] = [
                dict(claim) for claim in independent_claims
            ]
            duplicate["ownership_claims"][1][resource] = (
                duplicate["ownership_claims"][0][resource]
            )
            with self.subTest(duplicate_resource=resource):
                self.assertEqual(
                    workspace_isolation_decision(duplicate),
                    "stop-affected-writer",
                )

    def test_wayfinder_maps_only_the_visible_github_frontier(self) -> None:
        skill = read_text("skills/wayfinder/SKILL.md")
        normalized = " ".join(skill.split())
        wayfinder = frontmatter_metadata("skills/wayfinder/SKILL.md")
        self.assertEqual(wayfinder["handoff-skill"], "to-spec")
        for required in (
            "owning GitHub repository",
            "persistent decision fog",
            "regardless of predicted session length",
            "## Plan, don't do",
            "## Refer by name",
            "## Question",
            "## Type",
            "## Decision Issue types",
            "Research (AFK)",
            "Prototype (HITL)",
            "Grilling (HITL)",
            "Task (HITL or AFK)",
            "Invoke the bundled `research` Skill",
            "Invoke the bundled `prototype` Skill",
            "without asking the human to select a workflow",
            "breadth-first",
            "visible decision frontier",
            "native blocking",
            "assigning it",
            "agent never stands in for the human",
            "close it",
            "stop when the route is clear",
        ):
            self.assertIn(required, normalized)
        for forbidden in (
            "setup-matt-pocock-skills",
            "local-markdown",
            "Fire the research subagents",
            "100K",
            "more than one agent session can hold",
        ):
            self.assertNotIn(forbidden, skill)

        agents = read_text("AGENTS.md")
        normalized_agents = " ".join(agents.split())
        self.assertIn(
            "unresolved dependent decisions prevent a reliable spec",
            normalized_agents,
        )
        self.assertNotIn(
            "use `wayfinder` only when a large effort still has an unclear",
            normalized_agents,
        )

    def test_prototype_answers_a_typed_decision_issue(self) -> None:
        skill = " ".join(read_text("skills/prototype/SKILL.md").split())
        for required in (
            "Prototype Decision Issue",
            "without asking the human to select it",
            "[LOGIC.md](LOGIC.md)",
            "[UI.md](UI.md)",
            "runnable smoke check",
            "human verdict",
            "owning GitHub Issue",
            "throwaway branch",
        ):
            self.assertIn(required, skill)

    def test_research_answers_a_typed_decision_issue(self) -> None:
        skill = " ".join(read_text("skills/research/SKILL.md").split())
        for required in (
            "Research Decision Issue",
            "without asking the human to select it",
            "primary sources",
            "facts from inference",
            "single Markdown file",
            "owning GitHub Issue",
            "background agent",
        ):
            self.assertIn(required, skill)

    def test_grilling_keeps_the_exhaustive_frontier(self) -> None:
        skill = read_text("skills/grilling/SKILL.md")
        self.assertIn("Interview the user relentlessly", skill)
        self.assertIn("Ask the whole frontier in one round", skill)
        self.assertIn("frontier is empty", skill)
        self.assertNotIn("question limit", skill)

    def test_readme_explains_package_and_registry_boundaries(self) -> None:
        readme = read_text("README.md")
        for required in (
            "Skill Catalogue",
            "Product Registry",
            "Plugin Registry",
            "fresh session",
            "duplicate",
        ):
            self.assertIn(required, readme)

    def test_readme_explains_project_direction_runtime_and_limits(self) -> None:
        readme = read_text("README.md")
        normalized = " ".join(readme.split())
        self.assertNotIn("The workflow Skills are human-controlled.", readme)
        for required in (
            "VISION.md`, `MISSION.md`, and `OBJECTIVE.md",
            "human-controlled planning workflows",
            "`project-direction` is model-invoked",
            "SessionStart",
            "UserPromptSubmit",
            "SubagentStart",
            "8,192 bytes per file",
            "16,384 bytes combined",
            "intended base",
            "configured upstream",
            "ahead/behind",
            "`potentially_stale`",
            "without network access or checkout mutation",
            "does not prove reinjection after a subagent's private compaction",
            "review and trust",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
