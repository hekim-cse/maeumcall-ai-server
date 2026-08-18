from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_qwen_audition_module_import_does_not_require_huggingface_hub():
    probe = """
import builtins
import importlib

original_import = builtins.__import__

def reject_optional_hugging_face_dependency(name, *args, **kwargs):
    if name == "huggingface_hub" or name.startswith("huggingface_hub."):
        raise ModuleNotFoundError(
            "No module named 'huggingface_hub'",
            name="huggingface_hub",
        )
    return original_import(name, *args, **kwargs)

builtins.__import__ = reject_optional_hugging_face_dependency
module = importlib.import_module("scripts.generate_qwen_mother_voice_design_auditions")

try:
    module.resolve_model_snapshot(allow_network=False)
except RuntimeError as error:
    assert "requirements-tts.txt" in str(error)
else:
    raise AssertionError("The optional TTS dependency boundary was not exercised.")
"""

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_timing_refinement_module_import_does_not_require_soundfile():
    probe = """
import builtins
import importlib

original_import = builtins.__import__

def reject_optional_audio_dependency(name, *args, **kwargs):
    if name == "soundfile" or name.startswith("soundfile."):
        raise ModuleNotFoundError("No module named 'soundfile'", name="soundfile")
    return original_import(name, *args, **kwargs)

builtins.__import__ = reject_optional_audio_dependency
importlib.import_module("scripts.refine_tts_timing_and_prosody")
"""

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
