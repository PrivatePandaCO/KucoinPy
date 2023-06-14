import threading
import time
import traceback
import uuid
from typing import List, Optional, Union

import orjson
import requests
from pyloggor import pyloggor

from KucoinPy.classes import Order
from KucoinPy.http import HTTP, Response
from KucoinPy.ws import KucoinWS


def empty(message):
    pass


def emmptyempty():
    pass


class KCW:
    def __init__(
        self,
        kc_api_key,
        kc_api_secret,
        kc_api_passphrase,
        defaults=None,
        second_message_handler=empty,
        after_ws=emmptyempty,
        logger=pyloggor(project_root="KucoinPy"),
    ):
        logger.log("INFO", "Kucoin Client", msg="Starting...")
        self.kc_api_key = kc_api_key
        self.kc_api_secret = kc_api_secret
        self.kc_api_passphrase = kc_api_passphrase

        self.logger = logger
        self._shutdown_global = False
        self._shutdown_ws = False
        self.second_message_handler = second_message_handler
        self.after_ws = after_ws

        self.acks: list[str] = []
        self.messages = []
        self.subscriptions: list[tuple[str, bool]] = (
            [
                ("/account/balance", True),
                ("/spotMarket/tradeOrdersV2", True),
            ]
            if defaults is None
            else defaults
        )

        self.balance: dict[str, dict[str, str]] = {}
        self.orders = {}
        self.baseline = {}

        self.sockets: list[HTTP] = [HTTP(self.kc_api_key, self.kc_api_secret, self.kc_api_passphrase) for _ in range(3)]
        threading.Thread(daemon=True, target=self.sock_cache_maintainer).start()
        self.logger.log("DEBUG", "Kucoin Client", msg="Initialized sockets")

        if not self.get_balance():
            raise SystemExit

        self.cache_lots()
        self.cache_baseline()

        self.__boot_ws(new=True)

        self.logger.log("INFO", "Kucoin Client", msg="Booted up successfully.")

    def cache_baseline(self) -> None:
        try:
            r = requests.get("https://api.kucoin.com/api/v1/market/allTickers")
            data = r.json()["data"]["ticker"]
            self.baseline = {i["symbol"]: i["last"] for i in data}
            self.logger.log(
                "DEBUG",
                "Baseline Caching",
                msg="Successfully cached baseline",
            )
            return True
        except Exception as e:
            self.logger.log(
                "WARNING",
                "Baseline Caching",
                msg="Failed to cache baseline",
                extras={"error": str(e)},
            )
            raise SystemExit

    def cache_lots(self) -> None:
        try:
            r = requests.get("https://api.kucoin.com/api/v1/symbols")
        except Exception as e:
            self.logger.log(
                "WARNING",
                "Lots Caching",
                msg="Failed to cache lots",
                extras={"error": str(e)},
            )
            return self.cache_lots()

        if r.status_code != 200:
            self.logger.log(
                "WARNING",
                "Lots Caching",
                msg="Response not 200",
                extras={"error": r.text},
            )
            return self.cache_lots()

        data = r.json()["data"]
        required_data = {}

        for i in data:
            if i["quoteCurrency"] == "USDT":
                required_data[i["baseCurrency"]] = {
                    "min_funds": i["minFunds"],
                    "coin_lot": i["baseIncrement"],
                    "price_lot": i["priceIncrement"],
                }

        self.lots = required_data
        self.logger.log(
            "DEBUG",
            "Lots Caching",
            msg="Successfully cached Lots",
        )

    def __boot_ws(self, new=False) -> None:
        self._shutdown_ws = True
        self.logger.log(
            "DEBUG",
            "Kucoin Client",
            msg="Booting Kucoin WebSocket",
        )
        self.ws_socket = HTTP(self.kc_api_key, self.kc_api_secret, self.kc_api_passphrase)
        self.ws_socket.send(
            method="POST",
            location="/api/v1/bullet-private",
        )

        try:
            hello: Optional[Response] = self.ws_socket.recv()
            resp: dict = hello.json()
            TOKEN: str = resp["data"]["token"]
            interval: int = resp["data"]["instanceServers"][0]["pingInterval"]
        except Exception as e:
            self.logger.log(
                "ERROR",
                "Kucoin Client",
                msg="Failed to boot WS",
                extras={"error": str(e)},
            )
            return self.__boot_ws()

        ws = KucoinWS(f"/endpoint?token={TOKEN}&private=true")

        self.ws = ws
        self.interval = interval

        threading.Thread(daemon=True, target=self.ping).start()
        threading.Thread(daemon=True, target=self.listen).start()
        threading.Thread(daemon=True, target=self.message_handler).start()

        self.logger.log(
            "DEBUG",
            "Kucoin Client",
            msg="Successfully booted WS, running secondaries",
        )

        for subscription in self.subscriptions:
            x = False
            while not x:
                x = self.subscribe(subscription[0], subscription[1])

        self.logger.log(
            "INFO",
            "Kucoin Client",
            msg="Successfully booted Kucoin WebSocket",
        )
        self._shutdown_ws = False
        if not new:
            self.after_ws()

    def message_handler(self) -> None:
        while True:
            self.messages = [i for i in self.messages if i]
            if not self.messages:
                continue
            else:
                try:
                    threading.Thread(daemon=True, target=self.handle_message, args=(self.messages.pop(0),)).start()
                except Exception as e:
                    self.logger.log(
                        "WARNING",
                        "Kucoin Client",
                        msg="Failed to handle message",
                        extras={"error": str(e)},
                    )

    def handle_message(self, message: dict[str, Union[dict[str, str], str]]) -> None:
        handled = False
        message = orjson.loads(message)
        if message["type"] in ("ack", "pong"):  # required for internal functioning
            self.acks.append(message["id"])  # string
            handled = True

        if message["type"] == "message":  # handle defaults
            data = message["data"]
            if message["topic"] == "/account/balance":  # balance
                self.balance[data["currency"]] = {
                    "available": data["available"],
                    "hold": data["hold"],
                }
                handled = True
            elif message["subject"] == "orderChange":  # personal order change, inbuilt supports v2
                data["filledSize"] = data.get("filledSize", "0")
                cOid = data["clientOid"]
                if cOid not in self.orders:
                    self.orders[cOid] = {
                        "received": [],
                        "open": [],
                        "match": [],
                        "filled": [],
                        "canceled": [],
                        "update": [],
                    }  # initialize with empty list
                self.orders[cOid][data["status"]].append(data)  # maintain all updates pertaining to an order
                handled = True

        # After handling defaults, if second exists, we pass it to second and forget about it
        # However, if second does not exist and message is not handler, log a warning.

        if self.second_message_handler != empty:
            return self.second_message_handler(message)

        if not handled:
            self.logger.log(
                "WARNING",
                "Kucoin Client",
                msg="Unknown message type",
                extras={"message": message},
            )

    def listen(self):
        data = b""
        while True:
            try:
                m = self.ws.socket.recv(256)
            except TimeoutError:
                continue
            except OSError:
                return
            except AttributeError:
                continue
            except Exception as e:
                self.logger.log(
                    "WARNING",
                    "Socket Listen",
                    msg="Unhandled exception while recving data, continuing.",
                    extras={"error": str(e)},
                )
                continue

            data += m
            if b"\xff" not in data:  # end byte
                continue

            msgs = data.split(b"\xff")  # caution: last split result may not be full
            if data.endswith(b"\xff"):  # single or multiple full messages
                data = b""  # reset data
                self.messages.extend([i.strip(b"\x00") for i in msgs])
            else:
                data = msgs[-1]  # last split result may not be full
                self.messages.extend([i.strip(b"\x00") for i in msgs[:-1]])

    def subscribe(self, topic: str, private: bool = True, force_unsub=False) -> bool:
        self.subscriptions.append((topic, private))
        self.subscriptions = list(set(self.subscriptions))

        if force_unsub:
            unsub = self.unsubscribe(topic, private)
            if not unsub:
                return self.subscribe(topic, private)
        start = int(time.time() * 1000)
        myid = str(start)
        self.ws.send(
            {
                "id": myid,
                "type": "subscribe",
                "topic": topic,
                "privateChannel": private,
                "response": True,
            }
        )

        while start + 30000 > time.time() * 1000:
            if myid in self.acks:
                self.logger.log(
                    "DEBUG",
                    "Kucoin Client",
                    msg="Subscribed to topic",
                    extras={"topic": topic},
                )
                return True

        self.logger.log(
            "ERROR",
            "Kucoin Client",
            msg="Failed to subscribe to topic",
            extras={"topic": topic},
        )
        return self.subscribe(topic, private)

    def unsubscribe(self, topic: str, private: bool = True) -> bool:
        self.subscriptions = [i for i in set(self.subscriptions) if i != (topic, private)]
        start = int(time.time() * 1000)

        myid = str(start)
        self.ws.send(
            {
                "id": myid,
                "type": "unsubscribe",
                "topic": topic,
                "privateChannel": private,
                "response": True,
            }
        )

        while start + 30000 > time.time() * 1000:
            if myid in self.acks:
                self.logger.log(
                    "DEBUG",
                    "Kucoin Client",
                    msg="Unsubscribed from topic",
                    extras={"topic": topic},
                )
                sub = (topic, private)
                while sub in self.subscriptions:
                    self.subscriptions.remove(sub)
                self.subscriptions = list(set(self.subscriptions))
                return True

        self.logger.log(
            "ERROR",
            "Kucoin Client",
            msg="Failed to unsubscribe from topic",
            extras={"topic": topic},
        )
        return False

    def reboot_ws(self):
        self._shutdown_ws = True
        self.ws.close_connection()
        self.__boot_ws()

    def internal_ping(self):
        myid = uuid.uuid4().hex
        start = int(time.time() * 1000)
        self.ws.send({"id": myid, "type": "ping"})
        while start + 30000 > time.time() * 1000:
            if myid in self.acks:
                self.acks.remove(myid)
                return True
        return False

    def ping(self):
        while True:
            time.sleep(self.interval / 1000)
            if self._shutdown_ws:
                break
            try:
                if not self.internal_ping():
                    self.logger.log(
                        "WARNING",
                        "Kucoin Client",
                        msg="Kucoin did not respond to ping, rebooting WS.",
                    )
                    self.reboot_ws()
            except Exception as e:
                self.logger.log(
                    "WARNING",
                    "Kucoin Client",
                    msg="Failed to ping WS",
                    extras={"error": str(e)},
                )
                self.reboot_ws()

    def shutdown(self):
        self._shutdown_global = True
        self._shutdown_ws = True
        self.ws.close_connection()
        for sock in self.sockets:
            sock.close_connection()

    def sock_cache_maintainer(self):
        while True:
            if self._shutdown_global:
                continue
            if len(self.sockets) < 10:
                self.sockets.append(HTTP(self.kc_api_key, self.kc_api_secret, self.kc_api_passphrase))
            time.sleep(0.5)  # not spam :)

    def calc_lots(self, raw: str, lot_size: str) -> str:
        return raw[: len(raw.split(".")[0]) + 1 + len(lot_size.split(".")[1])]

    def order(self, order: Order, autosplit: int = 1, response=False, sock=None) -> str:
        sock = sock or self.sockets.pop()
        if autosplit > 6 or autosplit < 1:
            return "bad autosplit"

        base = order.symbol.split("-")[0]

        if order.type == "limit":
            order.price = self.calc_lots(str(order.price), self.lots[base]["price_lot"])
            order.size = self.calc_lots(str(float(order.size) / autosplit), self.lots[base]["coin_lot"])
            orders = [order] * autosplit
        else:
            try:
                order.funds = self.calc_lots(str(float(order.funds)), self.lots[base]["coin_lot"])
            except:
                try:
                    order.size = self.calc_lots(str(float(order.size)), self.lots[base]["coin_lot"])
                except:
                    pass
            return self._single_order(order, sock, response)

        if len(orders) == 1:
            return self._single_order(orders[0], sock, response)
        else:
            return self._multi_order(orders, sock, response)

    def _single_order(self, order: Order, sock, response=False) -> Union[bool, Response]:
        try:
            sock.send(
                method="POST",
                location="/api/v1/hf/orders",
                payload=order.__dict__,
            )
            if response:
                return sock.recv()

            return True
        except Exception as e:
            self.logger.log(
                "WARNING",
                "Kucoin Client",
                msg="Failed to place order",
                extras={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "dumped": order.__dict__,
                },
            )
            return

    def _multi_order(self, orders: List[Order], sock, response=False) -> Union[bool, Response]:
        for order in orders:
            order.clientOid = uuid.uuid4().hex
        payload = {"symbol": orders[0].symbol, "orderList": [i.__dict__ for i in orders]}
        try:
            sock.send(
                method="POST",
                location="/api/v1/hf/orders/multi",
                payload=payload,
            )
            if response:
                return sock.recv()
            return True
        except Exception as e:
            self.logger.log(
                "WARNING",
                "Kucoin Client",
                msg="Failed to place order",
                extras={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "payload": payload,
                },
            )
            return


    def cancel_all(self, symbol, retries=5, response=False):
        for i in range(retries):
            try:
                sock = self.sockets.pop()
                sock.send(
                    method="DELETE",
                    location=f"/api/v1/hf/orders?symbol={symbol}",
                    payload={"symbol": symbol},
                )
                self.logger.log(
                    "DEBUG",
                    "Order cancel",
                    msg=f"Cancelled all orders for {symbol}",
                )

                return sock.recv() if response else True
            except Exception as e:
                self.logger.log(
                    "WARNING",
                    "Order cancel",
                    msg=f"Failed to cancel all orders for {symbol}",
                    extras={"error": e, "traceback": traceback.format_exc()},
                )
                continue

    def get_balance(self, retries=3):
        if retries <= 0:
            return False
        try:
            sock = self.sockets.pop()
            sock.send(
                "GET",
                "/api/v1/accounts",
            )
        except Exception as e:
            self.logger.log(
                "WARNING",
                "Balance maintainence",
                msg="Failed to get balance",
                extras={"error": e},
            )
            return self.get_balance(retries - 1)

        try:
            resp = sock.recv()
            data = resp.json()["data"]
        except Exception as e:
            self.logger.log(
                "WARNING",
                "Balance maintainence",
                msg="Failed to get balance",
                extras={"error": e},
            )
            return self.get_balance(retries - 1)

        for entry in data:
            if entry["type"] != "trade_hf":
                continue
            self.balance[entry["currency"]] = {"available": 0, "hold": 0}
            self.balance[entry["currency"]]["available"] = float(entry["available"])
            self.balance[entry["currency"]]["hold"] = float(entry["holds"])
        return True

    def get_ob(self, symbol):
        r = requests.get(
            url=f"https://api.kucoin.com/api/v3/market/orderbook/level2?symbol={symbol}",
            headers=HTTP(self.kc_api_key, self.kc_api_secret, self.kc_api_passphrase).send(
                method="GET", location=f"/api/v3/market/orderbook/level2?symbol={symbol}", heads_only=True
            ),
        )
        return r.json()["data"]
