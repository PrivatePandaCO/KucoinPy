from typing import Literal


class Order:
    def __init__(
        self,
        *,
        clientOid: str,
        side: Literal["buy", "sell"],
        symbol: str,
        type: Literal["market", "limit"],
        timeInForce: Literal["GTC", "IOC", "FOK", "GTT"] = "GTC",
        cancelAfter: int = 5,
        price: str = "",
        size: str = "",
        funds: str = "",
    ):
        self.clientOid = clientOid
        self.side = side
        self.symbol = symbol
        self.type = type
        self.timeInForce = timeInForce

        if type == "market":
            if funds:
                self.funds = funds
            if size:
                self.size = size
        elif type == "limit":
            self.price = price
            self.size = size
            if self.timeInForce == "GTT":
                self.cancelAfter = cancelAfter
