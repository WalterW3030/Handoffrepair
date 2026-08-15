"""T7 — Local user simulator (replaces ToolSandbox's external OpenAI user role, P3).

A LOCAL vLLM-served model generates the user's turns with a FIXED seed from
configs/seeds.yaml (101). All simulator outputs are logged; scoring never uses
simulator judgment (milestone/minefield DAG only).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from vllm_client import VLLMClient

SIM_SEED = 101


class LocalUserSimulator:
    def __init__(self, model_name="Qwen/Qwen3-8B", base_url="http://127.0.0.1:8000"):
        self.client = VLLMClient(model_name, base_url)
        self.name = f"user_sim:{model_name}"

    def next_user_turn(self, conversation):
        """Deterministic (seeded) next user message given the conversation so far."""
        prompt = ([{"role": "system", "content":
                    "You are simulating the user. Reply with only the user's next message."}]
                  + conversation)
        out = self.client.generate(prompt)
        return {"role": "user", "content": out["action"].get("content", ""),
                "sim_seed": SIM_SEED}
