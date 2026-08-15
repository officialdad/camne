#!/usr/bin/env python3
"""Ollama-API shim so the UNMODIFIED InterCode-ALFA scorer can use
llama-server for embeddings. Ollama is llama.cpp inside; same mxbai fp16
GGUF + same backend = same embeddings, minus a 700 MB daemon install.

Listens on 11434 (the scorer's hardcoded ollama URL), forwards
POST /api/embeddings -> llama-server /v1/embeddings.

  llama-server -m mxbai-embed-large-v1_fp16.gguf --embeddings --port 18093 &
  python3 embed_shim.py
"""
import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

BACKEND = "http://127.0.0.1:18093/v1/embeddings"


def embed(text):
    """Ollama truncates an over-long input to the context window and embeds
    the head; llama-server refuses it with a 500 ("input is too large"),
    which the scorer counts as a wrong answer. 14 of 900 tasks in run 7 hit
    this — the ones whose command output runs past 512 tokens. Retry on the
    head of the text until it fits, which is what the scorer's real backend
    would have done."""
    while True:
        req = urllib.request.Request(
            BACKEND, data=json.dumps({"input": text}).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["data"][0]["embedding"]
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code != 500 or "too large" not in msg or len(text) < 64:
                raise
            text = text[: len(text) * 3 // 4]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/embeddings":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        emb = embed(body["prompt"])
        out = json.dumps({"embedding": emb}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    print("ollama shim on :11434 -> " + BACKEND)
    HTTPServer(("127.0.0.1", 11434), Handler).serve_forever()
