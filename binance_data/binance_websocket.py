from typing import Callable
import websocket
import json
import threading

class BinanceWebsocket:
    def __init__(self, symbol, callback: Callable, vol_callback: Callable):
        self.callback = callback
        self.vol_callback = vol_callback
        self.symbol = symbol
        self.stream_name = f"{self.symbol}@bookTicker"
        self.url = f"wss://stream.binance.com:9443/ws/{self.stream_name}"

    def on_message(self, ws, message):
        data = json.loads(message)

        bid = float(data['b'])
        ask = float(data['a'])

        price = (bid + ask) / 2

        self.vol_callback(price)
        self.callback(price)


    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Connection closed")

    def on_open(self, ws):
        print("Connection opened")

    def start_websocket(self):
        ws = websocket.WebSocketApp(self.url,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)
        ws.on_open = self.on_open
        ws.run_forever()

    def run(self):
        # start ws in separate thread
        threading.Thread(target=self.start_websocket).start()