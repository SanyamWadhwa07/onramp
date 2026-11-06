import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .store import Store

store = Store()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/products":
            self._send(200, [p.__dict__ for p in store.products()])
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/orders":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        skus = json.loads(self.rfile.read(length) or b"[]")
        try:
            order = store.place_order(skus)
        except KeyError as exc:
            return self._send(400, {"error": str(exc)})
        self._send(201, order.__dict__)


def main(port=8000):
    HTTPServer(("", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
