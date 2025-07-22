from polydata.calculator import Calculator
import time


def main():
    sol_slug = "bitcoin-up-or-down-july-22-5am-et"
    sol_symbol = "btcusdt"
    solana_calculator = Calculator(sol_slug, 118290.0, sol_symbol)
    solana_calculator.initialize()

    while True: time.sleep(1)

if __name__ == "__main__":
    main()