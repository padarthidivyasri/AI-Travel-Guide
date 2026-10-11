from http.server import BaseHTTPRequestHandler

from Backend.app import app


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(405)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        with app.test_client() as client:
            response = client.post(
                "/api/generate-audio-guide",
                data=body,
                content_type=self.headers.get("Content-Type", "application/json"),
            )

        payload = response.get_data()
        self.send_response(response.status_code)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
