"""T7 — Real vLLM client. Drop-in replacement for MockModel (same generate() signature).

Talks to the OpenAI-compatible vLLM server started by serving/serve_*.sh.
Raises runner.TransportError on transport failures so the retry rule reuses the op-ID.
Decoding comes from configs/decoding.yaml (frozen). tool_call_shim.UniformToolShim sits in
front of this client for EVERY pilot model (user decision 2026-08-29, choice 2-C — no
engine-native tool parsers anywhere); the runner cannot tell the difference.
"""
import os, sys, json, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
import yaml


def _decoding():
    with open(os.path.join(os.path.dirname(__file__), "..", "configs", "decoding.yaml")) as f:
        return yaml.safe_load(f)["decoding"]


class VLLMClient:
    def __init__(self, model_name, base_url="http://127.0.0.1:8000"):
        self.name = model_name
        self.base_url = base_url.rstrip("/")
        self._dec = _decoding()

    def generate(self, messages, tools=None):
        body = {
            "model": self.name,
            "messages": messages,
            "temperature": self._dec["temperature"],
            "top_p": self._dec["top_p"],
            "max_tokens": self._dec["max_new_tokens"],
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                out = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            from runner import TransportError
            raise TransportError(str(e))
        msg = out["choices"][0]["message"]
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            action = {"type": "tool_call", "tool": tc["function"]["name"],
                      "args": json.loads(tc["function"]["arguments"] or "{}")}
        else:
            action = {"type": "message", "content": msg.get("content", "")}
        return {"model": self.name, "action": action,
                "usage": {"prompt_tokens": out["usage"]["prompt_tokens"],
                          "completion_tokens": out["usage"]["completion_tokens"]}}
