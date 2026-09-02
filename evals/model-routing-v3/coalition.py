"""Fail-closed access to macOS process coalition identity and reap state.

The interfaces used here are private Darwin interfaces.  The benchmark pins
their expected ABI at this narrow boundary and refuses to run when the host
does not provide the exact symbols or result sizes.  It does not substitute a
process group, environment marker, or parent-PID walk when coalition evidence
is unavailable.
"""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from dataclasses import asdict, dataclass


PROC_PIDCOALITIONINFO = 20
PROC_PIDCOALITIONINFO_SIZE = 5 * ctypes.sizeof(ctypes.c_uint64)
LISTCOALITIONS_SINGLE_TYPE = 2
COALITION_TYPE_RESOURCE = 0
COALITION_TYPE_JETSAM = 1
PROC_PIDPATHINFO_MAXSIZE = 4 * 1024


class CoalitionError(RuntimeError):
    """The host could not provide exact coalition evidence."""


class _ProcPidCoalitionInfo(ctypes.Structure):
    _fields_ = [
        ("coalition_id", ctypes.c_uint64 * 2),
        ("reserved1", ctypes.c_uint64),
        ("reserved2", ctypes.c_uint64),
        ("reserved3", ctypes.c_uint64),
    ]


class _ProcInfoCoalInfo(ctypes.Structure):
    _fields_ = [
        ("coalition_id", ctypes.c_uint64),
        ("coalition_type", ctypes.c_uint32),
        ("coalition_tasks", ctypes.c_uint32),
    ]


