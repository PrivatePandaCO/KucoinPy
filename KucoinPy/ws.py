import socket
import ssl
from typing import Optional, Union

import orjson


class KucoinWS:
    def __init__(self, location: str) -> None:
        self.location = location

        self.socket = self.create_connection()
        self.connect()

    def create_connection(self) -> ssl.SSLSocket:
        socket_session = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_session.connect(("ws-api.kucoin.com", 443))
        socket_session.settimeout(5)
        return ssl.create_default_context().wrap_socket(socket_session, server_hostname="ws-api.kucoin.com")

    def close_connection(self) -> None:
        try:
            self.socket.sendall(b"\x08")
        except:
            pass
        try:
            self.socket.close()
        except:
            pass
        self.socket = None

    def connect(self) -> str:
        self.socket.sendall(
            f"GET {self.location} HTTP/1.1\r\nHost: ws-api.kucoin.com\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nOrigin: null\r\n\r\n".encode()
        )

        res: bytes = self.socket.recv(1024)
        status_code = int(res.split(b" ")[1].decode("UTF-8"))
        if status_code != 101:
            return self.connect()

        hello: Optional[str] = self.recv(1024)
        if hello in ("none", "empty"):
            return self.connect()

    def send(self, data: Union[str, dict[str, str]]):
        if not self.socket:
            return
        d = orjson.dumps(data) if isinstance(data, dict) else (data.encode() if isinstance(data, bytes) else data)
        self.socket.sendall(b"\x00" + d + b"\xff")

    def recv(self, size) -> Union[str, list[bytes]]:
        if not self.socket:
            return
        try:
            res = self.socket.recv(size)
        except:
            return "none"

        if res in [False, None, b""] or len(res) == 0:
            return "empty"

        return res.strip(b"\x00").strip(b"\xff").split(b"\xff\x00")
