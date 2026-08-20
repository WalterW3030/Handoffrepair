#!/usr/bin/env python3
"""Verify downloaded model weights against configs/weight_sha256.lock (per-file SHA-256).

Run on the staging machine AFTER `hf download` of the four pinned repos.
Reads the HF cache (or --root override), hashes every locked file, and reports
OK / MISMATCH / MISSING per model. Exit 0 only if everything matches.

The lock is YAML:
  models:
    <org/name>:
      revision: <sha>
      safetensors_sha256:
        <filename>: <sha256>

Usage:
  python tools/hash_weights.py                      # use HF_HOME/HF_HUB_CACHE or ~/.cache/huggingface
  python tools/hash_weights.py --root /ephemeral/u/hf   # custom HF cache root (contains hub/)
Requires: pyyaml (installed by scripts/setup_machine.sh).
"""
import argparse, hashlib, os, sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOCK = os.path.join(ROOT, "configs", "weight_sha256.lock")


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def load_lock():
    """Return list of (repo, revision, filename, sha256) from the YAML lock."""
    with open(LOCK) as f:
        data = yaml.safe_load(f)
    entries = []
    for repo, spec in data["models"].items():
        rev = spec["revision"]
        for fname, digest in (spec.get("safetensors_sha256") or {}).items():
            entries.append((repo, rev, fname, digest))
    return entries


def find_snapshot(cache_root, repo, revision):
    """Locate the exact pinned snapshot dir for a repo inside an HF cache root."""
    snap_dir = os.path.join(cache_root, "hub",
                            "models--" + repo.replace("/", "--"), "snapshots")
    exact = os.path.join(snap_dir, revision)
    if os.path.isdir(exact):
        return exact
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get(
        "HF_HUB_CACHE",
        os.path.join(os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")))))
    ap.add_argument("--out", default=None,
                    help="if set, append a verification summary block to this yaml file")
    a = ap.parse_args()

    entries = load_lock()
    n_ok = n_bad = n_missing = 0
    per_model = {}
    for repo, rev, fname, digest in entries:
        per_model.setdefault(repo, {"ok": 0, "bad": 0, "missing": 0})
        snap = find_snapshot(a.root, repo, rev)
        path = os.path.join(snap, fname) if snap else None
        if not path or not os.path.exists(path):
            n_missing += 1
            per_model[repo]["missing"] += 1
            print(f"MISSING  {repo}@{rev[:8]}:{fname}")
            continue
        actual = sha256_file(path)
        if actual == digest:
            n_ok += 1
            per_model[repo]["ok"] += 1
        else:
            n_bad += 1
            per_model[repo]["bad"] += 1
            print(f"MISMATCH {repo}:{fname}: lock={digest[:16]}... actual={actual[:16]}...")

    print(f"\nverified {n_ok} OK / {n_bad} MISMATCH / {n_missing} MISSING "
          f"({len(entries)} locked files, cache root {a.root})")
    if a.out:
        import datetime
        with open(a.out, "a") as f:
            f.write(f"\nweight_verification:  # {datetime.datetime.now(datetime.UTC).isoformat()}\n")
            f.write(f"  cache_root: {a.root}\n  ok: {n_ok}\n  mismatch: {n_bad}\n  missing: {n_missing}\n")
            for m, c in per_model.items():
                f.write(f'  "{m}": {c}\n')
    sys.exit(0 if (n_bad == 0 and n_missing == 0 and n_ok == len(entries)) else 1)


if __name__ == "__main__":
    main()
