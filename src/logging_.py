"""A1 — Append-only run log (advisor: "freeze and log the pilot pipeline").

Schema (one JSON object per line, JSONL):
  ts, episode_id, column, switch_point, seed, model_source, model_target,
  prefix_ids (dict), steps (list of step dicts), checks_fired, gate_branch,
  usage {prompt_tokens, completion_tokens}, gpu_h, cash, score (dict)

Append-only discipline: this module never opens the log in any mode other
than "a". There is intentionally NO update/delete API.
"""
import json, os, datetime

REQUIRED_FIELDS = ["ts", "episode_id", "column", "switch_point", "seed",
                   "model_source", "model_target", "prefix_ids", "steps",
                   "checks_fired", "gate_branch", "usage", "gpu_h", "cash", "score"]


def append_record(log_path, record):
    record = dict(record)
    record["ts"] = record.get("ts") or datetime.datetime.utcnow().isoformat() + "Z"
    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        raise ValueError(f"log record missing fields: {missing}")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:          # append-only, always
        f.write(json.dumps(record, sort_keys=True) + "\n")


def read_log(log_path):
    if not os.path.exists(log_path):
        return []
    with open(log_path) as f:
        return [json.loads(line) for line in f if line.strip()]
