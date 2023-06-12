import base64
import hashlib
import hmac
import socket
import ssl
import time
from typing import Optional

import orjson


def get_headers(kc_api_secret, kc_api_key, PASSPHRASE, method: str, endpoint: str, payload: dict = {}) -> dict[str, str]:
    now = str(int(time.time() * 1000))
    x = f"{now}{method}{endpoint}".encode()
    if payload:
        x += orjson.dumps(payload)

    return {
        "KC-API-SIGN": base64.b64encode(
            hmac.new(
                kc_api_secret.encode(),
                x,
                hashlib.sha256,
            ).digest()
        ).decode(),
        "KC-API-TIMESTAMP": now,
        "KC-API-KEY": kc_api_key,
        "KC-API-PASSPHRASE": PASSPHRASE,
        "KC-API-KEY-VERSION": "2",
    }


def make_PASSPHRASE(secret, passphrase):
    return base64.b64encode(hmac.new(secret.encode(), passphrase.encode(), hashlib.sha256).digest()).decode()


class Response:
    def __init__(self, data: bytes) -> None:
        self.raw_response = data
        if data.endswith(b"\r\n0\r\n\r\n"):  # still working on the fix 😩
            self.text = data.split(b"\r\n0")[0].split(b"\r\n")[-1].decode()
        else:
            self.text = data.split(b"\r\n\r\n")[-1].decode().strip()

    def json(self):
        try:
            return orjson.loads(self.text)
        except:
            raise ValueError(f"Response is not JSON: {self.raw_response}")


class HTTP:
    def __init__(self, kc_api_key, kc_api_secret, kc_api_passphrase, timeout: int = 3) -> None:
        self.timeout = timeout
        self.new_conn()

        self.kc_api_key = kc_api_key
        self.kc_api_secret = kc_api_secret
        self.kc_api_passphrase = kc_api_passphrase
        self.PASSPHRASE = make_PASSPHRASE(self.kc_api_secret, self.kc_api_passphrase)

    def new_conn(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("api.kucoin.com", 443))
        s.settimeout(self.timeout)
        self.socket = ssl.create_default_context().wrap_socket(s, server_hostname="api.kucoin.com")

    def close_connection(self) -> None:
        self.socket.close()

    def recv(self) -> Optional[Response]:
        data = b""
        while True:
            try:
                response = self.socket.recv(1024)
                if response in [False, None, b""] or len(response) == 0:
                    return Response(data)
            except TimeoutError:
                if data:
                    return Response(data)
                raise TimeoutError("Connection timed out")
            data += response

    def send(self, method: str, location: str, payload: dict = {}, heads_only=False) -> None:
        headers, payload = get_headers(self.kc_api_secret, self.kc_api_key, self.PASSPHRASE, method, location, payload)
        if heads_only:
            return headers

        d = "\r\n"
        if payload:
            req = f"{method.upper()} {location} HTTP/1.1\r\n{d.join([f'{a}: {b}' for a, b in headers.items()])}\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\n\r\n"
            req = req.encode() + payload
        else:
            req = (
                f"{method.upper()} {location} HTTP/1.1\r\n{d.join([f'{a}: {b}' for a, b in headers.items()])}\r\n\r\n".encode()
            )

        self.socket.sendall(req)
