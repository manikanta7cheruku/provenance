"""A local stand-in for the Gemini embedContent endpoint, to try meaning search with no real key.

Run:  python scripts/fake_gemini.py 8765
Then start the api and worker with GEMINI_API_KEY=fake-key, LLM_EMBEDDING_MODEL=fake-embed and
GEMINI_BASE_URL=http://host.docker.internal:8765/v1beta (see docs/operations/operator-commands.md).

It turns words into a 768-number vector by hashing them, so texts that share words are close.
It is a test double, not a model: it cannot find synonyms. Never point it at real data.
"""

import hashlib
import json
import math
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

STOP = {"the", "and", "for", "with", "that", "this", "from", "was", "are", "you", "your"}
CALLS = {"n": 0}


def vector(text: str) -> list[float]:
    v = [0.0] * 768
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) > 2 and word not in STOP:
            v[int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16) % 768] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if (
            not self.path.endswith(":embedContent")
            or self.headers.get("x-goog-api-key") != "fake-key"
        ):
            self.send_response(403)
            self.end_headers()
            return
        text = body["content"]["parts"][0]["text"]
        CALLS["n"] += 1
        payload = json.dumps(
            {
                "embedding": {"values": vector(text)},
                "usageMetadata": {"promptTokenCount": len(text.split())},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        print("embed call", CALLS["n"], flush=True)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(sys.argv[1])), Handler).serve_forever()  # noqa: S104
