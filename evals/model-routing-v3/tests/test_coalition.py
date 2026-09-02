from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coalition import (  # noqa: E402
    COALITION_TYPE_JETSAM,
    CoalitionError,
    MacOSCoalitionInspector,
)


@unittest.skipUnless(sys.platform == "darwin", "Darwin coalition ABI is required")
class CoalitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inspector = MacOSCoalitionInspector()

    def test_self_has_two_positive_coalition_ids(self) -> None:
        ids = self.inspector.coalition_for_pid(os.getpid())
        self.assertIsNotNone(ids)
        assert ids is not None
        self.assertGreater(ids.resource, 0)
        self.assertGreater(ids.jetsam, 0)
        self.assertFalse(self.inspector.resource_coalition_reaped(ids.resource))
        self.assertIn(
            ids.jetsam,
            self.inspector.coalition_ids(COALITION_TYPE_JETSAM),
        )

    def test_missing_pid_and_reaped_ids_have_exact_results(self) -> None:
        missing_pid = 2**30
        self.assertIsNone(
            self.inspector.coalition_for_pid(missing_pid, allow_missing=True)
        )
        missing_coalition = 2**63
        self.assertTrue(
            self.inspector.resource_coalition_reaped(missing_coalition)
        )
        self.assertTrue(
            self.inspector.jetsam_coalition_absent(missing_coalition)
        )

    def test_invalid_ids_fail_closed(self) -> None:
        with self.assertRaises(CoalitionError):
            self.inspector.coalition_for_pid(0)
        with self.assertRaises(CoalitionError):
            self.inspector.resource_coalition_reaped(0)
        with self.assertRaises(CoalitionError):
            self.inspector.jetsam_coalition_absent(0)


if __name__ == "__main__":
    unittest.main()
