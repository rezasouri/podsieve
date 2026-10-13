"""Platform startup helpers shared by the desktop and command-line entry points."""
import os
from pathlib import Path
import shutil
import sys

_DLL_HANDLES = {}


def configure_audio_runtime():
    """Keep FFmpeg's shared-library directory in Windows' DLL search path."""
    if sys.platform != "win32":
        return
    executable = shutil.which("ffmpeg")
    if not executable:
        return
    directory = str(Path(executable).resolve().parent)
    if directory not in _DLL_HANDLES:
        # The handle must remain alive for later lazy TorchCodec imports.
        _DLL_HANDLES[directory] = os.add_dll_directory(directory)
