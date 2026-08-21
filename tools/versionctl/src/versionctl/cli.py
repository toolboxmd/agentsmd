from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .errors import ExitCode, VersionCtlError
from .service import CommandOutcome, VersionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="versionctl",
        description="Deterministic repository version mechanics",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="inspect repository version state without writing")
    doctor.add_argument("--json", action="store_true", help="emit stable JSON")
    doctor.add_argument("--staged", action="store_true", help="inspect the Git index for commit-hook use")
    doctor.add_argument("--ci", action="store_true", help="compare committed HEAD with a base ref")
    doctor.add_argument("--base", help="base ref for --ci")

    adopt = commands.add_parser("adopt", help="create the initial repository version state")
    adopt.add_argument("version", help="chosen initial MAJOR.MINOR.PATCH version")
    adopt.add_argument("--reason", required=True, help="initial-version rationale")
    adopt.add_argument("--dry-run", action="store_true", help="preview without writing")
    adopt.add_argument("--json", action="store_true", help="emit stable JSON")

    prepare = commands.add_parser("prepare", help="apply an already-decided semantic impact")
    prepare.add_argument("impact", choices=("major", "minor", "patch"))
    prepare.add_argument("--reason", required=True, help="one-line deliverable summary")
    prepare.add_argument("--dry-run", action="store_true", help="preview without writing")
    prepare.add_argument("--json", action="store_true", help="emit stable JSON")

    release = commands.add_parser("release-check", help="validate a committed release candidate")
    release.add_argument("--version", help="required declared version")
    release.add_argument("--sha", help="required exact release commit")
    release.add_argument("--tag", help="required tag name")
    release.add_argument("--json", action="store_true", help="emit stable JSON")

    hooks = commands.add_parser("install-hooks", help="install managed pre-commit and commit-msg hooks")
    hooks.add_argument("--json", action="store_true", help="emit stable JSON")

    hook_check = commands.add_parser("hook-check", help=argparse.SUPPRESS)
    hook_check.add_argument("phase", choices=("pre-commit", "commit-msg"))
    hook_check.add_argument("--message-file", type=Path)
    hook_check.add_argument("--json", action="store_true", help="emit stable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    json_requested = "--json" in arguments
    try:
        args = build_parser().parse_args(arguments)
        service = VersionService.discover()
        if args.command == "doctor":
            outcome = service.doctor(staged=args.staged, ci=args.ci, base=args.base)
        elif args.command == "adopt":
            outcome = service.adopt(
                args.version,
                reason=args.reason,
                dry_run=args.dry_run,
            )
        elif args.command == "prepare":
            outcome = service.prepare(
                args.impact,
                reason=args.reason,
                dry_run=args.dry_run,
            )
        elif args.command == "release-check":
            outcome = service.release_check(
                version_value=args.version,
                sha=args.sha,
                tag=args.tag,
            )
        elif args.command == "install-hooks":
            outcome = service.install_hooks()
        elif args.command == "hook-check":
            outcome = service.hook_check(args.phase, message_file=args.message_file)
        else:
            raise AssertionError(args.command)
        _emit_outcome(outcome, as_json=args.json)
        return int(outcome.exit_code)
    except VersionCtlError as exc:
        _emit_error(exc, as_json=json_requested)
        return int(exc.code)
    except BrokenPipeError:
        return int(ExitCode.OK)


def _emit_outcome(outcome: CommandOutcome, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(outcome.report, indent=2, sort_keys=True, ensure_ascii=False))
        return
    command = outcome.report["command"]
    if command == "doctor":
        _print_doctor(outcome.report)
    elif command in {"prepare", "adopt"}:
        _print_write_preview(outcome.report)
    elif command == "release-check":
        print(
            f"release candidate OK: {outcome.report['tag']} at "
            f"{outcome.report['sha']} ({outcome.report['version']})"
        )
    elif command == "install-hooks":
        installed = ", ".join(outcome.report["installed"]) or "none"
        unchanged = ", ".join(outcome.report["unchanged"]) or "none"
        print(f"versionctl hooks installed: {installed}; unchanged: {unchanged}")
    elif command == "hook-check":
        print(f"versionctl {outcome.report['phase']} check: OK")
    else:
        print(f"versionctl {command}: OK")


def _print_doctor(report: dict[str, Any]) -> None:
    state = "OK" if report["ok"] else "FAILED"
    repo = report["repository"]
    version = report["version"]
    print(f"versionctl doctor [{report['scope']}]: {state}")
    print(f"repository: {repo['root']}")
    print(f"branch: {repo['branch'] or '(detached)'}")
    print(f"HEAD: {repo['head']}")
    print(f"version: {version['current']} ({version['source']})")
    print(f"tag: {version['tag']} -> {version['tagSha'] or '(not created)'}")
    print(f"dirty: {str(repo['dirty']).lower()}")
    if repo["upstream"]:
        print(f"cached remote: ahead {repo['ahead']}, behind {repo['behind']} of {repo['upstream']}")
    for issue in report["issues"]:
        print(f"{issue['code']}: {issue['message']}", file=sys.stderr)
    if report["bump"]["required"]:
        print("Choose semantic impact, then run exactly one of:", file=sys.stderr)
        print('  versionctl prepare patch --reason "<completed change>"', file=sys.stderr)
        print('  versionctl prepare minor --reason "<new capability>"', file=sys.stderr)
        print('  versionctl prepare major --reason "<incompatible contract>"', file=sys.stderr)


def _print_write_preview(report: dict[str, Any]) -> None:
    mode = "dry run" if report["dryRun"] else "applied"
    if report["command"] == "prepare":
        print(
            f"versionctl prepare {report['impact']} ({mode}): "
            f"{report['version']['before']} -> {report['version']['after']}"
        )
    else:
        print(f"versionctl adopt ({mode}): {report['version']}")
    for change in report["changes"]:
        pointer = change.get("pointer")
        target = f"{change['path']}{pointer}" if pointer else change["path"]
        print(f"  {target}: {change.get('before')} -> {change.get('after')}")
        if change.get("normalization"):
            print(f"    formatting: {change['normalization']}")
    print("next:")
    for item in report["next"]:
        print(f"  - {item}")


def _emit_error(error: VersionCtlError, *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {"schema": 1, "ok": False, "error": error.as_dict()},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        return
    print(f"versionctl: {error.code.name}: {error.message}", file=sys.stderr)
    if error.details:
        print(json.dumps(error.details, indent=2, sort_keys=True, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
