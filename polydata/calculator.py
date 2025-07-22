from dataclasses import dataclass
from binance_data.binance_websocket import BinanceWebsocket
from binance_data.volatility import CalculateVolatility
from polydata import rest_api
from datetime import datetime, timezone
from polydata.polymarket_websocket import StartWs
import numpy as np
from scipy.stats import norm

class Calculator:
    def __init__(self, slug, strike_price, symbol):
        self.slug = slug
        self.buy_token, self.sell_token, self.expiration = rest_api.get_market_details(self.slug)
        self.time_to_expiration = None
        self.strike_price = strike_price
        self.order_book = {'bids': [], 'asks': []}
        self.symbol = symbol
        self.price = None
        self.volatility = None
        self.interest_rate = 0
        self.black_scholes_price = None
        self.garman_klass_volatility = []
        self.standard_deviation_ema_volatility = []
        self.standard_deviation_volatility = []
        self.parkinson_volatility = []
        self.garman_klass_fair_value = []
        self.parkinson_fair_value = []
        self.standard_deviation_fair_value = []
        self.standard_deviation_ema_fair_value = []
        self.cum_garman_klass_difference = 0
        self.cum_standard_deviation_difference = 0
        self.cum_standard_deviation_ema_difference = 0
        self.cum_parkinson_difference = 0
        self.garman_klass_cum_side = 0
        self.parkinson_cum_side = 0
        self.standard_deviation_cum_side = 0
        self.standard_deviation_ema_cum_side = 0

    def initialize(self):
        buy_token, sell_token, expiry = rest_api.get_market_details(self.slug)
        pm_ws = StartWs.start_connection(buy_token, self)
        vol = CalculateVolatility(self.symbol, self.update_vol)
        bn_ws = BinanceWebsocket(self.symbol, self.binance_update, vol.binance_update)
        bn_ws.run()

    def update_vol(self, garman_klass, sd, sdema, parkinson):
        self.garman_klass_volatility = garman_klass
        self.standard_deviation_volatility = sd
        self.standard_deviation_ema_volatility = sdema
        self.parkinson_volatility = parkinson

    def book_update(self, order_book):
        self.order_book = order_book

    def binance_update(self, price):
        self.price = price
        self.time_to_expiration = self.calculate_time_to_expiration(self.expiration)
        print()
        self.garman_klass_fair_value = self.get_all_fair_value(self.garman_klass_volatility)
        self.parkinson_fair_value = self.get_all_fair_value(self.parkinson_volatility)
        self.standard_deviation_fair_value = self.get_all_fair_value(self.standard_deviation_volatility)
        self.standard_deviation_ema_fair_value = self.get_all_fair_value(self.standard_deviation_ema_volatility)
        self.compare_vol_types()

    def get_all_fair_value(self, volatility):
        fair_values = []
        if volatility:
            for vol in volatility:
                fair_values.append(self.calculate_black_scholes(vol))
        return fair_values

    def calculate_time_to_expiration(self, expiration_date_str: str) -> float:
        SECONDS_IN_A_YEAR = 365.25 * 24 * 60 * 60
        expiration_date = datetime.fromisoformat(expiration_date_str.replace('Z', '+00:00'))
        current_date_utc = datetime.now(timezone.utc)
        time_difference_seconds = (expiration_date - current_date_utc).total_seconds()

        if time_difference_seconds <= 0:
            return 0
        return time_difference_seconds / SECONDS_IN_A_YEAR

    def calculate_black_scholes(self, volatility):
        if self.price is None or volatility is None or self.expiration is None:
            return

        d1 = (np.log(self.price / self.strike_price) + (
                    self.interest_rate + 0.5 * volatility ** 2) * self.time_to_expiration) / (
                         volatility * np.sqrt(self.time_to_expiration))
        d2 = d1 - volatility * np.sqrt(self.time_to_expiration)
        # print("binance price: ", self.binance_price)
        black_scholes_price = norm.cdf(d2)
        # print(f"Fair Value: {black_scholes_price} Vol: {volatility} Best Bid: {self.order_book['bids'][0]['price']} Best Ask: {self.order_book['asks'][0]['price']}")
        return black_scholes_price

    def compare_vol_types(self):
        if not self.order_book['bids'] or not self.order_book['asks']:
            return

        best_bid = self.order_book['bids'][0]['price']
        best_ask = self.order_book['asks'][0]['price']

        mid_price = (best_bid + best_ask) / 2

        # Generate timeframe labels for 15-minute increments up to 4 hours (240 minutes)
        timeframe_labels = [f"{i} minutes" for i in range(15, 241, 15)]

        all_fair_values_with_details = []

        fair_value_types = {
            "Garman Klass": self.garman_klass_fair_value,
            "Parkinson": self.parkinson_fair_value,
            "Standard Deviation": self.standard_deviation_fair_value,
            "Standard Deviation EMA": self.standard_deviation_ema_fair_value
        }

        for vol_type_name, fair_values_list in fair_value_types.items():
            for i, fv in enumerate(fair_values_list):
                # Ensure the index 'i' is within the bounds of timeframe_labels
                if i < len(timeframe_labels):
                    current_timeframe_label = timeframe_labels[i]
                    if fv is not None:
                        diff = abs(fv - mid_price)
                        all_fair_values_with_details.append((vol_type_name, current_timeframe_label, fv, diff))

        if all_fair_values_with_details:
            overall_closest_fv_info = min(all_fair_values_with_details, key=lambda x: x[3])
            closest_type_name, closest_timeframe, closest_fv, _ = overall_closest_fv_info

            print(f"{closest_type_name}, {closest_timeframe}, fair value: {closest_fv:.4f}")
            print(f"Fair Value: {mid_price} Garman klass: {self.garman_klass_fair_value}\nSD: {self.standard_deviation_fair_value}\nSDEMA: {self.standard_deviation_ema_fair_value}\nParkinson: {self.parkinson_fair_value}")