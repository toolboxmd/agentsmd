"""Strict, race-aware tree manifests and safe ``git archive`` extraction.

This module deliberately does not invoke Git.  Callers provide a directory to
manifest or the bytes produced by a trusted ``git archive`` invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Final, Iterable


DEFAULT_MAX_FILE_SIZE: Final = 64 * 1024 * 1024
DEFAULT_MAX_TOTAL_SIZE: Final = 512 * 1024 * 1024
DEFAULT_MAX_ENTRIES: Final = 100_000
DEFAULT_MAX_DEPTH: Final = 64
DEFAULT_MAX_DIRECTORY_ENTRIES: Final = 10_000
DEFAULT_MAX_ARCHIVE_SIZE: Final = 512 * 1024 * 1024
_READ_SIZE: Final = 1024 * 1024


class TreeManifestError(RuntimeError):
    """Base class for rejected trees and archives."""


class UnsafeTreeError(TreeManifestError):
    """The tree contains an unsafe path or file type, or changed while read."""


class TreeLimitError(TreeManifestError):
    """A configured file, entry, archive, or aggregate-size limit was exceeded."""


class UnsafeArchiveError(TreeManifestError):
    """The archive or extraction destination is unsafe."""


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One regular file or directory in a canonical tree manifest."""

    path: str
    kind: str
    mode: int
    size: int
    sha256: str | None

    def as_dict(self) -> dict[str, object]:
        """Return the stable JSON representation used by :class:`TreeManifest`."""

        value: dict[str, object] = {
            "kind": self.kind,
            "mode": self.mode,
            "path": self.path,
        }
        if self.kind == "file":
            value["sha256"] = self.sha256
            value["size"] = self.size
        return value


