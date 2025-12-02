from typing import List

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.models import Fill, Order, PortfolioPosition, PortfolioState


logger = get_logger(__name__)
settings = get_settings()


class AlpacaBroker:
    """
    Minimal Alpaca paper trading client.

    This is intentionally lightweight and focuses on the subset of
    functionality needed by the orchestrator.
    """

    def __init__(self) -> None:
        if not settings.alpaca.api_key or not settings.alpaca.secret_key:
            logger.warning(
                "Alpaca API credentials are not fully configured; broker calls will fail."
            )
        # Normalize base_url to remove trailing /v2/ if present
        base_url = str(settings.alpaca.base_url).rstrip("/")
        if base_url.endswith("/v2"):
            base_url = base_url[:-3]
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "APCA-API-KEY-ID": settings.alpaca.api_key or "",
                "APCA-API-SECRET-KEY": settings.alpaca.secret_key or "",
            },
        )

    def get_account(self) -> dict:
        resp = self._client.get("/v2/account")
        resp.raise_for_status()
        return resp.json()

    def get_positions(self) -> PortfolioState:
        resp = self._client.get("/v2/positions")
        resp.raise_for_status()
        positions_data = resp.json()

        positions: List[PortfolioPosition] = []
        for item in positions_data:
            positions.append(
                PortfolioPosition(
                    symbol=item["symbol"],
                    quantity=float(item["qty"]),
                    average_price=float(item["avg_entry_price"]),
                )
            )

        account = self.get_account()
        cash = float(account.get("cash", 0.0))
        return PortfolioState(cash=cash, positions=positions)

    def execute_orders(self, orders: List[Order]) -> List[Fill]:
        fills: List[Fill] = []
        for order in orders:
            payload = {
                "symbol": order.symbol,
                "qty": order.quantity,
                "side": order.side,
                "type": order.type,
                "time_in_force": "day",
            }
            if order.type == "limit" and order.limit_price is not None:
                payload["limit_price"] = order.limit_price

            resp = self._client.post("/v2/orders", json=payload)
            resp.raise_for_status()
            data = resp.json()

            from datetime import datetime

            fills.append(
                Fill(
                    order_id=data["id"],
                    symbol=data["symbol"],
                    side=data["side"],
                    quantity=float(data["qty"]),
                    price=float(data.get("filled_avg_price") or data.get("limit_price") or 0.0),
                    timestamp=datetime.fromisoformat(
                        (data.get("filled_at") or data.get("created_at")).replace("Z", "+00:00")
                    ),
                )
            )

        return fills


_alpaca_instance: AlpacaBroker | None = None


def get_alpaca_broker() -> AlpacaBroker:
    global _alpaca_instance
    if _alpaca_instance is None:
        _alpaca_instance = AlpacaBroker()
    return _alpaca_instance



