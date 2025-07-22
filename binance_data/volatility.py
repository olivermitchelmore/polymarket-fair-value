import math
import threading
import time
from typing import Callable

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import requests

# standard deviation, standard deviation ema, parkinson, garman klass

class CalculateVolatility:
    def __init__(self, symbol, callback: Callable, interval = "1m", limit = 15, minutes = 15):
        self.symbol = symbol.upper()
        self.interval = "1m"
        self.limit = limit + 1
        self.minutes = minutes
        self.ewm_span = limit
        self.candle_data = None
        self.binance_price = None
        self.callback = callback
        self.garman_klass = []
        self.sd = []
        self.sdema = []
        self.parkinson = []
        self._scheduler_thread = None
        self._stop_event = threading.Event()
        self._start_scheduler()
        print("fetching binance data...")
        self.get_binance_data(255)

    def _start_scheduler(self):
        self._scheduler_thread = threading.Thread(target=self._schedule_data_fetch, daemon=True)
        self._scheduler_thread.start()

    def _schedule_data_fetch(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            target_second = 1
            current_second = now.second
            current_microsecond = now.microsecond

            if current_second < target_second:
                seconds_to_wait = (target_second - current_second) - (current_microsecond / 1_000_000)
            else:
                seconds_to_wait = (60 - current_second + target_second) - (current_microsecond / 1_000_000)

            if seconds_to_wait < 0:
                seconds_to_wait = 0

            time.sleep(seconds_to_wait)

            if self._stop_event.is_set():
                break

            print("fetching binance candles...")
            self.get_binance_data(255)  # Max limit needed for all calculations (15 * 16)
            self.calc_all_vol()

    def stop_scheduler(self):
        self._stop_event.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join()

    def calc_all_vol(self):
        self.garman_klass, self.sd, self.sdema, self.parkinson = [], [], [], []
        for i in range(16):
            self.ewm_span = (15 * (i+1))
            self.garman_klass.append(self.garman_klass_volatility())
            self.sd.append(self.standard_deviation_volatility())
            self.sdema.append(self.standard_deviation_ema_volatility())
            self.parkinson.append(self.parkinson_volatility())

        self.callback(self.garman_klass, self.sd, self.sdema, self.parkinson)


    def get_binance_data(self, limit):
        url = f"https://api.binance.com/api/v3/klines?symbol={self.symbol}&interval={self.interval}&limit={limit}"
        response = requests.get(url)
        candle_data = response.json()
        self.candle_data = candle_data

    def binance_update(self, price):
        self.binance_price = price
        self.calc_all_vol()

    def standard_deviation_ema_volatility(self):
        if self.binance_price is None or self.candle_data is None:
            return
        close_prices = pd.Series([float(candle[4]) for candle in self.candle_data])
        close_prices = pd.concat([close_prices, pd.Series([self.binance_price])])
        log_returns = np.log(close_prices / close_prices.shift(1)).dropna()
        ewm_std = log_returns.ewm(span=self.ewm_span, adjust=False).std().iloc[-1]
        intervals_per_year = 1440 * 365.25
        annualized_volatility = ewm_std * np.sqrt(intervals_per_year)
        return annualized_volatility

    def garman_klass_volatility(self):
        if self.binance_price is None or self.candle_data is None:
            return

        price_df = pd.DataFrame(self.candle_data,
                                columns=['Open_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close_time',
                                         'Quote_asset_volume', 'Number_of_trades', 'Taker_buy_base_asset_volume',
                                         'Taker_buy_quote_asset_volume', 'Ignore'])
        price_data = price_df[['Open', 'High', 'Low', 'Close']].apply(pd.to_numeric)

        last_idx = len(price_data) - 1
        price_data.loc[last_idx, 'High'] = max(price_data.loc[last_idx, 'High'], self.binance_price)
        price_data.loc[last_idx, 'Low'] = min(price_data.loc[last_idx, 'Low'], self.binance_price)
        price_data.loc[last_idx, 'Close'] = self.binance_price

        log_hl = (price_data["High"] / price_data["Low"]).apply(np.log)
        log_co = (price_data["Close"] / price_data["Open"]).apply(np.log)

        rs = 0.5 * log_hl ** 2 - (2 * math.log(2) - 1) * log_co ** 2

        trading_periods = 525960
        window = self.ewm_span

        def f(v):
            return (trading_periods * v.mean()) ** 0.5

        result = rs.rolling(window=window, center=False).apply(func=f, raw=False)
        final_volatility = result.dropna().iloc[-1]
        return final_volatility

    def parkinson_volatility(self):
        if self.binance_price is None or self.candle_data is None:
            return

        price_df = pd.DataFrame(self.candle_data,
                                columns=['Open_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close_time',
                                         'Quote_asset_volume', 'Number_of_trades', 'Taker_buy_base_asset_volume',
                                         'Taker_buy_quote_asset_volume', 'Ignore'])
        price_data = price_df[['Open', 'High', 'Low', 'Close']].apply(pd.to_numeric)

        last_idx = len(price_data) - 1
        price_data.loc[last_idx, 'High'] = max(price_data.loc[last_idx, 'High'], self.binance_price)
        price_data.loc[last_idx, 'Low'] = min(price_data.loc[last_idx, 'Low'], self.binance_price)

        rs = (1.0 / (4.0 * math.log(2.0))) * (
            (price_data["High"] / price_data["Low"]).apply(np.log)
        ) ** 2.0

        trading_periods = (365.25 * 24 * 60)  # Annualization factor for 1m data
        window = self.ewm_span

        def f(v):
            return (trading_periods * v.mean()) ** 0.5

        result = rs.rolling(window=window, center=False).apply(func=f, raw=False)
        final_volatility = result.dropna().iloc[-1]
        return final_volatility

    def standard_deviation_volatility(self):
        """Calculates annualized volatility using the rolling standard deviation of log returns."""
        if self.binance_price is None or self.candle_data is None:
            return

        close_prices = pd.Series([float(candle[4]) for candle in self.candle_data])
        close_prices = pd.concat([close_prices, pd.Series([self.binance_price], index=[len(close_prices)])])

        log_return = np.log(close_prices / close_prices.shift(1))

        trading_periods = (365.25 * 24 * 60)  # Annualization factor for 1m data
        window = self.ewm_span

        result = log_return.rolling(window=window, center=False).std() * math.sqrt(
            trading_periods
        )

        final_volatility = result.dropna().iloc[-1]
        return final_volatility