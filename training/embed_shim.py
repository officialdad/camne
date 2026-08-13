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
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

BACKEND = "http://127.0.0.1:18093/v1/embeddings"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/embeddings":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        req = urllib.request.Request(
            BACKEND,
            data=json.dumps({"input": body["prompt"]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            emb = json.load(r)["data"][0]["embedding"]
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
