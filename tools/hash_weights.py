#!/usr/bin/env python3
"""Verify downloaded model weights against configs/weight_sha256.lock (per-file SHA-256).

Run on the staging machine AFTER `huggingface-cli download` of the four pinned repos.
Reads the HF cache (or --root override), hashes every locked file, and reports
MATCH / MISMATCH / MISSING per model. Exit 0 only if everything matches.

Usage:
  python tools/hash_weights.py                      # use default HF cache (~/.cache/huggingface)
  python tools/hash_weights.py --root /data/hf      # custom HF_HOME/HF_HUB_CACHE root
"""
import argparse, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOCK = os.path.join(ROOT, "configs", "weight_sha256.lock")

MODELS = {
    "Qwen/Qwen3-32B": None,
    "Qwen/Qwen3-8B": None,
    "RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic": None,
    "google/gemma-4-31B-it": None,
}


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def load_lock():
    """lock format: one 'sha256  model_repo/relpath' per line (see configs/weight_sha256.lock)."""
    entries = []
    with open(LOCK) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                entries.append((parts[0], parts[1]))
    return entries


def find_snapshot(cache_root, repo):
    """Locate the snapshot dir for a repo inside an HF cache root."""
    repo_dir = os.path.join(cache_root, "hub",
                            "models--" + repo.replace("/", "--"), "snapshots")
    if not os.path.isdir(repo_dir):
        return None
    snaps = sorted(os.listdir(repo_dir))
    return os.path.join(repo_dir, snaps[-1]) if snaps else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get(
        "HF_HUB_CACHE", os.path.expanduser("~/.cache/huggingface")))
    ap.add_argument("--out", default=None,
                    help="if set, append a verification summary block to this yaml file")
    a = ap.parse_args()

    entries = load_lock()
    n_ok = n_bad = n_missing = 0
    per_model = {}
    for digest, relpath in entries:
        repo, _, rel = relpath.partition("/")
        per_model.setdefault(repo, {"ok": 0, "bad": 0, "missing": 0})
        snap = find_snapshot(a.root, repo)
        path = os.path.join(snap, rel) if snap else None
        if not path or not os.path.exists(path):
            n_missing += 1
            per_model[repo]["missing"] += 1
            print(f"MISSING  {relpath}")
            continue
        actual = sha256_file(path)
        if actual == digest:
            n_ok += 1
            per_model[repo]["ok"] += 1
        else:
            n_bad += 1
            per_model[repo]["bad"] += 1
            print(f"MISMATCH {relpath}: lock={digest[:16]}… actual={actual[:16]}…")

    print(f"\nverified {n_ok} OK / {n_bad} MISMATCH / {n_missing} MISSING "
          f"({len(entries)} locked files, cache root {a.root})")
    if a.out:
        import datetime
        with open(a.out, "a") as f:
            f.write(f"\nweight_verification:  # {datetime.datetime.now(datetime.UTC).isoformat()}\n")
            f.write(f"  cache_root: {a.root}\n  ok: {n_ok}\n  mismatch: {n_bad}\n  missing: {n_missing}\n")
            for m, c in per_model.items():
                f.write(f"  {m}: {c}\n")
    sys.exit(0 if (n_bad == 0 and n_missing == 0 and n_ok == len(entries)) else 1)


if __name__ == "__main__":
    main()
