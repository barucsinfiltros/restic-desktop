import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core import restore_destination as restore


class RestoreDestinationTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent))
        self.root = Path(temp)
        self.target = self.root / "destination"
        self.target.mkdir()

    def test_existing_empty_directory(self):
        with restore.guard_destination(self.target) as (path, identity):
            self.assertEqual(path, self.target)
            self.assertEqual(len(identity), len(path.parts))

    def test_missing_nonempty_and_invalid_paths(self):
        (self.target / "sentinel").touch()
        for bad in (self.root / "missing", self.target, "relative", self.root / "bad\0name"):
            with self.subTest(path=bad), self.assertRaises((OSError, ValueError)):
                with restore.guard_destination(bad):
                    self.fail("Invalid path was accepted")

    def test_uninspectable_component_fails_closed(self):
        helper = "_open_component" if os.name == "nt" else "_posix_identity"
        original = getattr(restore, helper)

        def inspect(path, *args):
            if path == self.root:
                raise PermissionError("simulated inspection denial")
            return original(path, *args)

        with patch.object(restore, helper, side_effect=inspect), self.assertRaises(PermissionError):
            with restore.guard_destination(self.target):
                self.fail("Uninspectable path was accepted")

    def test_symlink_at_leaf_or_parent(self):
        (self.target / "child").mkdir()
        link = self.root / "link"
        try:
            link.symlink_to(self.target, target_is_directory=True)
        except OSError as exc:
            if os.name == "nt" and exc.winerror == 1314:
                self.skipTest("Windows account cannot create directory symlinks (1314).")
            raise
        for path in (link, link / "child"):
            with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                with restore.guard_destination(path):
                    self.fail("Directory symlink was accepted")

    @unittest.skipUnless(os.name == "nt", "Windows junctions require Windows.")
    def test_windows_junction_in_parent(self):
        (self.target / "child").mkdir()
        link = self.root / "junction"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(self.target)],
            capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_junction())
        for path in (link, link / "child"):
            with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                with restore.guard_destination(path):
                    self.fail("Junction was accepted")

    @unittest.skipUnless(os.name == "nt", "Win32 reparse attributes require Windows.")
    def test_windows_rejects_any_reported_reparse_point(self):
        def information(_handle, info):
            info._obj.attributes = stat.FILE_ATTRIBUTE_DIRECTORY | stat.FILE_ATTRIBUTE_REPARSE_POINT
            return True

        with patch.object(restore, "_info", side_effect=information):
            with self.assertRaisesRegex(ValueError, "ordinary directory"):
                with restore.guard_destination(self.target):
                    self.fail("Unknown reparse point was accepted")

    def test_replacement_and_modification_before_launch_are_rejected(self):
        with restore.guard_destination(self.target) as (_, identity):
            pass
        self.target.rename(self.root / "original")
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, "changed after validation"):
            with restore.guard_destination(self.target, identity):
                self.fail("Replacement accepted")
        with restore.guard_destination(self.target) as (_, identity):
            pass
        (self.target / "sentinel").touch()
        with self.assertRaisesRegex(ValueError, "no longer empty"):
            with restore.guard_destination(self.target, identity):
                self.fail("Modification accepted")

    @unittest.skipUnless(os.name == "nt", "Windows share modes require Windows.")
    def test_windows_pins_destination_and_parent_against_rename(self):
        with restore.guard_destination(self.target):
            for path in (self.target, self.root):
                with self.subTest(path=path):
                    moved = path.with_name(path.name + "-moved")
                    try:
                        with self.assertRaises(OSError) as denied:
                            path.rename(moved)
                        self.assertIn(denied.exception.winerror, (5, 32))
                    finally:
                        if moved.exists():
                            moved.rename(path)
