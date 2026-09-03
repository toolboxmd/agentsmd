#!/usr/bin/env python3
"""Contract tests for the AgentsMD release-to-Marketplace wake-up seam."""

from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"


def workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def step_block(source: str, name: str, next_name: str) -> str:
    start_marker = f"      - name: {name}\n"
    end_marker = f"      - name: {next_name}\n"
    start = source.index(start_marker)
    end = source.index(end_marker, start + len(start_marker))
    return source[start:end]


class ReleaseDispatchContractTests(unittest.TestCase):
    def test_token_is_restricted_to_marketplace_contents_write(self) -> None:
        source = workflow_text()
        token_step = step_block(
            source,
            "Mint Marketplace-only Toolybara token",
            "Dispatch Marketplace reconciliation wake-up",
        )

        self.assertIn(
            "uses: actions/create-github-app-token@"
            "bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0",
            token_step,
        )
        self.assertIn("client-id: ${{ vars.TOOLYBARA_CLIENT_ID }}", token_step)
        self.assertIn(
            "private-key: ${{ secrets.TOOLYBARA_PRIVATE_KEY }}", token_step
        )
        self.assertIn("owner: toolboxmd", token_step)
        self.assertIn("repositories: marketplace", token_step)
        self.assertIn("permission-contents: write", token_step)
        self.assertEqual(token_step.count("permission-"), 1)
        self.assertNotIn("skip-token-revoke", token_step)

    def test_dispatch_uses_only_the_app_token_and_minimal_wake_hint(self) -> None:
        source = workflow_text()
        dispatch_step = step_block(
            source,
            "Dispatch Marketplace reconciliation wake-up",
            "Report exact release identity",
        )

        self.assertIn(
            "GH_TOKEN: ${{ steps.toolybara-token.outputs.token }}", dispatch_step
        )
        self.assertNotIn("github.token", dispatch_step)
        self.assertNotIn("GITHUB_TOKEN", dispatch_step)
        self.assertIn("repos/toolboxmd/marketplace/dispatches", dispatch_step)
        self.assertIn('event_type: "agentsmd_release_published"', dispatch_step)
        self.assertIn("release_tag: $tag", dispatch_step)
        self.assertIn("untrusted wake hint", dispatch_step)
        for forbidden_claim in (
            "release_sha",
            "release_commit",
            "project_record",
            "record_digest",
            "eligible",
            "proof",
        ):
            self.assertNotIn(forbidden_claim, dispatch_step.lower())

    def test_dispatch_happens_only_after_release_and_fails_actionably(self) -> None:
        source = workflow_text()

        self.assertLess(
            source.index("      - name: Create matching GitHub Release"),
            source.index("      - name: Mint Marketplace-only Toolybara token"),
        )
        self.assertLess(
            source.index("      - name: Mint Marketplace-only Toolybara token"),
            source.index("      - name: Dispatch Marketplace reconciliation wake-up"),
        )
        self.assertIn("if ! gh api", source)
        self.assertIn(
            "::error title=Marketplace wake-up failed::", source
        )
        self.assertNotIn("continue-on-error", source)
        self.assertIn("Marketplace promotion: not claimed", source)
        self.assertIn("Distribution: not performed", source)
        self.assertIn("Installation: not performed", source)

    def test_workflow_does_not_request_broader_app_or_repository_scope(self) -> None:
        source = workflow_text()
        token_step = step_block(
            source,
            "Mint Marketplace-only Toolybara token",
            "Dispatch Marketplace reconciliation wake-up",
        )

        self.assertEqual(source.count("TOOLYBARA_CLIENT_ID"), 1)
        self.assertEqual(source.count("TOOLYBARA_PRIVATE_KEY"), 1)
        self.assertNotIn("repositories: agentsmd", token_step)
        for forbidden_permission in (
            "permission-actions:",
            "permission-administration:",
            "permission-metadata:",
            "permission-pull-requests:",
            "permission-secrets:",
            "permission-variables:",
            "permission-workflows:",
        ):
            self.assertNotIn(forbidden_permission, token_step)


if __name__ == "__main__":
    unittest.main()
