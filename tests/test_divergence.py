from cton.divergence import detect_swings, find_divergences, find_latest_divergence

# Explicit RSI values keep these tests focused on the swing/divergence rules
# instead of on how a particular synthetic series moves the RSI indicator.

#            0   1   2  3   4   5   6  7   8
LOWS_PRICE = [10, 9, 8, 9, 10, 9, 7, 8, 9]
HIGHS_PRICE = [10, 11, 12, 11, 10, 11, 13, 12, 11]


def test_detect_swings_finds_lows_and_highs():
    rsi = [50] * len(LOWS_PRICE)
    swings = detect_swings(LOWS_PRICE, rsi, k=2)
    assert [(s.index, s.kind) for s in swings] == [(2, 'low'), (4, 'high'), (6, 'low')]


def test_bullish_divergence_lower_price_low_higher_rsi_low():
    rsi = [50, 40, 20, 40, 55, 45, 30, 45, 50]
    sig = find_latest_divergence('TEST', '1d', LOWS_PRICE, rsi, k=2)
    assert sig is not None
    assert sig.kind == 'bullish'
    assert (sig.price_prev, sig.price_last) == (8, 7)
    assert (sig.rsi_prev, sig.rsi_last) == (20, 30)
    assert sig.candle_index == 6


def test_bearish_divergence_higher_price_high_lower_rsi_high():
    rsi = [50, 60, 80, 60, 45, 55, 70, 55, 50]
    sig = find_latest_divergence('TEST', '4h', HIGHS_PRICE, rsi, k=2)
    assert sig is not None
    assert sig.kind == 'bearish'
    assert (sig.price_prev, sig.price_last) == (12, 13)
    assert sig.candle_index == 6


def test_no_divergence_when_rsi_confirms_price():
    rsi = [50, 40, 30, 40, 55, 45, 20, 45, 50]  # lower low in both price and RSI
    assert find_latest_divergence('TEST', '1d', LOWS_PRICE, rsi, k=2) is None
    assert find_divergences('TEST', '1d', LOWS_PRICE, rsi, k=2) == []