@dataclass(frozen=True)
class CoalitionIds:
    resource: int
    jetsam: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class CoalitionMember:
    pid: int
    coalitions: CoalitionIds

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class MacOSCoalitionInspector:
    """Read coalition membership through libproc and libsystem_kernel."""

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise CoalitionError("macOS coalition evidence is unavailable off Darwin")
        try:
            library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            self._proc_pidinfo = library.proc_pidinfo
            self._proc_listallpids = library.proc_listallpids
            self._proc_pidpath = library.proc_pidpath
            self._proc_listcoalitions = library.proc_listcoalitions
            self._coalition_info_resource_usage = (
                library.coalition_info_resource_usage
            )
        except (AttributeError, OSError) as exc:
            raise CoalitionError(
                "required macOS coalition interfaces are unavailable"
            ) from exc

        self._proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self._proc_pidinfo.restype = ctypes.c_int
        self._proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._proc_listallpids.restype = ctypes.c_int
        self._proc_pidpath.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self._proc_pidpath.restype = ctypes.c_int
        self._proc_listcoalitions.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self._proc_listcoalitions.restype = ctypes.c_int
        self._coalition_info_resource_usage.argtypes = [
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        self._coalition_info_resource_usage.restype = ctypes.c_int

        if ctypes.sizeof(_ProcPidCoalitionInfo) != PROC_PIDCOALITIONINFO_SIZE:
            raise CoalitionError("unexpected proc_pidcoalitioninfo ABI size")
        if ctypes.sizeof(_ProcInfoCoalInfo) != 16:
            raise CoalitionError("unexpected procinfo_coalinfo ABI size")

    def coalition_for_pid(self, pid: int, *, allow_missing: bool = False) -> CoalitionIds | None:
        if pid <= 0:
            raise CoalitionError("coalition PID must be positive")
        value = _ProcPidCoalitionInfo()
        ctypes.set_errno(0)
        result = self._proc_pidinfo(
            pid,
            PROC_PIDCOALITIONINFO,
            0,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
        error = ctypes.get_errno()
        if result == ctypes.sizeof(value):
            if any((value.reserved1, value.reserved2, value.reserved3)):
                raise CoalitionError("proc_pidcoalitioninfo reserved fields are nonzero")
            return CoalitionIds(
                resource=int(value.coalition_id[COALITION_TYPE_RESOURCE]),
                jetsam=int(value.coalition_id[COALITION_TYPE_JETSAM]),
            )
        if result == 0 and error == errno.ESRCH and allow_missing:
            return None
        raise CoalitionError(
            f"proc_pidinfo coalition query failed for PID {pid}: "
            f"result={result} errno={error}"
        )

    def all_pids(self) -> tuple[int, ...]:
        ctypes.set_errno(0)
        suggested = self._proc_listallpids(None, 0)
        error = ctypes.get_errno()
        if suggested < 0 or (suggested == 0 and error):
            raise CoalitionError(
                f"proc_listallpids sizing failed: result={suggested} errno={error}"
            )
        capacity = max(256, suggested + 128)
        for _ in range(4):
            values = (ctypes.c_int * capacity)()
            ctypes.set_errno(0)
            count = self._proc_listallpids(values, ctypes.sizeof(values))
            error = ctypes.get_errno()
            if count < 0 or (count == 0 and error):
                raise CoalitionError(
                    f"proc_listallpids failed: result={count} errno={error}"
                )
            if count < capacity:
                return tuple(sorted({int(pid) for pid in values[:count] if pid > 0}))
            capacity *= 2
        raise CoalitionError("process list did not stabilize within its fixed bound")

    def matching_members(self, expected: CoalitionIds) -> tuple[CoalitionMember, ...]:
        if expected.resource <= 0 or expected.jetsam <= 0:
            raise CoalitionError("expected coalition IDs must both be positive")
        found: list[CoalitionMember] = []
        for pid in self.all_pids():
            ids = self.coalition_for_pid(pid, allow_missing=True)
            if ids is None:
                continue
            if ids.resource == expected.resource or ids.jetsam == expected.jetsam:
                found.append(CoalitionMember(pid=pid, coalitions=ids))
        return tuple(found)

    def executable_path(self, pid: int, *, allow_missing: bool = False) -> str | None:
        buffer = ctypes.create_string_buffer(PROC_PIDPATHINFO_MAXSIZE)
        ctypes.set_errno(0)
        result = self._proc_pidpath(pid, buffer, ctypes.sizeof(buffer))
        error = ctypes.get_errno()
        if result > 0:
            raw = bytes(buffer[:result]).split(b"\0", 1)[0]
            try:
                return os.fsdecode(raw)
            except UnicodeDecodeError as exc:
                raise CoalitionError(
                    f"process path for PID {pid} is not decodable"
                ) from exc
        if result == 0 and error == errno.ESRCH and allow_missing:
            return None
        raise CoalitionError(
            f"proc_pidpath failed for PID {pid}: result={result} errno={error}"
        )

    def resource_coalition_reaped(self, coalition_id: int) -> bool:
        if coalition_id <= 0:
            raise CoalitionError("resource coalition ID must be positive")
        # The current Darwin structure is smaller than this fixed buffer.  The
        # API accepts a caller-provided size and fails closed below if that ABI
        # behavior changes.
        usage = (ctypes.c_uint64 * 64)()
        ctypes.set_errno(0)
        result = self._coalition_info_resource_usage(
            coalition_id, ctypes.byref(usage), ctypes.sizeof(usage)
        )
        error = ctypes.get_errno()
        if result == 0:
            return False
        if result == -1 and error == errno.ESRCH:
            return True
        raise CoalitionError(
            "coalition_info_resource_usage failed without an ESRCH reap proof: "
            f"result={result} errno={error}"
        )

    def coalition_ids(self, coalition_type: int) -> frozenset[int]:
        if coalition_type not in {COALITION_TYPE_RESOURCE, COALITION_TYPE_JETSAM}:
            raise CoalitionError("unsupported coalition type")
        ctypes.set_errno(0)
        needed = self._proc_listcoalitions(
            LISTCOALITIONS_SINGLE_TYPE, coalition_type, None, 0
        )
        error = ctypes.get_errno()
        if needed < 0 or (needed == 0 and error):
            raise CoalitionError(
                f"proc_listcoalitions sizing failed: result={needed} errno={error}"
            )
        capacity = max(64, (needed // ctypes.sizeof(_ProcInfoCoalInfo)) + 64)
        for _ in range(4):
            values = (_ProcInfoCoalInfo * capacity)()
            ctypes.set_errno(0)
            returned = self._proc_listcoalitions(
                LISTCOALITIONS_SINGLE_TYPE,
                coalition_type,
                ctypes.byref(values),
                ctypes.sizeof(values),
            )
            error = ctypes.get_errno()
            if returned < 0 or (returned == 0 and error):
                raise CoalitionError(
                    f"proc_listcoalitions failed: result={returned} errno={error}"
                )
            if returned % ctypes.sizeof(_ProcInfoCoalInfo):
                raise CoalitionError("proc_listcoalitions returned a partial record")
            if returned < ctypes.sizeof(values):
                count = returned // ctypes.sizeof(_ProcInfoCoalInfo)
                result: set[int] = set()
                for item in values[:count]:
                    if int(item.coalition_type) != coalition_type:
                        raise CoalitionError(
                            "proc_listcoalitions returned the wrong coalition type"
                        )
                    if item.coalition_id > 0:
                        result.add(int(item.coalition_id))
                return frozenset(result)
            capacity *= 2
        raise CoalitionError("coalition list did not stabilize within its fixed bound")

    def jetsam_coalition_absent(self, coalition_id: int) -> bool:
        if coalition_id <= 0:
            raise CoalitionError("jetsam coalition ID must be positive")
        return coalition_id not in self.coalition_ids(COALITION_TYPE_JETSAM)
