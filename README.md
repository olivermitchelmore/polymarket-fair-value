# Polymarket Fair Value

Prices a Polymarket "Bitcoin up or down" market with Black-Scholes and compares the result with the market's live order book.

> This project was written in July 2025 as an experiment and published in October 2026 as an archive. It is not maintained and the pinned libraries are out of date.

## How it works

1. Streams the Bitcoin price from Binance and the market's order book from Polymarket over WebSockets.
2. Fetches 1-minute Binance candles once a minute.
3. Estimates annualised volatility four ways (Garman-Klass, Parkinson, standard deviation, exponentially weighted standard deviation) over 16 lookback windows from 15 to 240 minutes.
4. Turns each estimate into a fair value for the market: the Black-Scholes probability that the price finishes above the strike.
5. Prints every fair value and the estimator and window closest to the order book mid price.

It only prints. It places no orders.

## Run

```sh
pip install -r requirements.txt
python main.py
```

The market slug and strike price are hard-coded in `main.py`. Change both to a live market first.

## Licence

GPL-3.0. See `LICENSE`.