@dataclass(frozen=True, slots=True)
class TreeManifest:
    """A sorted tree manifest and the SHA-256 of its canonical JSON."""

    entries: tuple[ManifestEntry, ...]
    total_bytes: int
    sha256: str

    def canonical_bytes(self) -> bytes:
        """Return the exact bytes covered by ``sha256``."""

        payload = {
            "entries": [entry.as_dict() for entry in self.entries],
            "schema_version": 2,
            "total_bytes": self.total_bytes,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def as_dict(self) -> dict[str, object]:
        """Return the public manifest representation, including its digest."""

        return {
            "entries": [entry.as_dict() for entry in self.entries],
            "sha256": self.sha256,
            "total_bytes": self.total_bytes,
        }


@dataclass(frozen=True, slots=True)
class _ArchiveMember:
    member: tarfile.TarInfo
    parts: tuple[str, ...]
    is_directory: bool
    mode: int


def _open_flags(*, directory: bool = False) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    return flags


def _display(parts: Iterable[str]) -> str:
    rendered = "/".join(parts)
    return rendered or "."


def _validate_component(name: str, *, archive: bool = False) -> None:
    label = "archive path" if archive else "tree path"
    if name in {"", ".", ".."}:
        raise UnsafeTreeError(f"{label} has an unsafe component: {name!r}")
    if name in {".git", "__pycache__"} or name.endswith(".pyc"):
        raise UnsafeTreeError(f"{label} contains forbidden runtime or Git metadata")
    if "/" in name or "\\" in name or "\x00" in name:
        raise UnsafeTreeError(f"{label} has an invalid component: {name!r}")
    try:
        name.encode("utf-8")
    except UnicodeEncodeError as error:
        raise UnsafeTreeError(f"{label} is not valid UTF-8: {name!r}") from error


def _same_identity(before: os.stat_result, after: os.stat_result) -> bool:
    return before.st_dev == after.st_dev and before.st_ino == after.st_ino


def _same_directory_state(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        _same_identity(before, after)
        and stat.S_ISDIR(after.st_mode)
        and before.st_mode == after.st_mode
        and before.st_nlink == after.st_nlink
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ctime_ns == after.st_ctime_ns
    )


def _normalized_mode(mode: int) -> int:
    """Return only permission bits, independent of filesystem file-type bits."""

    return stat.S_IMODE(mode) & 0o777


def _hash_regular_file(
    parent_fd: int,
    name: str,
    before: os.stat_result,
    parts: tuple[str, ...],
    *,
    max_file_size: int,
    remaining_total: int,
) -> tuple[str, int]:
    path = _display(parts)
    if before.st_nlink != 1:
        raise UnsafeTreeError(f"regular file has {before.st_nlink} links: {path}")
    if before.st_size < 0 or before.st_size > max_file_size:
        raise TreeLimitError(
            f"file size {before.st_size} exceeds limit {max_file_size}: {path}"
        )
    if before.st_size > remaining_total:
        raise TreeLimitError(f"tree size exceeds aggregate limit at: {path}")

    try:
        file_fd = os.open(name, _open_flags(), dir_fd=parent_fd)
    except OSError as error:
        raise UnsafeTreeError(f"cannot safely open regular file: {path}: {error}") from error

    digest = hashlib.sha256()
    observed_size = 0
    try:
        opened = os.fstat(file_fd)
        if (
            not _same_identity(before, opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_mode != before.st_mode
            or opened.st_size != before.st_size
        ):
            raise UnsafeTreeError(f"file identity or metadata changed before read: {path}")

        while True:
            chunk = os.read(file_fd, _READ_SIZE)
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > max_file_size or observed_size > remaining_total:
                raise TreeLimitError(f"file or aggregate size limit exceeded while reading: {path}")
            digest.update(chunk)

        finished = os.fstat(file_fd)
        if (
            not _same_identity(opened, finished)
            or not stat.S_ISREG(finished.st_mode)
            or finished.st_nlink != 1
            or finished.st_mode != opened.st_mode
            or finished.st_size != opened.st_size
            or observed_size != opened.st_size
            or finished.st_mtime_ns != opened.st_mtime_ns
            or finished.st_ctime_ns != opened.st_ctime_ns
        ):
            raise UnsafeTreeError(f"file changed while it was being hashed: {path}")
    finally:
        os.close(file_fd)

    return digest.hexdigest(), observed_size


def _build_tree_manifest(
    root: str | os.PathLike[str],
    *,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_directory_entries: int = DEFAULT_MAX_DIRECTORY_ENTRIES,
) -> TreeManifest:
    """Build a canonical manifest without following any path below ``root``.

    Only directories and single-link regular files are accepted.  Every entry
    is bound into the manifest.  Directories record their relative POSIX path
    and normalized permission mode; regular files also record byte size and a
    content SHA-256.
    """

    if min(max_file_size, max_total_size, max_entries, max_depth, max_directory_entries) < 0:
        raise ValueError("manifest limits must be non-negative")

    root_path = os.path.abspath(os.fspath(root))
    try:
        root_before = os.lstat(root_path)
    except OSError as error:
        raise UnsafeTreeError(f"cannot lstat manifest root {root_path!r}: {error}") from error
    if not stat.S_ISDIR(root_before.st_mode):
        raise UnsafeTreeError(f"manifest root is not a real directory: {root_path!r}")

    try:
        root_fd = os.open(root_path, _open_flags(directory=True))
    except OSError as error:
        raise UnsafeTreeError(f"cannot safely open manifest root {root_path!r}: {error}") from error

    try:
        return _build_tree_manifest_from_fd(
            root_fd,
            max_file_size=max_file_size,
            max_total_size=max_total_size,
            max_entries=max_entries,
            max_depth=max_depth,
            max_directory_entries=max_directory_entries,
            expected_root=root_before,
        )
    finally:
        os.close(root_fd)


def _build_tree_manifest_from_fd(
    root_fd: int,
    *,
    max_file_size: int,
    max_total_size: int,
    max_entries: int,
    max_depth: int,
    max_directory_entries: int,
    expected_root: os.stat_result | None = None,
) -> TreeManifest:
    """Manifest the directory held by ``root_fd`` without reopening its path."""

    entries: list[ManifestEntry] = []
    total_size = 0

    def walk(directory_fd: int, parts: tuple[str, ...]) -> None:
        nonlocal total_size
        directory_before = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_before.st_mode):
            raise UnsafeTreeError(f"opened path is no longer a directory: {_display(parts)}")

        try:
            discovered: list[os.DirEntry[str]] = []
            with os.scandir(directory_fd) as scanned:
                for item in scanned:
                    if len(discovered) >= max_directory_entries:
                        raise TreeLimitError(
                            "directory has more than "
                            f"{max_directory_entries} entries: {_display(parts)}"
                        )
                    discovered.append(item)
        except OSError as error:
            raise UnsafeTreeError(f"cannot scan directory {_display(parts)}: {error}") from error
        after_scan = os.fstat(directory_fd)
        if not _same_directory_state(directory_before, after_scan):
            raise UnsafeTreeError(f"directory changed while it was scanned: {_display(parts)}")

        for item in sorted(discovered, key=lambda value: value.name):
            _validate_component(item.name)
            child_parts = (*parts, item.name)
            child_path = _display(child_parts)
            if len(child_parts) > max_depth:
                raise TreeLimitError(f"tree exceeds maximum depth {max_depth}: {child_path}")
            if len(entries) >= max_entries:
                raise TreeLimitError(f"tree has more than {max_entries} entries")
            try:
                child_before = item.stat(follow_symlinks=False)
            except OSError as error:
                raise UnsafeTreeError(f"cannot lstat tree entry {child_path}: {error}") from error

            if stat.S_ISLNK(child_before.st_mode):
                raise UnsafeTreeError(f"symbolic link is forbidden: {child_path}")
            if stat.S_ISDIR(child_before.st_mode):
                try:
                    child_fd = os.open(
                        item.name,
                        _open_flags(directory=True),
                        dir_fd=directory_fd,
                    )
                except OSError as error:
                    raise UnsafeTreeError(
                        f"cannot safely open directory {child_path}: {error}"
                    ) from error
                try:
                    child_opened = os.fstat(child_fd)
                    if not _same_identity(child_before, child_opened) or not stat.S_ISDIR(
                        child_opened.st_mode
                    ):
                        raise UnsafeTreeError(
                            f"directory identity changed before open: {child_path}"
                        )
                    entries.append(
                        ManifestEntry(
                            path=child_path,
                            kind="directory",
                            mode=_normalized_mode(child_opened.st_mode),
                            size=0,
                            sha256=None,
                        )
                    )
                    walk(child_fd, child_parts)
                    child_finished = os.fstat(child_fd)
                    if not _same_directory_state(child_opened, child_finished):
                        raise UnsafeTreeError(f"directory changed while traversed: {child_path}")
                finally:
                    os.close(child_fd)
                continue
            if stat.S_ISREG(child_before.st_mode):
                file_sha256, file_size = _hash_regular_file(
                    directory_fd,
                    item.name,
                    child_before,
                    child_parts,
                    max_file_size=max_file_size,
                    remaining_total=max_total_size - total_size,
                )
                total_size += file_size
                entries.append(
                    ManifestEntry(
                        path=child_path,
                        kind="file",
                        mode=_normalized_mode(child_before.st_mode),
                        size=file_size,
                        sha256=file_sha256,
                    )
                )
                continue
            raise UnsafeTreeError(f"special file type is forbidden: {child_path}")

        directory_finished = os.fstat(directory_fd)
        if not _same_directory_state(directory_before, directory_finished):
            raise UnsafeTreeError(f"directory changed while traversed: {_display(parts)}")

    root_opened = os.fstat(root_fd)
    if (
        expected_root is not None
        and not _same_identity(expected_root, root_opened)
    ) or not stat.S_ISDIR(root_opened.st_mode):
        raise UnsafeTreeError("manifest root identity changed before open")
    walk(root_fd, ())
    root_finished = os.fstat(root_fd)
    if not _same_directory_state(root_opened, root_finished):
        raise UnsafeTreeError("manifest root changed while traversed")

    sorted_entries = tuple(sorted(entries, key=lambda entry: entry.path))
    provisional = TreeManifest(entries=sorted_entries, total_bytes=total_size, sha256="")
    canonical_sha256 = hashlib.sha256(provisional.canonical_bytes()).hexdigest()
    return TreeManifest(
        entries=sorted_entries,
        total_bytes=total_size,
        sha256=canonical_sha256,
    )


def build_tree_manifest(
    root: Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_SIZE,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_SIZE,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_directory_entries: int = DEFAULT_MAX_DIRECTORY_ENTRIES,
) -> dict[str, object]:
    """Return a plain canonical manifest dictionary for ``root``.

    ``sha256`` covers canonical JSON containing the entries, ``total_bytes``,
    and the manifest schema version.  It does not cover the digest itself.
    """

    manifest = _build_tree_manifest(
        root,
        max_file_size=max_file_bytes,
        max_total_size=max_total_bytes,
        max_entries=max_entries,
        max_depth=max_depth,
        max_directory_entries=max_directory_entries,
    )
    return manifest.as_dict()


def _archive_parts(name: str) -> tuple[str, ...]:
    if not name or name.startswith("/") or "\x00" in name:
        raise UnsafeArchiveError(f"archive has an unsafe path: {name!r}")
    stripped = name[:-1] if name.endswith("/") else name
    raw_parts = stripped.split("/")
    if not stripped or any(part in {"", ".", ".."} for part in raw_parts):
        raise UnsafeArchiveError(f"archive has an unsafe path: {name!r}")
    try:
        for part in raw_parts:
            _validate_component(part, archive=True)
    except UnsafeTreeError as error:
        raise UnsafeArchiveError(str(error)) from error
    return tuple(raw_parts)


def _validated_archive_members(
    archive: tarfile.TarFile,
    *,
    max_file_size: int,
    max_total_size: int,
    max_entries: int,
    max_depth: int,
    max_directory_entries: int,
) -> list[_ArchiveMember]:
    validated: list[_ArchiveMember] = []
    path_types: dict[tuple[str, ...], bool] = {}
    explicit_paths: set[tuple[str, ...]] = set()
    directory_children: dict[tuple[str, ...], set[str]] = {}
    total_size = 0

    for member in archive:
        parts = _archive_parts(member.name)
        if len(parts) > max_depth:
            raise TreeLimitError(
                f"archive exceeds maximum depth {max_depth}: {_display(parts)}"
            )
        if parts in explicit_paths:
            raise UnsafeArchiveError(f"archive path occurs more than once: {_display(parts)}")
        if member.mode & ~0o777:
            raise UnsafeArchiveError(
                f"archive member has special permission bits: {_display(parts)}"
            )
        mode = member.mode & 0o777
        if member.isdir():
            is_directory = True
            if mode & 0o500 != 0o500:
                raise UnsafeArchiveError(
                    f"archive directory is not owner-readable and searchable: {_display(parts)}"
                )
        elif member.isfile():
            is_directory = False
            if mode & 0o400 == 0:
                raise UnsafeArchiveError(
                    f"archive regular file is not owner-readable: {_display(parts)}"
                )
            if member.size < 0 or member.size > max_file_size:
                raise TreeLimitError(
                    "archive file size "
                    f"{member.size} exceeds limit {max_file_size}: {_display(parts)}"
                )
            total_size += member.size
            if total_size > max_total_size:
                raise TreeLimitError("archive contents exceed aggregate size limit")
        else:
            raise UnsafeArchiveError(
                f"archive link or special member is forbidden: {_display(parts)}"
            )

        for length in range(1, len(parts) + 1):
            prefix = parts[:length]
            expected_directory = length < len(parts) or is_directory
            existing = path_types.get(prefix)
            if existing is None:
                if len(path_types) >= max_entries:
                    raise TreeLimitError(f"archive has more than {max_entries} entries")
                path_types[prefix] = expected_directory
            elif existing != expected_directory:
                raise UnsafeArchiveError(
                    f"archive places a path below regular file: {_display(prefix)}"
                )

            parent = prefix[:-1]
            children = directory_children.setdefault(parent, set())
            child_name = prefix[-1]
            if child_name not in children:
                if len(children) >= max_directory_entries:
                    raise TreeLimitError(
                        "archive directory has more than "
                        f"{max_directory_entries} entries: {_display(parent)}"
                    )
                children.add(child_name)

        explicit_paths.add(parts)
        validated.append(
            _ArchiveMember(
                member=member,
                parts=parts,
                is_directory=is_directory,
                mode=mode,
            )
        )

    return validated


def _open_or_create_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    except OSError as error:
        raise UnsafeArchiveError(f"cannot create extraction directory {name!r}: {error}") from error
    try:
        directory_fd = os.open(name, _open_flags(directory=True), dir_fd=parent_fd)
    except OSError as error:
        raise UnsafeArchiveError(
            f"cannot safely open extraction directory {name!r}: {error}"
        ) from error
    opened = os.fstat(directory_fd)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(directory_fd)
        raise UnsafeArchiveError(f"extraction path is not a real directory: {name!r}")
    try:
        os.fchmod(directory_fd, 0o700)
    except OSError as error:
        os.close(directory_fd)
        raise UnsafeArchiveError(f"cannot secure extraction directory {name!r}: {error}") from error
    return directory_fd


def _open_parent_directory(root_fd: int, parts: tuple[str, ...]) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = _open_or_create_directory(current_fd, part)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def extract_git_archive(
    archive_bytes: bytes | bytearray | memoryview,
    destination: str | os.PathLike[str],
    *,
    max_archive_size: int = DEFAULT_MAX_ARCHIVE_SIZE,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_directory_entries: int = DEFAULT_MAX_DIRECTORY_ENTRIES,
) -> TreeManifest:
    """Safely extract trusted ``git archive`` tar bytes into an empty directory.

    Archive metadata is validated completely before any member is written.
    Only regular files and directories are accepted.  The returned manifest is
    computed from the extracted destination with the same content limits.
    """

    if any(
        limit < 0
        for limit in (
            max_archive_size,
            max_file_size,
            max_total_size,
            max_entries,
            max_depth,
            max_directory_entries,
        )
    ):
        raise ValueError("archive limits must be non-negative")
    raw_archive = bytes(archive_bytes)
    if len(raw_archive) > max_archive_size:
        raise TreeLimitError(
            f"archive size {len(raw_archive)} exceeds limit {max_archive_size}"
        )

    destination_path = os.path.abspath(os.fspath(destination))
    try:
        destination_before = os.lstat(destination_path)
    except OSError as error:
        raise UnsafeArchiveError(
            f"extraction destination must be an existing empty directory: {destination_path!r}"
        ) from error
    if not stat.S_ISDIR(destination_before.st_mode):
        raise UnsafeArchiveError("extraction destination is not a real directory")
    try:
        destination_fd = os.open(destination_path, _open_flags(directory=True))
    except OSError as error:
        raise UnsafeArchiveError(f"cannot safely open extraction destination: {error}") from error

    try:
        destination_opened = os.fstat(destination_fd)
        if not _same_identity(destination_before, destination_opened):
            raise UnsafeArchiveError("extraction destination identity changed before open")
        if list(os.scandir(destination_fd)):
            raise UnsafeArchiveError("extraction destination is not empty")

        try:
            archive = tarfile.open(fileobj=io.BytesIO(raw_archive), mode="r:*")
        except (tarfile.TarError, OSError) as error:
            raise UnsafeArchiveError(f"cannot read tar archive: {error}") from error

        with archive:
            members = _validated_archive_members(
                archive,
                max_file_size=max_file_size,
                max_total_size=max_total_size,
                max_entries=max_entries,
                max_depth=max_depth,
                max_directory_entries=max_directory_entries,
            )
            directory_modes: dict[tuple[str, ...], int] = {}

            for record in members:
                if record.is_directory:
                    directory_fd = _open_parent_directory(destination_fd, record.parts)
                    os.close(directory_fd)
                    directory_modes[record.parts] = record.mode
                    continue

                parent_fd = _open_parent_directory(destination_fd, record.parts[:-1])
                file_fd: int | None = None
                try:
                    flags = (
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NOFOLLOW", 0)
                    )
                    try:
                        file_fd = os.open(record.parts[-1], flags, 0o600, dir_fd=parent_fd)
                    except OSError as error:
                        raise UnsafeArchiveError(
                            f"cannot create archive file {_display(record.parts)}: {error}"
                        ) from error

                    source = archive.extractfile(record.member)
                    if source is None:
                        raise UnsafeArchiveError(
                            f"archive regular file has no readable body: {_display(record.parts)}"
                        )
                    with source:
                        remaining = record.member.size
                        while remaining:
                            chunk = source.read(min(_READ_SIZE, remaining))
                            if not chunk:
                                raise UnsafeArchiveError(
                                    f"archive file is truncated: {_display(record.parts)}"
                                )
                            view = memoryview(chunk)
                            while view:
                                written = os.write(file_fd, view)
                                if written <= 0:
                                    raise UnsafeArchiveError(
                                        f"short write extracting: {_display(record.parts)}"
                                    )
                                view = view[written:]
                            remaining -= len(chunk)

                    written_state = os.fstat(file_fd)
                    if (
                        not stat.S_ISREG(written_state.st_mode)
                        or written_state.st_nlink != 1
                        or written_state.st_size != record.member.size
                    ):
                        raise UnsafeArchiveError(
                            f"extracted file identity or size is unsafe: {_display(record.parts)}"
                        )
                    os.fchmod(file_fd, record.mode)
                finally:
                    if file_fd is not None:
                        os.close(file_fd)
                    os.close(parent_fd)

            for parts, mode in sorted(
                directory_modes.items(), key=lambda item: len(item[0]), reverse=True
            ):
                directory_fd = _open_parent_directory(destination_fd, parts)
                try:
                    os.fchmod(directory_fd, mode)
                finally:
                    os.close(directory_fd)
            manifest = _build_tree_manifest_from_fd(
                destination_fd,
                max_file_size=max_file_size,
                max_total_size=max_total_size,
                max_entries=max_entries,
                max_depth=max_depth,
                max_directory_entries=max_directory_entries,
                expected_root=destination_opened,
            )
            try:
                destination_finished = os.lstat(destination_path)
            except OSError as error:
                raise UnsafeArchiveError(
                    "extraction destination disappeared before return"
                ) from error
            if not stat.S_ISDIR(destination_finished.st_mode) or not _same_identity(
                destination_opened, destination_finished
            ):
                raise UnsafeArchiveError(
                    "extraction destination identity changed before return"
                )
            return manifest
    finally:
        os.close(destination_fd)


def safe_extract_tar(tar_bytes: bytes, destination: Path) -> TreeManifest:
    """Extract and manifest validated ``git archive`` bytes."""

    return extract_git_archive(tar_bytes, destination)


__all__ = [
    "DEFAULT_MAX_ARCHIVE_SIZE",
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_DIRECTORY_ENTRIES",
    "DEFAULT_MAX_FILE_SIZE",
    "DEFAULT_MAX_TOTAL_SIZE",
    "ManifestEntry",
    "TreeLimitError",
    "TreeManifest",
    "TreeManifestError",
    "UnsafeArchiveError",
    "UnsafeTreeError",
    "build_tree_manifest",
    "extract_git_archive",
    "safe_extract_tar",
]
