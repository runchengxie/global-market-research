"""Within-symbol windows with explicit label and hypothetical availability clocks."""

from dataclasses import dataclass
import numpy as np
import pandas as pd

FEATURES = [
    "return",
    "ma5_deviation",
    "ma20_deviation",
    "gap",
    "range",
    "intraday",
    "rsi",
    "macd",
    "volatility",
    "relative_volume",
]


@dataclass
class SampleSet:
    x: np.ndarray
    audit: pd.DataFrame
    features: list


def feature_frame(bars):
    close = bars.close
    ret = close.pct_change(fill_method=None)
    change = close.diff()
    gain = change.clip(lower=0).rolling(14).mean()
    loss = (-change.clip(upper=0)).rolling(14).mean()
    rsi = gain / (gain + loss)
    rsi = rsi.mask((gain + loss) == 0, 0.5)
    return pd.DataFrame(
        dict(
            return_=ret,
            ma5_deviation=close / close.rolling(5).mean() - 1,
            ma20_deviation=close / close.rolling(20).mean() - 1,
            gap=bars.open / close.shift() - 1,
            range_=(bars.high - bars.low) / close,
            intraday=(close - bars.open) / bars.open,
            rsi=rsi,
            macd=(
                close.ewm(span=12, adjust=False).mean()
                - close.ewm(span=26, adjust=False).mean()
            )
            / close,
            volatility=ret.rolling(20).std(),
            relative_volume=bars.volume
            / bars.volume.shift().rolling(20).mean().replace(0, np.nan),
        )
    ).rename(columns={"return_": "return", "range_": "range"})[FEATURES]


def build_samples(snapshot, lookback=20, symbols=None):
    if type(lookback) is not int or lookback < 1:
        raise ValueError("INVALID_LOOKBACK")
    symbols = symbols or snapshot.manifest["spec"]["products"]
    arrays, records = [], []
    sessions = snapshot.schedule.index.tolist()
    for symbol in symbols:
        bars = snapshot.frames[symbol]
        features = feature_frame(bars).to_numpy(dtype=float)
        for end in range(lookback - 1, len(bars) - 2):
            window = features[end - lookback + 1 : end + 1]
            if not np.isfinite(window).all():
                continue
            start, day, entry, exit_day = (
                sessions[i] for i in [end - lookback + 1, end, end + 1, end + 2]
            )
            entry_price, exit_price = (
                bars.loc[entry, "open"],
                bars.loc[exit_day, "open"],
            )
            forward = exit_price / entry_price - 1
            arrays.append(window)
            records.append(
                dict(
                    symbol=symbol,
                    feature_start=start,
                    feature_end=day,
                    available_ts=snapshot.schedule.loc[day, "close"]
                    + pd.Timedelta(minutes=15),
                    signal_ts=snapshot.schedule.loc[day, "close"]
                    + pd.Timedelta(minutes=15),
                    entry_session=entry,
                    exit_session=exit_day,
                    entry_ts=snapshot.schedule.loc[entry, "open"],
                    exit_ts=snapshot.schedule.loc[exit_day, "open"],
                    label_available_ts=snapshot.schedule.loc[exit_day, "open"],
                    entry_price=float(entry_price),
                    exit_price=float(exit_price),
                    forward_return=float(forward),
                    target=int(forward > 0.002),
                )
            )
    if not arrays:
        raise ValueError("NO_ELIGIBLE_SAMPLES")
    audit = pd.DataFrame(records)
    order = audit.sort_values(["feature_end", "symbol"]).index.to_numpy()
    return SampleSet(
        np.asarray(arrays, dtype=np.float32)[order],
        audit.iloc[order].reset_index(drop=True),
        FEATURES.copy(),
    )
