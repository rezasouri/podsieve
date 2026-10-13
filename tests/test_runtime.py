"""Windows DLL discovery without loading any platform-specific audio libraries."""
from pathlib import Path
import unittest
from unittest.mock import patch
from src.core import runtime


class AudioRuntimeTests(unittest.TestCase):
    def test_non_windows_does_not_change_dll_search_path(self):
        with patch.object(runtime.sys, "platform", "linux"), patch.object(runtime.shutil, "which") as which:
            runtime.configure_audio_runtime()
            which.assert_not_called()

    def test_windows_registers_ffmpeg_directory_and_retains_handle(self):
        executable = str(Path("ffmpeg-bin/ffmpeg.exe").resolve())
        handle = object()
        with patch.object(runtime.sys, "platform", "win32"), patch.object(runtime.shutil, "which", return_value=executable), patch.object(runtime.os, "add_dll_directory", create=True, return_value=handle) as add, patch.dict(runtime._DLL_HANDLES, {}, clear=True):
            runtime.configure_audio_runtime()
            runtime.configure_audio_runtime()
            directory = str(Path(executable).parent)
            add.assert_called_once_with(directory)
            self.assertIs(runtime._DLL_HANDLES[directory], handle)

    def test_missing_ffmpeg_does_not_block_command_help(self):
        with patch.object(runtime.sys, "platform", "win32"), patch.object(runtime.shutil, "which", return_value=None), patch.object(runtime.os, "add_dll_directory", create=True) as add:
            runtime.configure_audio_runtime()
            add.assert_not_called()
