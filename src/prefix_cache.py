"""A3 — Prefix identity layer for strict pairing.

A "cached prefix" is the exact message list at the switch point. Its ID is
the sha256 of canonical JSON, so equality of IDs == bitwise equality of
prefixes. On the GPU machine vLLM's automatic prefix caching gives the
performance; THIS module gives the audit guarantee: every column that
claims to continue the same prefix must log the same prefix_id.
"""
import hashlib, json


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def prefix_id(messages):
    return hashlib.sha256(canonical(messages).encode()).hexdigest()


def assert_paired(ids):
    """All columns of a paired cell must report identical prefix IDs."""
    if len(set(ids)) != 1:
        raise AssertionError(f"pairing violated: prefix ids diverge {ids}")
    return ids[0]
