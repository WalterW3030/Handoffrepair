"""DEPRECATED 2026-08-29 (user decision, choice 2-C): use serving/tool_call_shim.py.

This module remains only so older imports keep working. The pilot now uses
UniformToolShim for ALL models (no engine-native tool parsers anywhere).
"""
from tool_call_shim import UniformToolShim, GemmaToolShim  # noqa: F401
