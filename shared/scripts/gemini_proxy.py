#!/usr/bin/env python3
"""
gemini_proxy.py — OpenAI-compatible proxy for Vertex AI Gemini
Maps OpenAI chat/completions → Vertex AI generateContent → OpenAI response
Run standalone: python3 gemini_proxy.py
"""
import json, urllib.request, http.server, os, time

VERTEX_KEY  = "AQ.Ab8RN6Kn4OjGu7Vfzec6OaAXKGtUKAfaumQkPmMHp-dT3s0G9w"
VERTEX_BASE = "https://aiplatform.googleapis.com/v1/publishers/google/models"
DEFAULT_MDL = "gemini-2.5-flash"
PORT        = int(os.environ.get("GEMINI_PROXY_PORT", "18790"))
MIN_TOKENS  = 64  # gemini-2.5 thinking model needs headroom

MODEL_MAP = {
    "gemini-2.5-flash":        "gemini-2.5-flash",
    "gemini-2.5-flash-lite":   "gemini-2.5-flash-lite",
    "google/gemini-2.5-flash": "gemini-2.5-flash",
}

def call_vertex(model, openai_body):
    messages  = openai_body.get("messages", [])
    contents, sys_parts = [], []
    for m in messages:
        role    = m["role"]
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(p.get("text","") for p in content if isinstance(p,dict))
        if role == "system":
            sys_parts.append({"text": content})
        else:
            contents.append({"role":"model" if role=="assistant" else "user",
                             "parts":[{"text": content}]})

    max_tok = max(
        openai_body.get("max_tokens") or 0,
        openai_body.get("max_completion_tokens") or 0,
        MIN_TOKENS
    )
    req_body = {"contents": contents,
                "generationConfig": {"maxOutputTokens": max_tok}}
    if sys_parts:
        req_body["systemInstruction"] = {"parts": sys_parts}

    vertex_model = MODEL_MAP.get(model, DEFAULT_MDL)
    url = f"{VERTEX_BASE}/{vertex_model}:generateContent?key={VERTEX_KEY}"
    req = urllib.request.Request(
        url, data=json.dumps(req_body).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()), vertex_model

def to_openai(vertex_resp, model):
    candidate = vertex_resp["candidates"][0]
    parts     = candidate.get("content",{}).get("parts",[])
    text      = parts[0]["text"] if parts else ""
    usage     = vertex_resp.get("usageMetadata", {})
    return {
        "id":      f"chatcmpl-{int(time.time())}",
        "object":  "chat.completion",
        "model":   model,
        "choices": [{"index":0, "message":{"role":"assistant","content":text},
                     "finish_reason":"stop"}],
        "usage":   {"prompt_tokens":     usage.get("promptTokenCount",0),
                    "completion_tokens": usage.get("candidatesTokenCount",0),
                    "total_tokens":      usage.get("totalTokenCount",0)},
    }

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_POST(self):
        ln   = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(ln))
        model = body.get("model", DEFAULT_MDL)
        try:
            vertex_resp, used_model = call_vertex(model, body)
            response = to_openai(vertex_resp, used_model)
            status = 200
        except Exception as e:
            response = {"error":{"message":str(e),"type":"proxy_error"}}
            status = 500
        self._send(status, response)

    def do_GET(self):
        models = [{"id":m,"object":"model"} for m in MODEL_MAP]
        self._send(200, {"object":"list","data":models})

    def _send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",len(body))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    srv = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"gemini_proxy: 127.0.0.1:{PORT} → Vertex AI ({DEFAULT_MDL})", flush=True)
    srv.serve_forever()
