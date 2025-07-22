import json
import threading
import traceback
from typing import Dict, Callable
import time

import requests
from websocket import WebSocketApp

MARKET_CHANNEL = "market"



class WebSocketOrderBook:
    def __init__(self, channel_type: str, url: str, asset_ids: list, message_callback: Callable):
        self.channel_type = channel_type
        self.ws_url = url + "/ws/" + channel_type
        self.rest_url = url
        self.asset_ids = asset_ids
        self.bids: Dict[str, float] = {}
        self.asks: Dict[str, float] = {}
        self.message_callback = message_callback
        self.ws = WebSocketApp(
            self.ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
        )

    def _apply_update(self, price_str: str, size_float: float, side: str):
        book_side = self.bids if side == "BUY" else self.asks
        if size_float > 0:
            book_side[price_str] = size_float
        else:
            if price_str in book_side:
                del book_side[price_str]

    def on_message(self, ws, message):
        if not message or message == "PONG":
            return

        try:
            events = json.loads(message)
            if not isinstance(events, list):
                events = [events]

            book_updated = False
            for event in events:
                if not isinstance(event, dict):
                    continue

                event_type = event.get('event_type')
                if event_type == "book":
                    self.bids.clear()
                    self.asks.clear()
                    for bid in event.get('bids', []):
                        self.bids[str(bid['price'])] = float(bid['size'])
                    for ask in event.get('asks', []):
                        self.asks[str(ask['price'])] = float(ask['size'])
                    book_updated = True
                elif event_type == 'price_change':
                    for change in event.get('changes', []):
                        price = change.get('price')
                        size = change.get('size')
                        side = change.get('side')
                        if price is not None and size is not None and side is not None:
                            self._apply_update(str(price), float(size), side)
                    book_updated = True

            if book_updated and self.message_callback:
                self._send_book_to_callback()

        except Exception:
            traceback.print_exc()


    def _send_book_to_callback(self):
        bids_list = sorted(
            [{'price': float(p), 'size': s} for p, s in self.bids.items()],
            key=lambda x: x['price'],
            reverse=True
        )
        asks_list = sorted(
            [{'price': float(p), 'size': s} for p, s in self.asks.items()],
            key=lambda x: x['price']
        )
        book_payload = {'bids': bids_list, 'asks': asks_list}
        if self.message_callback:
            self.message_callback(book_payload)


    def get_initial_order_book(self):
        if not self.asset_ids:
            return
        token_id = self.asset_ids[0]
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            book_data = response.json()
            self.bids.clear()
            self.asks.clear()
            for bid in book_data.get('bids', []):
                self.bids[str(bid['price'])] = float(bid['size'])
            for ask in book_data.get('asks', []):
                self.asks[str(ask['price'])] = float(ask['size'])
            self._send_book_to_callback()
        except Exception as e:
            print(f"Failed to get initial order book: {e}")

    def on_open(self, ws):
        if self.channel_type == MARKET_CHANNEL:
            self.get_initial_order_book()
            ws.send(json.dumps({"assets_ids": self.asset_ids, "type": MARKET_CHANNEL}))
        threading.Thread(target=self.ping, daemon=True).start()


    def ping(self):
        while self.ws.sock and self.ws.sock.connected:
            self.ws.send("PING")
            time.sleep(10)

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, close_status_code, close_msg):
        pass

    def run(self):
        self.ws.run_forever()

class StartWs:
    @staticmethod
    def start_connection(token_id: str, calculator):
        ws_url = "wss://ws-subscriptions-clob.polymarket.com"
        rest_url = "https://clob.polymarket.com"
        asset_ids = [token_id]
        market_connection = WebSocketOrderBook(
            MARKET_CHANNEL, ws_url, asset_ids, calculator.book_update
        )
        market_connection.rest_url = rest_url
        threading.Thread(target=market_connection.run, daemon=True).start()
        print("websocket running")
        return market_connection