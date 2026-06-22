"""Minecraft/NBT profile placeholder.

NBT editing should only be enabled with a real NBT library, such as nbtlib.
"""

from __future__ import annotations


def nbt_support_available() -> bool:
    try:
        import nbtlib  # noqa: F401
    except ImportError:
        return False
    return True


def support_status() -> str:
    if nbt_support_available():
        return "NBT library available; viewer integration can be enabled in a future profile."
    return "NBT support is disabled until nbtlib is installed and wired into the UI."
