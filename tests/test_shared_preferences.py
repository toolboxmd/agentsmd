"""Public installer, hook and archive regressions for shared private defaults."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SharedPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.source = self.root / 'stable/AGENTS.md'
        self.source.parent.mkdir()
        self.source.write_text('# Shared contract\n')
        self.example = self.source.with_name('PREFERENCES.example.md')
        self.example.write_text('# Generic preferences\n')
        self.private = self.source.with_name('PREFERENCES.md')
        self.project = self.root / 'unrelated'
        self.project.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if key not in {'AGENTSMD_HOST', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'OPENCODE_CONFIG_DIR',
                                   'XDG_CONFIG_HOME', 'PLUGIN_DATA', 'CLAUDE_PLUGIN_DATA', 'GROK_PLUGIN_DATA'}}
        self.env.update(HOME=str(self.home), AGENTSMD_PROJECT_DIRECTION_DATA=str(self.root / 'cache'))

    def command(self, executable, *args, input=None, env=None, expected=0):
        result = subprocess.run([str(ROOT / 'bin' / executable), *map(str, args)],
                                cwd=self.project, env=env or self.env,
                                input=json.dumps(input) if input is not None else None,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.stdout else None

    def install(self, host='codex', **kwargs):
        return self.command('agentsmd-global-instructions', 'install', '--host', host,
                            '--source', self.source, **kwargs)

    def hook(self, event='UserPromptSubmit', **kwargs):
        output = self.command('project-direction', 'hook', input={
            'session_id': 'same-session', 'cwd': str(self.project),
            'hook_event_name': event, **kwargs})
        if output is None:
            return None
        return json.loads(output['hookSpecificOutput']['additionalContext'].splitlines()[1])

    def test_four_native_targets_initialize_once_and_preserve_preferences(self):
        locations = {'codex': '.codex/AGENTS.md', 'grok': '.grok/AGENTS.md',
                     'opencode': '.config/opencode/AGENTS.md', 'claude': '.claude/CLAUDE.md'}
        for index, (host, relative) in enumerate(locations.items()):
            with self.subTest(host=host):
                report = self.install(host)
                self.assertEqual(Path(report['target']), self.home / relative)
                self.assertEqual((self.home / relative).resolve(), self.source)
                self.assertEqual(report['source_sha256'], report['target_sha256'])
                self.assertEqual(report['preferences']['action'], 'created' if index == 0 else 'preserved')
                self.private.write_text('personal unchanged\n')
                self.assertEqual(self.install(host)['action'], 'unchanged')
                self.assertEqual(self.private.read_text(), 'personal unchanged\n')

    def test_config_roots_and_opencode_lifecycle_share_path(self):
        for host, key, relative in (('codex', 'CODEX_HOME', 'AGENTS.md'),
                                    ('claude', 'CLAUDE_CONFIG_DIR', 'CLAUDE.md'),
                                    ('opencode', 'XDG_CONFIG_HOME', 'opencode/AGENTS.md'),
                                    ('opencode', 'OPENCODE_CONFIG_DIR', 'AGENTS.md')):
            with self.subTest(key=key):
                env = {**self.env, key: str(self.root / key)}
                report = self.install(host, env=env)
                self.assertEqual(Path(report['target']), self.root / key / relative)
                if host == 'opencode':
                    status = self.command('agentsmd-opencode', 'status', '--source', self.source, env=env)
                    self.assertEqual(status['status'], 'owned-link')
                    self.command('agentsmd-opencode', 'uninstall', '--source', self.source, env=env)
                    self.assertFalse(Path(report['target']).exists())
                    self.assertTrue(self.private.exists())

    def test_native_and_compatibility_paths_coexist_without_mutating_project_rules(self):
        project_rules = {'AGENTS.md': 'project native', 'CLAUDE.md': 'project fallback',
                         'opencode.json': '{"instructions":["extra.md"]}', 'extra.md': 'extra project rules'}
        for name, content in project_rules.items():
            (self.project / name).write_text(content)
        for host in ('claude', 'grok', 'opencode', 'codex'):
            self.install(host)
        for host in ('claude', 'grok', 'opencode', 'codex'):
            report = self.command('project-direction', 'inspect', '--host', host)
            self.assertEqual(report['instructions']['resolved_target'], str(self.source))
            self.assertEqual(report['preferences']['content'], self.private.read_text())
        for name, content in project_rules.items():
            self.assertEqual((self.project / name).read_text(), content)

    def test_source_comparison_distinguishes_divergent_identical_bytes(self):
        self.install()
        other = self.root / 'other/AGENTS.md'
        other.parent.mkdir()
        other.write_bytes(self.source.read_bytes())
        report = self.command('agentsmd-global-instructions', 'inspect', '--source', other, expected=2)
        self.assertEqual(report['status'], 'divergent-link')

    def test_all_hosts_preserve_conflicts_and_backup_authorized_replacement(self):
        for host, relative in (('codex', '.codex/AGENTS.md'), ('grok', '.grok/AGENTS.md'),
                               ('opencode', '.config/opencode/AGENTS.md'), ('claude', '.claude/CLAUDE.md')):
            target = self.home / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('user-owned original')
            self.install(host, expected=2)
            self.assertEqual(target.read_text(), 'user-owned original')
            result = self.command('agentsmd-global-instructions', 'install', '--host', host,
                                  '--source', self.source, '--replace')
            self.assertEqual(Path(result['backup']).read_text(), 'user-owned original')
            self.assertEqual(target.resolve(), self.source)

    def test_outside_git_refreshes_and_discards_without_project_substitution(self):
        self.install()
        (self.project / 'PREFERENCES.md').write_text('WRONG PROJECT CONTENT')
        first = self.hook('SessionStart')
        self.assertEqual(first['status'], 'not_in_repository')
        self.assertEqual(first['preferences']['content'], self.example.read_text())
        self.assertIsNone(self.hook())
        self.private.write_text('changed private preferences\n')
        self.assertEqual(self.hook()['preferences']['content'], self.private.read_text())
        self.assertIsNone(self.hook())
        self.private.unlink()
        removed = self.hook()['preferences']
        self.assertEqual(removed['status'], 'absent')
        self.assertIn('discard', removed['action'])
        self.assertNotIn('content', removed)
        self.assertIsNone(self.hook())

    def test_source_change_worker_and_restore_refresh_without_reinjecting_core(self):
        self.install()
        original = self.hook('SessionStart')
        for event in ('SubagentStart', 'SessionStart'):
            payload = self.hook(event, source='compact')
            self.assertEqual(payload['preferences']['content'], self.private.read_text())
            self.assertNotIn('content', payload['instructions'])
            self.assertIn('freshness', payload['instructions']['action'])
        self.source.write_text('# New shared contract\n')
        changed = self.hook()
        self.assertNotEqual(original['instructions']['sha256'], changed['instructions']['sha256'])
        self.assertEqual(changed['instructions']['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertIsNone(self.hook())
        other = self.root / 'new-source'
        other.mkdir()
        (other / 'AGENTS.md').write_bytes(self.source.read_bytes())
        (other / 'PREFERENCES.md').write_text('new source defaults')
        target = self.home / '.codex/AGENTS.md'
        target.unlink()
        target.symlink_to(other / 'AGENTS.md')
        self.assertEqual(self.hook()['preferences']['content'], 'new source defaults')

    def test_plugin_cache_invocation_resolves_native_link_not_cached_example(self):
        self.install()
        cache = self.root / 'plugins/cache/agentsmd/1/bin'
        cache.mkdir(parents=True)
        for name in ('project-direction', 'agentsmd_instructions.py'):
            shutil.copy2(ROOT / 'bin' / name, cache / name)
        (cache.parent / 'PREFERENCES.md').write_text('WRONG CACHE CONTENT')
        result = subprocess.run([str(cache / 'project-direction'), 'inspect'], env=self.env,
                                cwd=self.project, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['preferences']['content'], self.private.read_text())

    def test_preferences_never_silently_truncated_or_replaced_by_example(self):
        self.install()
        for raw, status in ((b'x' * 8192, 'ready'), (b'x' * 8193, 'oversized'), (b'\xff', 'unreadable')):
            self.private.write_bytes(raw)
            payload = self.hook('SessionStart')['preferences']
            self.assertEqual(payload['status'], status)
            if status == 'ready':
                self.assertEqual(payload['content'].encode(), raw)
            else:
                self.assertNotIn('content', payload)
        self.private.unlink()
        self.private.mkdir()
        self.assertEqual(self.hook('SessionStart')['preferences']['status'], 'unreadable')
        self.assertEqual(self.install()['preferences']['action'], 'preserved')

    def test_hook_host_selection_refuses_conflicts_and_honors_explicit_override(self):
        self.install()
        other = self.root / 'other-host'
        other.mkdir()
        (other / 'AGENTS.md').write_text('different host source')
        (other / 'PREFERENCES.md').write_text('other host preferences')
        target = self.home / '.claude/CLAUDE.md'
        target.parent.mkdir()
        target.symlink_to(other / 'AGENTS.md')
        blocked = self.hook('SessionStart')
        self.assertEqual(blocked['instructions']['status'], 'source-ambiguous')
        self.assertNotIn('content', blocked['preferences'])
        self.env['AGENTSMD_HOST'] = 'claude'
        self.assertEqual(self.hook('SessionStart')['preferences']['content'], 'other host preferences')
        selected = self.command('project-direction', 'inspect', '--host', 'codex')
        self.assertEqual(selected['preferences']['content'], self.private.read_text())
        self.env['AGENTSMD_HOST'] = 'invalid'
        self.command('project-direction', 'inspect', expected=2)

    def test_serialized_budget_requires_full_read_without_partial_contents(self):
        self.install()
        subprocess.run(['git', 'init', '--quiet', str(self.project)], check=True)
        for name in ('VISION.md', 'MISSION.md', 'OBJECTIVE.md'):
            (self.project / name).write_text('# Direction\n' + 'x' * 3000)
        # Escaping each control byte expands JSON beyond the inline allowance.
        self.private.write_text('\x01' * 8192)
        payload = self.hook('SessionStart')
        self.assertEqual(payload['status'], 'read_required')
        self.assertEqual(payload['loaded_status'], 'ready')
        self.assertEqual(payload['preferences']['status'], 'read_required')
        self.assertNotIn('content', payload['preferences'])
        self.assertEqual(len(payload['files']), 3)
        for item in payload['files']:
            self.assertNotIn('content', item)
            self.assertIn('sha256', item)
        self.assertLess(len(json.dumps(payload).encode()), 14000)
        self.assertIsNone(self.hook())
        self.private.write_text('small defaults')
        self.assertEqual(self.hook()['status'], 'ready')

    def test_manual_inspection_uses_selected_host_and_rejects_missing_source(self):
        self.command('project-direction', 'inspect', '--host', 'claude', expected=2)
        self.install('claude')
        self.assertEqual(self.command('project-direction', 'inspect', '--host', 'claude')
                         ['preferences']['content'], self.private.read_text())
        self.assertEqual(self.hook('SessionStart')['preferences']['status'], 'source-unavailable')

    def test_archive_ships_example_and_excludes_force_tracked_private_marker(self):
        repo = self.root / 'artifact-fixture'
        repo.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)
        git('init', '--quiet')
        # Build the actual candidate's complete package tree through its release seam.
        inventory = subprocess.check_output(
            ['git', '-C', str(ROOT), 'ls-files'], text=True)
        # Include this component's new files before its coordinator-owned commit.
        # Never sweep unrelated untracked user files into the package fixture.
        package_files = set(inventory.splitlines()) | {
            '.gitattributes', 'PREFERENCES.example.md',
            'bin/agentsmd_instructions.py', 'tests/test_shared_preferences.py'}
        for name in package_files:
            source = ROOT / name
            if source.is_file():
                destination = repo / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        marker = 'PRIVATE-' + hashlib.sha256(str(self.root).encode()).hexdigest()
        (repo / 'PREFERENCES.md').write_text(marker)
        self.assertIn('PREFERENCES.md', git('check-ignore', 'PREFERENCES.md').stdout)
        git('add', '.')
        git('add', '--force', 'PREFERENCES.md')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--quiet', '-m', 'fixture')
        archive = self.root / 'agentsmd-fixture.tar.gz'
        git('archive', '--format=tar.gz', '--prefix=agentsmd/', f'--output={archive}', 'HEAD')
        with tarfile.open(archive) as package:
            for name in ('PREFERENCES.example.md', 'AGENTS.md', 'bin/project-direction',
                         'bin/agentsmd-global-instructions', 'bin/agentsmd_instructions.py'):
                self.assertIn('agentsmd/' + name, package.getnames())
            # Extract only this locally generated trusted fixture, then exercise the shipped CLI.
            package.extractall(self.root / 'unpacked')
            self.assertNotIn('agentsmd/PREFERENCES.md', package.getnames())
            for member in package.getmembers():
                if member.isfile():
                    self.assertNotIn(marker.encode(), package.extractfile(member).read())
        unpacked = self.root / 'unpacked/agentsmd'
        result = subprocess.run(
            [str(unpacked / 'bin/agentsmd-global-instructions'), 'install', '--host', 'claude',
             '--source', str(unpacked / 'AGENTS.md')], env=self.env, cwd=self.project,
            text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['preferences']['action'], 'created')
        self.assertEqual((unpacked / 'PREFERENCES.md').read_bytes(),
                         (unpacked / 'PREFERENCES.example.md').read_bytes())


if __name__ == '__main__':
    unittest.main()
