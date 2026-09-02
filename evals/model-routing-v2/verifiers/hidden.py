#!/usr/bin/env python3
"""Controller-owned hidden verification for model-routing-v2 fixtures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Sequence


EXPECTED_USE_GROK_VERSION = "0.2.0"
EXPECTED_USE_GROK_DESCRIPTION = (
    "Delegate research, coding, and reviews to the local Grok Build CLI."
)
EXPECTED_CODEX_ONLY = {
    "skills": "./skills/",
    "homepage": "https://github.com/toolboxmd/use-grok#readme",
    "keywords": ["grok", "xai", "delegation", "coding"],
    "interface": {
        "displayName": "Use Grok",
        "shortDescription": "Delegate work to the local Grok Build CLI.",
        "longDescription": (
            "Delegate explicitly requested research, coding, implementation, "
            "review, and second-opinion tasks to the local Grok Build CLI with "
            "unrestricted tool permissions."
        ),
        "developerName": "toolbox.md",
        "category": "Developer Tools",
        "capabilities": ["Interactive", "Write"],
        "websiteURL": "https://github.com/toolboxmd/use-grok",
        "defaultPrompt": [
            "Ask Grok to review this implementation.",
            "Delegate this research question to Grok.",
            "Ask Grok to implement this change.",
        ],
    },
}


class Verification:
    """Collect named checks without allowing a verifier exception to escape."""

    def __init__(self, task: str) -> None:
        self.task = task
        self.checks: list[dict[str, Any]] = []
        self.timed_out_commands: list[str] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        item: dict[str, Any] = {"name": name, "passed": bool(passed)}
        if not passed and detail:
            item["detail"] = detail
        self.checks.append(item)

    def guarded(self, name: str, operation: Callable[[], None]) -> None:
        try:
            operation()
        except Exception as exc:  # The verifier reports malformed fixtures.
            self.check(name, False, f"{type(exc).__name__}: {exc}")

    def command(self, name: str, result: "CommandResult", expected: bool) -> None:
        if result.timed_out:
            self.timed_out_commands.append(name)
            self.check(name, False, "command timed out")
            return
        output = (result.stdout + result.stderr).strip()
        detail = f"returncode={result.returncode}"
        if output:
            detail += f" output={output[-800:]}"
        self.check(name, expected, detail)

    def result(self) -> dict[str, Any]:
        failures = [item for item in self.checks if not item["passed"]]
        status = (
            "TIMEOUT"
            if self.timed_out_commands
            else "PASS" if not failures else "FAIL"
        )
        return {
            "schema_version": 1,
            "task": self.task,
            "status": status,
            "checks": self.checks,
            "failures": failures,
            "failed_count": len(failures),
            "timed_out_commands": self.timed_out_commands,
        }


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


def workspace_file(workspace: Path, relative: str) -> Path:
    """Return a regular workspace-contained file without following it outside."""
    candidate = workspace / relative
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {relative}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise ValueError(f"not a regular workspace file: {relative}")
    return resolved


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def run_command(
    executable: str,
    arguments: Sequence[str],
    cwd: Path,
    timeout_seconds: int = 120,
) -> CommandResult:
    """Run one system executable with an isolated, credential-free environment."""
    with tempfile.TemporaryDirectory(prefix="routing-hidden-runtime-") as runtime:
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": runtime,
            "TMPDIR": runtime,
            "LANG": "C",
            "LC_ALL": "C",
            "NO_COLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        try:
            completed = subprocess.run(
                [executable, *arguments],
                cwd=cwd,
                env=environment,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return CommandResult(None, stdout, stderr, True)
    return CommandResult(
        completed.returncode, completed.stdout, completed.stderr, False
    )


def run_bash_test(workspace: Path, relative: str) -> CommandResult:
    script = workspace_file(workspace, relative)
    return run_command("/bin/bash", [str(script)], workspace)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_use_grok(workspace: Path) -> dict[str, Any]:
    verification = Verification("use-grok")
    relative_manifests = {
        "codex": ".codex-plugin/plugin.json",
        "claude": ".claude-plugin/plugin.json",
        "grok": ".grok-plugin/plugin.json",
    }
    manifests: dict[str, dict[str, Any]] = {}

    def read_manifests() -> None:
        for host, relative in relative_manifests.items():
            manifests[host] = load_json_object(workspace_file(workspace, relative))

    verification.guarded("all three manifests are valid JSON objects", read_manifests)
    all_manifests_loaded = len(manifests) == 3
    verification.check(
        "all three host manifests are present", all_manifests_loaded
    )

    if all_manifests_loaded:
        portable_fields = (
            "name",
            "version",
            "description",
            "repository",
            "license",
        )
        for field in portable_fields:
            values = [manifest.get(field) for manifest in manifests.values()]
            verification.check(
                f"portable manifest field agrees: {field}",
                len({json.dumps(value, sort_keys=True) for value in values}) == 1,
                json.dumps(dict(zip(manifests, values)), sort_keys=True),
            )
        verification.check(
            "canonical manifest identity is use-grok",
            all(item.get("name") == "use-grok" for item in manifests.values()),
        )
        verification.check(
            "all manifest versions are exactly 0.2.0",
            all(
                item.get("version") == EXPECTED_USE_GROK_VERSION
                for item in manifests.values()
            ),
        )
        verification.check(
            "canonical manifest description is preserved",
            all(
                item.get("description") == EXPECTED_USE_GROK_DESCRIPTION
                for item in manifests.values()
            ),
        )
        verification.check(
            "canonical repository is preserved",
            all(
                item.get("repository")
                == "https://github.com/toolboxmd/use-grok"
                for item in manifests.values()
            ),
        )
        verification.check(
            "Apache-2.0 license is preserved",
            all(item.get("license") == "Apache-2.0" for item in manifests.values()),
        )
        author_names = [
            item.get("author", {}).get("name")
            if isinstance(item.get("author"), dict)
            else None
            for item in manifests.values()
        ]
        verification.check(
            "author name agrees and remains lukaszmaj",
            author_names == ["lukaszmaj", "lukaszmaj", "lukaszmaj"],
            json.dumps(author_names),
        )
        codex = manifests["codex"]
        for field, expected in EXPECTED_CODEX_ONLY.items():
            verification.check(
                f"Codex-only metadata is preserved: {field}",
                codex.get(field) == expected,
            )
        for host in ("claude", "grok"):
            extra = sorted(set(EXPECTED_CODEX_ONLY).intersection(manifests[host]))
            verification.check(
                f"{host} manifest omits Codex-only metadata",
                not extra,
                ", ".join(extra),
            )

    def check_version() -> None:
        text = workspace_file(workspace, "VERSION").read_text(encoding="utf-8")
        verification.check(
            "root VERSION is exactly 0.2.0",
            text.splitlines() == [EXPECTED_USE_GROK_VERSION],
            repr(text),
        )

    verification.guarded("root VERSION is readable", check_version)

    def check_readme() -> None:
        readme = workspace_file(workspace, "README.md").read_text(encoding="utf-8")
        lower = readme.lower()
        layout_phrases = (
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".grok-plugin/plugin.json",
        )
        for phrase in layout_phrases:
            verification.check(
                f"README layout names {phrase}", phrase in lower
            )
        installation_phrases = (
            "codex plugin add use-grok@toolboxmd",
            "grok plugin install use-grok --trust",
            "claude code",
            "extraknownmarketplaces",
            "use-grok@toolboxmd",
        )
        for phrase in installation_phrases:
            verification.check(
                f"README installation covers {phrase}", phrase in lower
            )
        workflow_phrases = (
            "portable agent skill",
            "local grok build cli",
            "--cwd",
            "--always-approve",
            "subagents",
            "web search",
            "file edits",
        )
        for phrase in workflow_phrases:
            verification.check(
                f"README preserves workflow phrase {phrase}", phrase in lower
            )

    verification.guarded("README is readable", check_readme)

    def check_changelog() -> None:
        changelog = workspace_file(workspace, "CHANGELOG.md").read_text(
            encoding="utf-8"
        )
        heading = re.search(
            r"(?m)^##\s+\[?0\.2\.0\]?\s+-\s+2026-08-31\s*$", changelog
        )
        verification.check(
            "changelog has the 0.2.0 release dated 2026-08-31",
            heading is not None,
        )
        section = ""
        if heading is not None:
            start = heading.end()
            next_heading = re.search(r"(?m)^##\s+", changelog[start:])
            end = start + next_heading.start() if next_heading else len(changelog)
            section = changelog[start:end]
        verification.check(
            "0.2.0 changelog names Claude Code",
            "Claude Code" in section,
        )
        verification.check(
            "0.2.0 changelog names Grok Build",
            "Grok Build" in section,
        )

    verification.guarded("CHANGELOG is readable", check_changelog)

    public = run_bash_test(workspace, "tests/use-grok.test.sh")
    public_passed = public.returncode == 0 and not public.timed_out
    verification.command("original public use-grok tests pass", public, public_passed)

    def mutation_result(host: str, field: str) -> CommandResult:
        with tempfile.TemporaryDirectory(prefix="routing-use-grok-mutation-") as raw:
            clone = Path(raw) / "workspace"
            shutil.copytree(
                workspace,
                clone,
                ignore=shutil.ignore_patterns(
                    ".git", ".venv", "__pycache__", "*.pyc"
                ),
            )
            target = workspace_file(clone.resolve(), relative_manifests[host])
            value = load_json_object(target)
            value[field] = "wrong-name" if field == "name" else "9.9.9"
            target.write_text(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return run_bash_test(clone.resolve(), "tests/use-grok.test.sh")

    for host in ("codex", "claude", "grok"):
        for field in ("name", "version"):
            check_name = f"public tests reject {host} manifest {field} drift"
            if not public_passed:
                verification.check(
                    check_name,
                    False,
                    "not discriminating because the unmodified public tests failed",
                )
                continue

            def check_mutation(
                host_name: str = host,
                field_name: str = field,
                name: str = check_name,
            ) -> None:
                result = mutation_result(host_name, field_name)
                verification.command(
                    name,
                    result,
                    result.returncode not in (0, None) and not result.timed_out,
                )

            verification.guarded(check_name, check_mutation)

    return verification.result()


def wiki_page(title: str, tags: str, summary: str = "Useful content.") -> str:
    return f'''---
title: "{title}"
type: concepts
tags: {tags}
sources: []
summary: "{summary}"
created: "2026-08-31T00:00:00Z"
updated: "2026-08-31T00:00:00Z"
---
{summary}
'''


def verify_karpathy_pointer(workspace: Path) -> dict[str, Any]:
    verification = Verification("karpathy-pointer")
    for relative in (
        "tests/unit/test-build-index.sh",
        "tests/unit/test-discover.sh",
    ):
        result = run_bash_test(workspace, relative)
        verification.command(
            f"original public verifier passes: {relative}",
            result,
            result.returncode == 0 and not result.timed_out,
        )

    build_script = workspace_file(workspace, "scripts/wiki-build-index.py")
    discover_script = workspace_file(workspace, "scripts/wiki-discover.py")

    with tempfile.TemporaryDirectory(prefix="routing-karpathy-hidden-") as raw:
        wiki = Path(raw) / "wiki"
        concepts = wiki / "concepts"
        projects = wiki / "projects"
        nested = projects / "nested"
        deep = nested / "deep"
        for directory in (concepts, deep):
            directory.mkdir(parents=True, exist_ok=True)
        (wiki / ".wiki-config").write_text("", encoding="utf-8")

        visible_files = {
            "ordinary": concepts / "ordinary.md",
            "missing": concepts / "missing.md",
            "malformed": concepts / "malformed.md",
            "non_mapping": concepts / "non-mapping.md",
            "non_utf8": concepts / "non-utf8.md",
            "unreadable": concepts / "filesystem-unreadable.md",
        }
        pointer_files = {
            "case_whitespace": concepts / "pointer-case-whitespace.md",
            "mixed_tags": concepts / "pointer-mixed-tags.md",
            "deep": deep / "deep-pointer.md",
        }
        project_visible = projects / "visible.md"
        nested_visible = nested / "nested-visible.md"

        visible_files["ordinary"].write_text(
            wiki_page("Ordinary page", "[ordinary]"), encoding="utf-8"
        )
        visible_files["missing"].write_text(
            "# Missing frontmatter remains visible\n", encoding="utf-8"
        )
        visible_files["malformed"].write_text(
            "---\ntitle: Malformed visible\ntags: [pointer\n---\nbody\n",
            encoding="utf-8",
        )
        visible_files["non_mapping"].write_text(
            "---\n- pointer\n---\nbody\n", encoding="utf-8"
        )
        visible_files["non_utf8"].write_bytes(
            b"---\ntitle: Non UTF8 visible\ntags: []\n---\n\xff\xfe\n"
        )
        visible_files["unreadable"].write_text(
            wiki_page("Filesystem unreadable visible", "[]"), encoding="utf-8"
        )
        pointer_files["case_whitespace"].write_text(
            wiki_page("Hidden case whitespace pointer", '[" Pointer "]'),
            encoding="utf-8",
        )
        pointer_files["mixed_tags"].write_text(
            wiki_page("Hidden mixed tags pointer", "[reference, POINTER]"),
            encoding="utf-8",
        )
        pointer_files["deep"].write_text(
            wiki_page("Hidden deep pointer", "[pointer]"), encoding="utf-8"
        )
        project_visible.write_text(
            wiki_page("Project visible", "[]"), encoding="utf-8"
        )
        nested_visible.write_text(
            wiki_page("Nested visible", "[]"), encoding="utf-8"
        )

        pointer_hashes = {
            name: sha256_file(path) for name, path in pointer_files.items()
        }
        os.chmod(visible_files["unreadable"], 0)
        try:
            discover = run_command(
                "/usr/bin/python3",
                [str(discover_script), "--wiki-root", str(wiki)],
                workspace,
            )
            build = run_command(
                "/usr/bin/python3",
                [str(build_script), "--wiki-root", str(wiki), "--rebuild-all"],
                workspace,
            )
        finally:
            os.chmod(visible_files["unreadable"], 0o600)

        verification.command(
            "discovery handles conservative and pointer cases without crashing",
            discover,
            discover.returncode == 0 and not discover.timed_out,
        )
        discovery_data: dict[str, Any] = {}
        if discover.returncode == 0 and not discover.timed_out:
            try:
                parsed = json.loads(discover.stdout)
                if not isinstance(parsed, dict):
                    raise ValueError("discovery output is not an object")
                discovery_data = parsed
                verification.check("discovery output is a JSON object", True)
            except (json.JSONDecodeError, ValueError) as exc:
                verification.check("discovery output is a JSON object", False, str(exc))
        else:
            verification.check(
                "discovery output is a JSON object", False, "discovery failed"
            )

        verification.check(
            "discovery output shape is unchanged",
            set(discovery_data) == {"categories", "reserved", "depths", "counts"},
            json.dumps(sorted(discovery_data)),
        )
        counts = discovery_data.get("counts", {})
        depths = discovery_data.get("depths", {})
        verification.check(
            "flat case whitespace and mixed pointer tags are excluded from counts",
            isinstance(counts, dict) and counts.get("concepts") == 6,
            json.dumps(counts, sort_keys=True),
        )
        verification.check(
            "deep pointer is excluded from recursive project count",
            isinstance(counts, dict) and counts.get("projects") == 2,
            json.dumps(counts, sort_keys=True),
        )
        verification.check(
            "deep pointer does not increase discovery depth",
            isinstance(depths, dict) and depths.get("projects") == 2,
            json.dumps(depths, sort_keys=True),
        )

        verification.command(
            "index build handles conservative and pointer cases without crashing",
            build,
            build.returncode == 0 and not build.timed_out,
        )
        concept_index = ""
        project_index = ""
        root_index = ""
        if build.returncode == 0 and not build.timed_out:
            try:
                concept_index = (concepts / "_index.md").read_text(encoding="utf-8")
                project_index = (projects / "_index.md").read_text(encoding="utf-8")
                root_index = (wiki / "index.md").read_text(encoding="utf-8")
                verification.check("generated indexes are readable UTF-8", True)
            except (OSError, UnicodeDecodeError) as exc:
                verification.check("generated indexes are readable UTF-8", False, str(exc))
        else:
            verification.check(
                "generated indexes are readable UTF-8", False, "index build failed"
            )

        for forbidden in (
            "Hidden case whitespace pointer",
            "pointer-case-whitespace.md",
            "Hidden mixed tags pointer",
            "pointer-mixed-tags.md",
        ):
            verification.check(
                f"category rows omit proven pointer: {forbidden}",
                forbidden not in concept_index if concept_index else False,
            )
        for visible in (
            "Ordinary page",
            "missing.md",
            "malformed.md",
            "non-mapping.md",
            "non-utf8.md",
            "filesystem-unreadable.md",
        ):
            verification.check(
                f"category rows keep conservative visible page: {visible}",
                visible in concept_index,
            )

        verification.check(
            "recursive subdirectory preview omits deep pointer title",
            bool(project_index) and "Hidden deep pointer" not in project_index,
        )
        verification.check(
            "recursive subdirectory preview keeps ordinary title",
            "Nested visible" in project_index,
        )
        nested_line = next(
            (line for line in project_index.splitlines() if "[nested/]" in line),
            "",
        )
        verification.check(
            "recursive subdirectory count excludes deep pointer",
            "1 pages" in nested_line,
            nested_line,
        )

        concepts_line = next(
            (
                line
                for line in root_index.splitlines()
                if "concepts/_index.md" in line.lower()
            ),
            "",
        )
        projects_line = next(
            (
                line
                for line in root_index.splitlines()
                if "projects/_index.md" in line.lower()
            ),
            "",
        )
        verification.check(
            "root index uses filtered concepts count",
            "6 pages" in concepts_line,
            concepts_line,
        )
        verification.check(
            "root index uses filtered projects count",
            "2 pages" in projects_line,
            projects_line,
        )
        verification.check(
            "root index uses filtered projects depth",
            "2 levels deep" in projects_line,
            projects_line,
        )

        for name, path in pointer_files.items():
            verification.check(
                f"pointer bytes are preserved: {name}",
                path.exists() and sha256_file(path) == pointer_hashes[name],
            )

    return verification.result()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task", required=True, choices=("use-grok", "karpathy-pointer")
    )
    parser.add_argument("--workspace", required=True, type=Path)
    arguments = parser.parse_args()

    try:
        workspace = arguments.workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise NotADirectoryError(workspace)
        result = (
            verify_use_grok(workspace)
            if arguments.task == "use-grok"
            else verify_karpathy_pointer(workspace)
        )
    except Exception as exc:  # Keep the CLI machine-readable on fixture failure.
        result = {
            "schema_version": 1,
            "task": arguments.task,
            "status": "FAIL",
            "checks": [],
            "failures": [
                {
                    "name": "verifier setup",
                    "passed": False,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ],
            "failed_count": 1,
            "timed_out_commands": [],
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
