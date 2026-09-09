"""Live OpenAI-compatible client for the GPU run path (2026-09-08, M28 follow-up).

VLLMClient speaks the engine's native tool_calls shape, which we deliberately do NOT
use (uniform-shim decision 2026-08-29). The shim needs an OpenAI-SDK-shaped client
(client.chat.completions.create(..., extra_body=...)) — this is that shape over
urllib, so the runner needs no openai package inside or outside containers.

Proxy-bypassing: the serving shell exports http_proxy for HF downloads; without an
empty ProxyHandler, urllib routes even localhost through the proxy (2026-09-05
health-check incident). Same fix as tools/t2_shim_gate.sh's LiveClient.
"""
import json
import urllib.request


class LiveClient:
    def __init__(self, base_url="http://127.0.0.1:8000", timeout=300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        # attribute chain the shim expects: client.chat.completions.create
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self._create

    def _create(self, model, messages, extra_body=None, temperature=0.0, max_tokens=None):
        payload = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_body:
            payload.update(extra_body)
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with self._opener.open(req, timeout=self.timeout) as r:
            d = json.loads(r.read().decode())
        msg = d["choices"][0]["message"]
        usage = d.get("usage", {})
        resp = type("Resp", (), {})()
        resp.choices = [type("C", (), {"message":
                                     type("M", (), {"content": msg.get("content")})()})()]
        resp.usage = type("U", (), {"model_dump": lambda s: dict(usage)})()
        return resp
