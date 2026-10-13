"""UI export ownership, source isolation and replacement behavior."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ui.storage_adapter import publish_output, output_directory, speaker_name


class OutputStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stage = self.root / "stage"
        (self.stage / "segments/SPEAKER_00").mkdir(parents=True)
        (self.stage / "segments/SPEAKER_00/SPEAKER_00_0001.wav").write_bytes(b"first")
        self.target = self.root / "hamid"

    def tearDown(self):
        self.tmp.cleanup()

    def test_other_sources_survive_overwrite_without_stale_files(self):
        publish_output(self.stage, self.target, "hamid", "source_001", overwrite=False)
        publish_output(self.stage, self.target, "hamid", "source_002", overwrite=False)
        with self.assertRaises(FileExistsError):
            publish_output(self.stage, self.target, "hamid", "source_001", overwrite=False)
        old = self.stage / "segments/SPEAKER_00/SPEAKER_00_0001.wav"
        old.rename(old.with_name("SPEAKER_00_0002.wav"))
        publish_output(self.stage, self.target, "hamid", "source_001", overwrite=True)
        self.assertFalse((self.target / "SPEAKER_00/source_001_SPEAKER_00_0001.wav").exists())
        self.assertTrue((self.target / "SPEAKER_00/source_001_SPEAKER_00_0002.wav").is_file())
        self.assertTrue((self.target / "SPEAKER_00/source_002_SPEAKER_00_0001.wav").is_file())

    def test_unrelated_folder_is_never_replaced(self):
        self.target.mkdir()
        (self.target / "personal.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            publish_output(self.stage, self.target, "hamid", "source_001", overwrite=True)
        self.assertEqual((self.target / "personal.txt").read_text(), "keep")

    def test_failed_publication_keeps_previous_output(self):
        publish_output(self.stage, self.target, "hamid", "source_001", overwrite=False)
        with patch("ui.storage_adapter.shutil.copy2", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                publish_output(self.stage, self.target, "hamid", "source_001", overwrite=True)
        self.assertEqual((self.target / "SPEAKER_00/source_001_SPEAKER_00_0001.wav").read_bytes(), b"first")
        self.assertFalse(list(self.root.glob(".hamid-building-*")))

    def test_path_names_are_free_but_cannot_escape_parent(self):
        self.assertEqual(speaker_name("حمید با فاصله"), "حمید با فاصله")
        for name in ("", "..", "../hamid", "x/y", "x\\y", "x\x00y"):
            with self.assertRaises(ValueError):
                speaker_name(name)
        self.assertEqual(output_directory(str(self.root), "hamid"), self.target)
        with self.assertRaises(ValueError):
            output_directory("relative", "hamid")
        self.target.symlink_to(self.stage, target_is_directory=True)
        with self.assertRaises(ValueError):
            output_directory(str(self.root), "hamid")
