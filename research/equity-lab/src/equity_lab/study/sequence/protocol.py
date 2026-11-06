"""Frozen rolling blocks with label-availability purge and a session embargo."""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Fold:
    fit: np.ndarray
    validation: np.ndarray
    test: np.ndarray
    fit_cutoff: pd.Timestamp
    selection_cutoff: pd.Timestamp
    ready_ts: pd.Timestamp
    first_test: str


def make_folds(samples, fit=400, validation=80, test=63, minimum_test=20):
    if any(type(n) is not int or n < 1 for n in [fit, validation, test, minimum_test]):
        raise ValueError("INVALID_FOLD_LENGTH")
    a = samples.audit
    dates = sorted(a.feature_end.unique())
    folds = []
    for start in range(fit + validation, len(dates), test):
        test_dates = dates[start : start + test]
        if len(test_dates) < minimum_test:
            break
        # One signal session is embargoed before each subsequent segment.
        fit_dates = dates[start - validation - fit : start - validation - 1]
        val_dates = dates[start - validation : start - 1]
        fit_cut = a.loc[a.feature_end == val_dates[0], "signal_ts"].min()
        select_cut = a.loc[a.feature_end == test_dates[0], "signal_ts"].min()
        fi = np.flatnonzero(
            a.feature_end.isin(fit_dates) & (a.label_available_ts < fit_cut)
        )
        vi = np.flatnonzero(
            a.feature_end.isin(val_dates) & (a.label_available_ts < select_cut)
        )
        if not len(fi) or not len(vi):
            continue
        ready = max(
            a.iloc[fi].label_available_ts.max(), a.iloc[vi].label_available_ts.max()
        ) + pd.Timedelta(hours=12)
        ti = np.flatnonzero(a.feature_end.isin(test_dates) & (a.entry_ts > ready))
        if a.iloc[ti].feature_end.nunique() >= minimum_test:
            folds.append(Fold(fi, vi, ti, fit_cut, select_cut, ready, test_dates[0]))
    if not folds:
        raise ValueError("NO_ELIGIBLE_FOLDS")
    return folds
