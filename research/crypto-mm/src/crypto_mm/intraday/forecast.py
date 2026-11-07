"""Pre-outcome forecasts from frozen price-only coefficients, without networking."""

import hashlib
import json
import math
from datetime import timedelta
from .inputs import read, sha, external, instant, PRODUCTS
from .features import price_features, NAMES
from .study import predict_model


def four_hour(rows):
    out = []
    for i, r in enumerate(rows):
        t = instant(r["time_open"])
        if t.hour % 4 or i + 4 > len(rows):
            continue
        group = rows[i : i + 4]
        if any(
            instant(v["time_open"]) != t + timedelta(hours=j)
            for j, v in enumerate(group)
        ):
            raise ValueError("FORECAST_GRID_GAP")
        out.append(
            dict(
                asset=r["asset"],
                time_open=r["time_open"],
                interval_end=group[-1]["interval_end"],
                open=r["open"],
                close=group[-1]["close"],
                high=max(v["high"] for v in group),
                low=min(v["low"] for v in group),
                volume=sum(v["volume"] for v in group),
            )
        )
    return out


def forecast_capture(capture, protocol, generated_at):
    generated = instant(generated_at)
    forecasts = []
    blocked = []
    for candidate, binding in protocol["models"].items():
        model_file = external(binding["file"])
        if sha(model_file) != binding["sha256"]:
            raise ValueError("FROZEN_CHECKPOINT_CHANGED")
        model = read(model_file)
        step = model["step_hours"]
        if (
            model["schema"] != "crypto.ridge_checkpoint.v1"
            or model["features"] != NAMES
            or model["arm"] != "price_only"
            or step not in [1, 4]
            or instant(model["fit_last_exit"]) >= instant(protocol["frozen_at"])
        ):
            raise ValueError("INVALID_FROZEN_MODEL")
        for asset in PRODUCTS:
            rows = capture["prices"][asset]
            for i, r in enumerate(rows):
                if (
                    r["asset"] != asset
                    or instant(r["interval_end"]) - instant(r["time_open"])
                    != timedelta(hours=1)
                    or (
                        i
                        and instant(r["time_open"])
                        != instant(rows[i - 1]["interval_end"])
                    )
                    or any(
                        not math.isfinite(r[k])
                        for k in ["open", "high", "low", "close", "volume"]
                    )
                ):
                    raise ValueError("INVALID_FORECAST_BARS")
            values = rows if step == 1 else four_hour(rows)
            features = price_features(values, step)
            if not features or features[-1] is None:
                blocked.append(candidate + ":" + asset + ":insufficient_history")
                continue
            cutoff = instant(values[-1]["interval_end"])
            entry = cutoff + timedelta(hours=step)
            exit = entry + timedelta(hours=step)
            if not cutoff <= generated < entry:
                blocked.append(candidate + ":" + asset + ":entry_deadline")
                continue
            x = features[-1]
            prediction = float(predict_model(model, [x])[0])
            feature_hash = hashlib.sha256(
                json.dumps(
                    dict(values=x, cutoff=cutoff.isoformat(), asset=asset),
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            forecasts.append(
                dict(
                    candidate=candidate,
                    asset=asset,
                    feature_cutoff=cutoff.isoformat(),
                    generated_at=generated.isoformat(),
                    entry_at=entry.isoformat(),
                    exit_at=exit.isoformat(),
                    prediction=prediction,
                    prior_prediction=model["y_mean"],
                    feature_sha256=feature_hash,
                    checkpoint_sha256=binding["sha256"],
                )
            )
    return dict(
        schema="crypto.forecast_candidates.v1", forecasts=forecasts, blocked=blocked
    )
