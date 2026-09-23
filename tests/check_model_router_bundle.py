#!/usr/bin/env python3
"""Check the real AgentsMD bundle in a supplied Model Router checkout.

Optional cross-repository proof, without installed-host changes or model calls:
    python3 tests/check_model_router_bundle.py /path/to/model-router
Model Router supplies isolated fake homes; its real materializers copy or link
this repository's bundle. Run against the exact two candidates being delivered.
"""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    router = Path(sys.argv[1]).resolve(strict=True)
    spec = importlib.util.spec_from_file_location(
        "agentsmd_package_checks", ROOT / "tests/test_pstack_packaging.py")
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    sys.path.insert(0, str(router))
    from tests.test_agentsmd_bundle import TestAgentsmdBundle
    from runner import kits, policy

    fixture = TestAgentsmdBundle()
    fixture.setUp()
    count = 0
    try:
        shutil.rmtree(fixture.operations)
        shutil.copytree(ROOT / "skills/operations", fixture.operations)
        shutil.rmtree(fixture.legacy)
        assert policy.kit_problems() == [], policy.kit_problems()
        for copied in (False, True):
            for host, materialize in fixture.materializers.items():
                for role in policy.KIT_ROLES[1:]:
                    target = fixture.base / f"actual-{host}-{role}-{copied}"
                    with patch("os.symlink", side_effect=OSError("copy proof")) if copied else nullcontext():
                        materialize(role, target)
                    bundle = (target / "skills/operations").resolve()
                    assert list(bundle.rglob("SKILL.md")) == [bundle / "SKILL.md"]
                    expected = ["operations"] + (["customize-opencode"] if host == "opencode" else [])
                    assert kits.observed_skills_for_kit_dir(target) == sorted(expected)
                    pending, seen = [bundle / "SKILL.md"], set()
                    while pending:
                        document = pending.pop().resolve()
                        if document in seen:
                            continue
                        seen.add(document)
                        for link in checks.relative_links(document):
                            destination = (document.parent / link).resolve(strict=True)
                            assert destination.is_relative_to(bundle), (document, link)
                            if destination.suffix == ".md":
                                pending.append(destination)
                    assert set(bundle.rglob("*.md")) <= seen
                    count += 1
        print(json.dumps({"kits": count, "hosts": len(fixture.materializers),
                          "roles": len(policy.KIT_ROLES) - 1,
                          "materialization": ["symlink", "copy"],
                          "result": "passed", "live_model_calls": False}))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
