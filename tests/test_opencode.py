"""OpenCode ownership and adapter proof in isolated homes, without model calls."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "bin/agentsmd-opencode"


class OpenCodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "xdg"
        self.target = self.config / "opencode/AGENTS.md"
        self.target.parent.mkdir(parents=True)
        self.source = self.root / "release/AGENTS.md"
        self.source.parent.mkdir()
        self.source.write_text("canonical contract\n")
        self.env = {**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config),
                    "XDG_DATA_HOME": str(self.root / "data"), "XDG_CACHE_HOME": str(self.root / "cache"),
                    "XDG_STATE_HOME": str(self.root / "state")}
        self.preserved = [self.target.parent / "opencode.json", self.target.parent / "opencode.jsonc",
                          self.root / "data/opencode/auth.json", self.home / ".agents/skills/user/SKILL.md"]
        for path in self.preserved:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("user-owned fixture " + path.name)
        self.hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.preserved}

    def tearDown(self):
        self.assertEqual(self.hashes, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.preserved})

    def call(self, *args, env=None):
        result = subprocess.run([str(COMMAND), *map(str, args)], env=env or self.env,
                                capture_output=True, text=True, cwd=ROOT)
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def manage(self, name, *args):
        return self.call(name, "--source", self.source, *args)

    def test_install_status_idempotent_update_and_uninstall(self):
        self.assertEqual(self.manage("status")[1]["status"], "missing")
        code, report = self.manage("install")
        self.assertEqual(code, 0)
        self.assertEqual(report["after"]["target_sha256"], report["after"]["source_sha256"])
        self.assertEqual(self.manage("install")[1]["action"], "unchanged")
        self.assertEqual(self.manage("status")[1]["status"], "owned-link")
        newer = self.root / "new-release/AGENTS.md"
        newer.parent.mkdir()
        newer.write_text("new canonical contract")
        self.assertEqual(self.call("update", "--source", newer)[0], 2)
        self.assertEqual(self.call("update", "--source", newer, "--previous-source", self.source)[0], 0)
        self.assertEqual(self.target.resolve(), newer)
        self.assertEqual(self.manage("uninstall")[0], 2)
        self.assertEqual(self.call("uninstall", "--source", newer)[0], 0)
        self.assertFalse(os.path.lexists(self.target))

    def test_regular_divergent_and_broken_user_paths_preserved(self):
        other = self.root / "other/AGENTS.md"
        other.parent.mkdir()
        for kind in ("regular-file", "divergent-link", "broken-link", "other-path"):
            with self.subTest(kind=kind):
                if kind == "regular-file":
                    self.target.write_text("user instructions")
                elif kind == "other-path":
                    self.target.mkdir()
                else:
                    if kind == "divergent-link":
                        other.write_text("unrelated instructions")
                    elif other.exists():
                        other.unlink()
                    self.target.symlink_to(other)
                self.assertEqual(self.manage("status")[1]["status"], kind)
                for action in ("install", "update", "uninstall"):
                    self.assertEqual(self.manage(action)[0], 2)
                if self.target.is_symlink():
                    self.assertEqual(os.readlink(self.target), str(other))
                    self.target.unlink()
                elif self.target.is_dir():
                    self.target.rmdir()
                else:
                    self.assertEqual(self.target.read_text(), "user instructions")
                    self.target.unlink()

    def test_broken_owned_link_can_be_removed_or_explicitly_updated(self):
        self.manage("install")
        self.source.unlink()
        code, report = self.manage("status")
        self.assertEqual(code, 2)
        self.assertTrue(report["owned"])
        self.assertEqual(report["status"], "broken-link")
        self.assertEqual(self.manage("uninstall")[0], 0)

    def test_fallback_home_and_relative_xdg_rejection(self):
        env = dict(self.env)
        del env["XDG_CONFIG_HOME"]
        code, report = self.call("install", "--source", self.source, env=env)
        self.assertEqual(code, 0)
        self.assertEqual(report["after"]["target"], str(self.home / ".config/opencode/AGENTS.md"))
        env["XDG_CONFIG_HOME"] = "relative"
        self.assertEqual(self.call("install", "--source", self.source, env=env)[0], 2)

    def test_cache_and_symlink_source_rejected(self):
        cached = self.root / "plugins/cache/release/AGENTS.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("cached")
        self.assertEqual(self.call("install", "--source", cached)[0], 2)
        alias = self.root / "alias"
        alias.symlink_to(cached.parent, target_is_directory=True)
        self.assertEqual(self.call("install", "--source", alias / "AGENTS.md")[0], 2)
        self.assertFalse(os.path.lexists(self.target))

    def test_status_and_uninstall_reject_source_alias_into_cache(self):
        cached = self.root / "plugins/cache/release/AGENTS.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("cached")
        alias = self.root / "alias/AGENTS.md"
        alias.parent.mkdir()
        alias.symlink_to(cached)
        self.target.symlink_to(alias)
        for action in ("status", "uninstall"):
            self.assertEqual(self.call(action, "--source", alias)[0], 2)
            self.assertEqual(os.readlink(self.target), str(alias))
        self.assertEqual(cached.read_text(), "cached")

    def test_update_exact_broken_previous_release(self):
        previous = self.root / "removed/AGENTS.md"
        self.target.symlink_to(previous)
        code, report = self.manage("update", "--previous-source", previous)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["before"]["status"], "broken-link")
        self.assertEqual(self.target.resolve(), self.source)

    def test_existing_directory_link_is_not_broken(self):
        directory = self.root / "user-directory"
        directory.mkdir()
        self.target.symlink_to(directory, target_is_directory=True)
        code, report = self.manage("status")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "other-path")
        self.assertFalse(report["owned"])
        for action in ("install", "update", "uninstall"):
            self.assertEqual(self.manage(action)[0], 2)
        self.assertEqual(os.readlink(self.target), str(directory))
        self.assertTrue(directory.is_dir())

    def test_uninstall_rejects_existing_directory_source(self):
        self.source.unlink()
        self.source.mkdir()
        self.target.symlink_to(self.source, target_is_directory=True)
        self.assertEqual(self.manage("uninstall")[0], 2)
        self.assertEqual(os.readlink(self.target), str(self.source))
        self.assertTrue(self.source.is_dir())

    def test_update_rejects_previous_directory_source(self):
        previous = self.root / "previous/AGENTS.md"
        previous.mkdir(parents=True)
        self.target.symlink_to(previous, target_is_directory=True)
        self.assertEqual(self.manage("update", "--previous-source", previous)[0], 2)
        self.assertEqual(os.readlink(self.target), str(previous))
        self.assertTrue(previous.is_dir())

    def prepare_skills(self, names=("alpha", "beta")):
        source = self.root / "release/skills"
        for name in names:
            (source / name).mkdir(parents=True)
            (source / name / "SKILL.md").write_text("# " + name + "\n")
        (source / "not-a-skill").mkdir()
        self.skills = self.target.parent / "skills"
        return source

    def test_skill_links_install_repeat_status_and_uninstall(self):
        source = self.prepare_skills()
        code, report = self.call("skills", "status", "--source", source)
        self.assertEqual(code, 2)
        self.assertEqual([entry["status"] for entry in report["entries"]], ["missing", "missing"])
        code, report = self.call("skills", "install", "--source", source)
        self.assertEqual(code, 0, report)
        self.assertEqual([entry["action"] for entry in report["entries"]], ["installed", "installed"])
        self.assertEqual(report["target_directory"], str(self.skills))
        for name in ("alpha", "beta"):
            self.assertEqual((self.skills / name).resolve(), source / name)
        self.assertFalse(os.path.lexists(self.skills / "not-a-skill"))
        self.assertEqual(self.call("skills", "status", "--source", source)[0], 0)
        code, report = self.call("skills", "install", "--source", source)
        self.assertEqual(code, 0, report)
        self.assertEqual([entry["action"] for entry in report["entries"]], ["unchanged", "unchanged"])
        code, report = self.call("skills", "uninstall", "--source", source)
        self.assertEqual(code, 0, report)
        self.assertEqual([entry["action"] for entry in report["entries"]], ["uninstalled", "uninstalled"])
        for name in ("alpha", "beta"):
            self.assertFalse(os.path.lexists(self.skills / name))
        self.assertEqual(self.call("skills", "uninstall", "--source", source)[0], 2)

    def test_skill_links_preserve_user_entries_and_install_the_rest(self):
        source = self.prepare_skills(("alpha", "beta", "gamma"))
        self.skills.mkdir(parents=True)
        (self.skills / "alpha").write_text("user skill file")
        foreign = self.root / "foreign/beta"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("user skill\n")
        (self.skills / "beta").symlink_to(foreign, target_is_directory=True)
        code, report = self.call("skills", "install", "--source", source)
        self.assertEqual(code, 2)
        self.assertEqual({entry["name"]: entry["action"] for entry in report["entries"]},
                         {"alpha": "preserved", "beta": "preserved", "gamma": "installed"})
        self.assertEqual({entry["name"]: entry["before"]["status"] for entry in report["entries"]},
                         {"alpha": "regular-file", "beta": "divergent-link", "gamma": "missing"})
        self.assertEqual((self.skills / "gamma").resolve(), source / "gamma")
        for action in ("status", "uninstall"):
            self.assertEqual(self.call("skills", action, "--source", source)[0], 2)
        self.assertEqual((self.skills / "alpha").read_text(), "user skill file")
        self.assertEqual(os.readlink(self.skills / "beta"), str(foreign))
        self.assertFalse(os.path.lexists(self.skills / "gamma"))

    def test_skill_links_status_and_uninstall_reach_removed_sources(self):
        source = self.prepare_skills()
        self.assertEqual(self.call("skills", "install", "--source", source)[0], 0)
        shutil.rmtree(source / "alpha")
        (source / "beta/SKILL.md").unlink()
        code, report = self.call("skills", "status", "--source", source)
        self.assertEqual(code, 2)
        states = {entry["name"]: (entry["status"], entry["owned"]) for entry in report["entries"]}
        self.assertEqual(states, {"alpha": ("broken-link", True), "beta": ("owned-link", True)})
        code, report = self.call("skills", "uninstall", "--source", source)
        self.assertEqual(code, 0, report)
        self.assertEqual([entry["action"] for entry in report["entries"]], ["uninstalled", "uninstalled"])
        for name in ("alpha", "beta"):
            self.assertFalse(os.path.lexists(self.skills / name))
        shutil.rmtree(source)
        self.assertEqual(self.call("skills", "status", "--source", source)[0], 2)
        self.assertEqual(self.call("skills", "install", "--source", source)[0], 2)

    def test_skill_links_uninstall_removes_owned_link_to_replaced_source(self):
        source = self.prepare_skills()
        self.assertEqual(self.call("skills", "install", "--source", source)[0], 0)
        shutil.rmtree(source / "alpha")
        (source / "alpha").write_text("replaced by a regular file\n")
        code, report = self.call("skills", "status", "--source", source)
        self.assertEqual(code, 2)
        alpha = next(entry for entry in report["entries"] if entry["name"] == "alpha")
        self.assertTrue(alpha["owned"])
        self.assertEqual(alpha["status"], "other-path")
        code, report = self.call("skills", "uninstall", "--source", source)
        self.assertEqual(code, 0, report)
        self.assertEqual([entry["action"] for entry in report["entries"]], ["uninstalled", "uninstalled"])
        self.assertFalse(os.path.lexists(self.skills / "alpha"))
        self.assertEqual((source / "alpha").read_text(), "replaced by a regular file\n")

    def test_skill_links_refuse_cache_bound_skill_before_linking(self):
        source = self.prepare_skills()
        cached = self.root / "plugins/cache/gamma"
        cached.mkdir(parents=True)
        (cached / "SKILL.md").write_text("cached\n")
        (source / "gamma").symlink_to(cached, target_is_directory=True)
        code, report = self.call("skills", "install", "--source", source)
        self.assertEqual(code, 2)
        entry = next(entry for entry in report["entries"] if entry["name"] == "gamma")
        self.assertEqual(entry["action"], "rejected")
        self.assertEqual(entry["reason"], "cache-bound-source")
        self.assertFalse(os.path.lexists(self.skills / "gamma"))
        self.assertEqual((self.skills / "alpha").resolve(), source / "alpha")

    def test_skill_links_use_config_dir_and_home_fallback(self):
        source = self.prepare_skills()
        env = {**self.env, "OPENCODE_CONFIG_DIR": str(self.root / "custom")}
        code, report = self.call("skills", "install", "--source", source, env=env)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["target_directory"], str(self.root / "custom/skills"))
        env = dict(self.env)
        del env["XDG_CONFIG_HOME"]
        code, report = self.call("skills", "install", "--source", source, env=env)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["target_directory"], str(self.home / ".config/opencode/skills"))
        self.assertEqual((self.home / ".config/opencode/skills/alpha").resolve(), source / "alpha")

    def test_skill_links_reject_cache_source_and_shared_targets(self):
        cached = self.root / "plugins/cache/skills"
        (cached / "alpha").mkdir(parents=True)
        (cached / "alpha/SKILL.md").write_text("cached\n")
        self.assertEqual(self.call("skills", "install", "--source", cached)[0], 2)
        source = self.prepare_skills()
        for name in (".agents", ".claude", ".grok"):
            env = {**self.env, "OPENCODE_CONFIG_DIR": str(self.home / name)}
            code, report = self.call("skills", "install", "--source", source, env=env)
            self.assertEqual(code, 2, report)
            self.assertIn("shared Skill directory", report["error"])
            self.assertFalse(os.path.lexists(self.home / name / "skills/alpha"))
        alias = self.root / "alias"
        alias.mkdir()
        (alias / "skills").symlink_to(self.home / ".agents/skills", target_is_directory=True)
        env = {**self.env, "OPENCODE_CONFIG_DIR": str(alias)}
        self.assertEqual(self.call("skills", "install", "--source", source, env=env)[0], 2)
        self.assertFalse(os.path.lexists(self.home / ".agents/skills/alpha"))

    def prepare_plugin(self):
        clone = self.root / "release"
        (clone / "bin").mkdir(parents=True, exist_ok=True)
        (clone / "bin/project-direction").write_text("#!/bin/sh\nexit 0\n")
        module = clone / "opencode/agentsmd-project-direction.js"
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text("export default async () => ({});\n")
        self.plugin = self.target.parent / "plugins/agentsmd-project-direction.js"
        return clone, module

    def test_plugin_link_install_repeat_status_and_uninstall(self):
        clone, module = self.prepare_plugin()
        code, report = self.call("plugin", "status", "--source", clone)
        self.assertEqual(code, 2)
        self.assertEqual(report["entry"]["status"], "missing")
        self.assertEqual(report["target"], str(self.plugin))
        code, report = self.call("plugin", "install", "--source", clone)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["action"], "installed")
        self.assertEqual(os.readlink(self.plugin), str(module))
        self.assertEqual(self.call("plugin", "install", "--source", module)[1]["action"], "unchanged")
        self.assertEqual(self.call("plugin", "status", "--source", module)[0], 0)
        code, report = self.call("plugin", "uninstall", "--source", clone)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["action"], "uninstalled")
        self.assertFalse(os.path.lexists(self.plugin))
        self.assertEqual(self.call("plugin", "uninstall", "--source", clone)[0], 2)

    def test_plugin_link_preserves_existing_entries_and_removes_owned_broken_link(self):
        clone, module = self.prepare_plugin()
        self.plugin.parent.mkdir(parents=True)
        foreign = self.root / "foreign/agentsmd-project-direction.js"
        foreign.parent.mkdir()
        foreign.write_text("user plugin\n")
        for kind, prepare in (("regular-file", lambda: self.plugin.write_text("user plugin file")),
                              ("divergent-link", lambda: self.plugin.symlink_to(foreign))):
            with self.subTest(kind=kind):
                prepare()
                self.assertEqual(self.call("plugin", "status", "--source", clone)[1]["entry"]["status"], kind)
                for action in ("install", "uninstall"):
                    code, report = self.call("plugin", action, "--source", clone)
                    self.assertEqual(code, 2, report)
                    self.assertEqual(report["action"], "preserved")
                if self.plugin.is_symlink():
                    self.assertEqual(os.readlink(self.plugin), str(foreign))
                    self.plugin.unlink()
                else:
                    self.assertEqual(self.plugin.read_text(), "user plugin file")
                    self.plugin.unlink()
        self.assertEqual(self.call("plugin", "install", "--source", clone)[0], 0)
        module.unlink()
        code, report = self.call("plugin", "status", "--source", clone)
        self.assertEqual(code, 2)
        self.assertEqual(report["entry"]["status"], "broken-link")
        self.assertTrue(report["entry"]["owned"])
        self.assertEqual(self.call("plugin", "install", "--source", clone)[0], 2)
        self.assertEqual(self.call("plugin", "uninstall", "--source", clone)[0], 0)
        self.assertFalse(os.path.lexists(self.plugin))

    def test_plugin_link_rejects_noncanonical_and_loaderless_sources(self):
        clone, module = self.prepare_plugin()
        alias = self.root / "alias-clone"
        alias.symlink_to(clone, target_is_directory=True)
        code, report = self.call("plugin", "install", "--source", alias / "opencode" / module.name)
        self.assertEqual(code, 2)
        self.assertIn("symlink alias", report["error"])
        aliased = self.root / "aliased-clone"
        (aliased / "bin").mkdir(parents=True)
        (aliased / "bin/project-direction").write_text("#!/bin/sh\nexit 0\n")
        (aliased / "opencode").symlink_to(module.parent, target_is_directory=True)
        code, report = self.call("plugin", "install", "--source", aliased)
        self.assertEqual(code, 2)
        self.assertIn("symlink alias", report["error"])
        standalone = self.root / "standalone/opencode"
        standalone.mkdir(parents=True)
        (standalone / module.name).write_text("export default async () => ({});\n")
        code, report = self.call("plugin", "install", "--source", standalone.parent)
        self.assertEqual(code, 2)
        self.assertIn("bin/project-direction", report["error"])
        self.assertFalse(os.path.lexists(self.plugin))

    def reset_plugin_fixture(self):
        clone = self.root / "release"
        if clone.is_symlink():
            clone.unlink()
        elif clone.is_dir():
            shutil.rmtree(clone)
        plugin = self.target.parent / "plugins/agentsmd-project-direction.js"
        if os.path.lexists(plugin):
            plugin.unlink()
        return self.prepare_plugin()

    def test_plugin_link_ownership_survives_every_source_mutation(self):
        def remove_clone_root(clone, module):
            shutil.rmtree(clone)

        def remove_loader(clone, module):
            (clone / "bin/project-direction").unlink()

        def remove_opencode_directory(clone, module):
            shutil.rmtree(module.parent)

        def replace_module_with_directory(clone, module):
            module.unlink()
            module.mkdir()

        def replace_module_with_alias(clone, module):
            copy = module.parent / "copy.js"
            copy.write_text(module.read_text())
            module.unlink()
            module.symlink_to(copy)

        def alias_the_clone_root(clone, module):
            moved = self.root / "moved-release"
            if moved.is_dir():
                shutil.rmtree(moved)
            clone.rename(moved)
            clone.symlink_to(moved, target_is_directory=True)

        for mutate in (remove_clone_root, remove_loader, remove_opencode_directory,
                       replace_module_with_directory, replace_module_with_alias,
                       alias_the_clone_root):
            with self.subTest(mutation=mutate.__name__):
                clone, module = self.reset_plugin_fixture()
                self.assertEqual(self.call("plugin", "install", "--source", clone)[0], 0)
                mutate(clone, module)
                code, report = self.call("plugin", "status", "--source", clone)
                self.assertTrue(report["entry"]["owned"], report)
                self.assertIn(report["entry"]["status"], ("owned-link", "broken-link", "other-path"))
                self.assertEqual(code, 0 if report["entry"]["status"] == "owned-link" else 2)
                code, report = self.call("plugin", "uninstall", "--source", clone)
                self.assertEqual(code, 0, report)
                self.assertEqual(report["action"], "uninstalled")
                self.assertFalse(os.path.lexists(self.plugin))
                code, report = self.call("plugin", "install", "--source", clone)
                self.assertEqual(code, 2, report)
                self.assertIn("error", report)
                self.assertFalse(os.path.lexists(self.plugin))

    def test_plugin_link_survives_a_removed_clone_root(self):
        clone, module = self.prepare_plugin()
        self.assertEqual(self.call("plugin", "install", "--source", clone)[0], 0)
        shutil.rmtree(clone)
        code, report = self.call("plugin", "status", "--source", clone)
        self.assertEqual(code, 2)
        self.assertEqual(report["entry"]["status"], "broken-link")
        self.assertTrue(report["entry"]["owned"])
        code, report = self.call("plugin", "install", "--source", clone)
        self.assertEqual(code, 2)
        self.assertIn("existing regular plugin file", report["error"])
        self.assertTrue(os.path.lexists(self.plugin))
        code, report = self.call("plugin", "uninstall", "--source", clone)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["action"], "uninstalled")
        self.assertFalse(os.path.lexists(self.plugin))

    def test_plugin_link_uses_config_dir_home_fallback_and_rejects_bad_sources(self):
        clone, module = self.prepare_plugin()
        env = {**self.env, "OPENCODE_CONFIG_DIR": str(self.root / "custom")}
        code, report = self.call("plugin", "install", "--source", clone, env=env)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["target"], str(self.root / "custom/plugins/agentsmd-project-direction.js"))
        env = dict(self.env)
        del env["XDG_CONFIG_HOME"]
        code, report = self.call("plugin", "install", "--source", clone, env=env)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["target"],
                         str(self.home / ".config/opencode/plugins/agentsmd-project-direction.js"))
        cached = self.root / "plugins/cache/release/opencode/agentsmd-project-direction.js"
        cached.parent.mkdir(parents=True)
        cached.write_text("cached\n")
        for source in (cached, cached.parents[1], self.source, clone / "bin/project-direction"):
            with self.subTest(source=str(source)):
                self.assertEqual(self.call("plugin", "install", "--source", source)[0], 2)
        alias = self.root / "alias/agentsmd-project-direction.js"
        alias.parent.mkdir()
        alias.symlink_to(module)
        code, report = self.call("plugin", "install", "--source", alias)
        self.assertEqual(code, 2)
        self.assertIn("opencode/agentsmd-project-direction.js", report["error"])
        alias_root = self.root / "alias-root"
        alias_root.symlink_to(clone, target_is_directory=True)
        code, report = self.call("plugin", "install", "--source", alias_root)
        self.assertEqual(code, 2, report)
        self.assertIn("symlink alias", report["error"])
        self.assertFalse(os.path.lexists(self.plugin))

    def prepare_run(self, mode="success", help_stream="stdout"):
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "--allow-empty", "-qm", "fixture"], check=True)
        head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("--dangerous-looking literal prompt $(touch never) `echo no`\nReturn a handoff.")
        fake = self.root / "opencode"
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
if sys.argv[1:] == ['--version']:
    print('1.18.29'); sys.exit()
if sys.argv[1:] == ['run', '--help']:
    print('--model --dir --format --auto', file=sys.''' + help_stream + '''); sys.exit()
pathlib.Path('invocation.json').write_text(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}))
mode = ''' + repr(mode) + '''
if mode == 'timeout': time.sleep(30)
if mode == 'failure': sys.exit(7)
if mode == 'invalid': print('not json'); sys.exit()
print(json.dumps({'type': 'text', 'sessionID': '' if mode == 'empty-session' else '   ' if mode == 'blank-session' else 'ses_fixture', 'part': {'text': '   ' if mode == 'blank' else 'Candidate only'}}))
if mode == 'error': print(json.dumps({'type': 'error', 'sessionID': 'ses_fixture'}))
if mode == 'missing-git': pathlib.Path('.git').rename('.git-hidden')
''')
        fake.chmod(0o755)
        self.output = self.root / "receipt"
        self.run_args = ["run", "--cwd", self.repo, "--issue", "https://github.com/toolboxmd/agentsmd/issues/78",
                         "--base", head, "--head", head, "--model", "provider/exact-model", "--permissions", "configured",
                         "--prompt-file", self.prompt, "--output", self.output, "--executable", fake]
        return head

    def test_run_binds_exact_invocation_and_does_not_infer_approval(self):
        head = self.prepare_run()
        code, report = self.call(*self.run_args)
        self.assertEqual(code, 0, report)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["head_before"], head)
        self.assertEqual(receipt["head_after"], head)
        self.assertEqual(receipt["base"], head)
        self.assertEqual(receipt["session_ids"], ["ses_fixture"])
        self.assertEqual(receipt["model"], "provider/exact-model")
        self.assertEqual(receipt["exit_status"], 0)
        self.assertFalse(receipt["approval"])
        self.assertFalse(receipt["live_verified"])
        invocation = json.loads((self.repo / "invocation.json").read_text())
        self.assertNotIn("--auto", invocation["argv"])
        self.assertEqual(invocation["argv"][-2], "--")
        self.assertIn(self.prompt.read_text(), invocation["argv"][-1])
        self.assertEqual(invocation["cwd"], str(self.repo))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.call(*self.run_args)[0], 2)

    def test_auto_requires_explicit_selection(self):
        self.prepare_run()
        self.run_args[self.run_args.index("configured")] = "auto"
        self.assertEqual(self.call(*self.run_args)[0], 0)
        self.assertIn("--auto", json.loads((self.repo / "invocation.json").read_text())["argv"])

    def test_run_accepts_supported_help_on_stderr(self):
        self.prepare_run(help_stream="stderr")
        code, report = self.call(*self.run_args)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["result"], "candidate")

    def test_stale_head_refuses_dispatch(self):
        self.prepare_run()
        self.run_args[self.run_args.index("--head") + 1] = "0" * 40
        self.assertEqual(self.call(*self.run_args)[0], 2)
        self.assertFalse((self.repo / "invocation.json").exists())

    def test_failure_receipt(self):
        self.prepare_run("failure")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["exit_status"], 7)

    def test_malformed_event_refuses_candidate(self):
        self.prepare_run("invalid")
        self.assertEqual(self.call(*self.run_args)[0], 2)

    def test_error_event_refuses_candidate(self):
        self.prepare_run("error")
        self.assertEqual(self.call(*self.run_args)[0], 2)

    def test_blank_result_refuses_candidate(self):
        self.prepare_run("blank")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        self.assertEqual(json.loads((self.output / "receipt.json").read_text())["result"], "failed")

    def test_empty_session_refuses_candidate(self):
        self.prepare_run("empty-session")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["session_ids"], [])

    def test_whitespace_session_refuses_candidate(self):
        self.prepare_run("blank-session")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["session_ids"], [])

    def test_unavailable_after_state_refuses_candidate(self):
        self.prepare_run("missing-git")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["exit_status"], 0)
        self.assertIsNone(receipt["head_after"])
        self.assertEqual(receipt["after_state_error"], "git-state-unavailable")

    def test_timeout_preserves_receipt(self):
        self.prepare_run("timeout")
        self.assertEqual(self.call(*self.run_args, "--timeout", "1")[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "timeout")
        self.assertEqual(receipt["exit_status"], 124)


if __name__ == "__main__":
    unittest.main()
