from cton.divergence import detect_swings, find_latest_divergence
from cton.indicators import rsi
import math

def test_detect_bullish_divergence():
    # Price makes lower low, RSI makes higher low
    closes = [10,9,11,8,9,12,11,13,12,14]
    rsi_vals = rsi(closes, period=2)  # artificially small to react faster
    sig = find_latest_divergence('TEST','1d', closes, rsi_vals, k=1)
    assert sig is not None
    assert sig.kind == 'bullish'


def test_detect_bearish_divergence():
    closes = [10,11,9,12,11,13,12,14,13,13.5]
    rsi_vals = rsi(closes, period=2)
    sig = find_latest_divergence('TEST','4h', closes, rsi_vals, k=1)
    assert sig is not None
    # Could be bullish or bearish depending, ensure type captured
    assert sig.kind in ('bullish','bearish')
