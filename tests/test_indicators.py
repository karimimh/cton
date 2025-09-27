from cton.indicators import rsi
import math

def test_rsi_basic_monotonic_up():
    prices = [i for i in range(0, 30)]  # strictly increasing
    values = rsi(prices, period=14)
    # After enough periods RSI should approach 100
    assert values[-1] > 90

def test_rsi_constant_series():
    prices = [100.0]*40
    values = rsi(prices, period=14)
    # RSI should be 100 when losses are zero by our implementation
    # (Some definitions set to 50; acceptable for notification context.)
    assert math.isclose(values[-1], 100.0, rel_tol=1e-6)
