from __future__ import annotations

import importlib.util
import hashlib
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "model_routing_v2_tree_manifest", ROOT / "tree_manifest.py"
)
assert SPEC and SPEC.loader
tree_manifest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tree_manifest
SPEC.loader.exec_module(tree_manifest)


def archive_with(name: str, payload: bytes, *, kind: bytes = tarfile.REGTYPE) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.mode = 0o644
        member.size = len(payload) if kind == tarfile.REGTYPE else 0
        archive.addfile(member, io.BytesIO(payload) if kind == tarfile.REGTYPE else None)
    return output.getvalue()


def archive_with_members(*members: tuple[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, payload in members:
            member = tarfile.TarInfo(name)
            member.mode = 0o644
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    return output.getvalue()


class TreeManifestTests(unittest.TestCase):
    def test_content_manifest_changes_when_same_path_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "tracked.txt"
            target.write_text("first\n", encoding="utf-8")
            first = tree_manifest.build_tree_manifest(root)
            target.write_text("second\n", encoding="utf-8")
            second = tree_manifest.build_tree_manifest(root)
            self.assertNotEqual(first["sha256"], second["sha256"])
            self.assertEqual(
                [entry["path"] for entry in second["entries"]],
                ["tracked.txt"],
            )

    def test_git_metadata_is_rejected_before_trusted_git_can_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            metadata = root / ".git"
            metadata.mkdir()
            (metadata / "config").write_text(
                "[core]\n\tfsmonitor = malicious-command\n", encoding="utf-8"
            )
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.build_tree_manifest(root)

    def test_symlink_hardlink_and_fifo_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "target"
            target.write_text("data", encoding="utf-8")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.build_tree_manifest(root)
            link.unlink()
            hard = root / "hard"
            os.link(target, hard)
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.build_tree_manifest(root)
            hard.unlink()
            target.unlink()
            fifo = root / "pipe"
            os.mkfifo(fifo)
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.build_tree_manifest(root)

    def test_file_and_total_size_limits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "large").write_bytes(b"12345")
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.build_tree_manifest(root, max_file_bytes=4)
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.build_tree_manifest(root, max_total_bytes=4)

    def test_directories_and_normalized_modes_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            directory = root / "nested"
            directory.mkdir()
            target = directory / "tracked.txt"
            target.write_text("data", encoding="utf-8")
            directory.chmod(0o1751)
            target.chmod(0o640)

            manifest = tree_manifest.build_tree_manifest(root)

            self.assertEqual(
                manifest["entries"],
                [
                    {"kind": "directory", "mode": 0o751, "path": "nested"},
                    {
                        "kind": "file",
                        "mode": 0o640,
                        "path": "nested/tracked.txt",
                        "sha256": hashlib.sha256(b"data").hexdigest(),
                        "size": 4,
                    },
                ],
            )

    def test_every_tree_entry_counts_toward_limits(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "empty").mkdir()
            (root / "file").write_text("x", encoding="utf-8")
            with self.assertRaises(tree_manifest.TreeLimitError):
                tree_manifest.build_tree_manifest(root, max_entries=1)
            with self.assertRaises(tree_manifest.TreeLimitError):
                tree_manifest.build_tree_manifest(root, max_directory_entries=1)

    def test_tree_depth_and_backslash_components_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            nested = root / "first" / "second"
            nested.mkdir(parents=True)
            (nested / "file").write_text("x", encoding="utf-8")
            with self.assertRaises(tree_manifest.TreeLimitError):
                tree_manifest.build_tree_manifest(root, max_depth=2)

            with tempfile.TemporaryDirectory() as backslash_raw:
                backslash_root = Path(backslash_raw)
                (backslash_root / "back\\slash").write_text("x", encoding="utf-8")
                with self.assertRaises(tree_manifest.UnsafeTreeError):
                    tree_manifest.build_tree_manifest(backslash_root)


class ArchiveExtractionTests(unittest.TestCase):
    def test_safe_regular_file_extracts_and_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "tree"
            destination.mkdir()
            manifest = tree_manifest.safe_extract_tar(
                archive_with("nested/file.txt", b"safe\n"), destination
            )
            self.assertEqual(
                [entry.path for entry in manifest.entries],
                ["nested", "nested/file.txt"],
            )

    def test_regular_file_and_child_conflicts_fail_in_both_orders(self) -> None:
        for members in (
            (("blocked", b"file"), ("blocked/child", b"child")),
            (("blocked/child", b"child"), ("blocked", b"file")),
        ):
            with self.subTest(members=members), tempfile.TemporaryDirectory() as raw:
                destination = Path(raw) / "tree"
                destination.mkdir()
                with self.assertRaises(tree_manifest.UnsafeArchiveError):
                    tree_manifest.safe_extract_tar(
                        archive_with_members(*members), destination
                    )

    def test_absolute_parent_git_link_and_special_members_are_rejected(self) -> None:
        cases = {
            "absolute": archive_with("/escape", b"x"),
            "parent": archive_with("../escape", b"x"),
            "backslash": archive_with("back\\slash", b"x"),
            "git": archive_with(".git/config", b"x"),
            "symlink": archive_with("link", b"", kind=tarfile.SYMTYPE),
            "fifo": archive_with("pipe", b"", kind=tarfile.FIFOTYPE),
        }
        for name, archive in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as raw:
                destination = Path(raw) / "tree"
                destination.mkdir()
                with self.assertRaises(tree_manifest.TreeManifestError):
                    tree_manifest.safe_extract_tar(archive, destination)

    def test_archive_limits_cover_implicit_directories_and_directory_children(self) -> None:
        archive = archive_with_members(("first/second/file", b"x"), ("first/other", b"y"))
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "tree"
            destination.mkdir()
            with self.assertRaises(tree_manifest.TreeLimitError):
                tree_manifest.extract_git_archive(archive, destination, max_entries=2)

        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "tree"
            destination.mkdir()
            with self.assertRaises(tree_manifest.TreeLimitError):
                tree_manifest.extract_git_archive(archive, destination, max_depth=2)

        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "tree"
            destination.mkdir()
            with self.assertRaises(tree_manifest.TreeLimitError):
                tree_manifest.extract_git_archive(
                    archive, destination, max_directory_entries=1
                )

    def test_extraction_rejects_destination_rebinding_after_manifest(self) -> None:
        archive = archive_with("safe.txt", b"safe\n")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            destination = root / "tree"
            replacement = root / "replacement"
            destination.mkdir()
            original = tree_manifest._build_tree_manifest_from_fd

            def rename_before_manifest(root_fd: int, **kwargs: object) -> tree_manifest.TreeManifest:
                destination.rename(replacement)
                destination.mkdir()
                (destination / "attacker.txt").write_text("attacker", encoding="utf-8")
                return original(root_fd, **kwargs)

            with mock.patch.object(
                tree_manifest, "_build_tree_manifest_from_fd", side_effect=rename_before_manifest
            ):
                with self.assertRaises(tree_manifest.UnsafeArchiveError):
                    tree_manifest.extract_git_archive(archive, destination)

            self.assertTrue((destination / "attacker.txt").is_file())

    def test_nonempty_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "tree"
            destination.mkdir()
            (destination / "existing").write_text("x", encoding="utf-8")
            with self.assertRaises(tree_manifest.TreeManifestError):
                tree_manifest.safe_extract_tar(
                    archive_with("new", b"x"), destination
                )


if __name__ == "__main__":
    unittest.main()
