"""Explicit finite experiment families and preflight fit accounting."""

SEEDS = [11, 23, 37, 53, 71]
PRIMARY = [
    "cash",
    "holding",
    "momentum",
    "logistic",
    "lstm64",
    "matched",
    "equal",
    "ensemble",
    "dense",
    "sparse",
]
SECONDARY = [
    "matched",
    "equal",
    "top1",
    "shared_router",
    "shared_encoder",
    "drop_expert",
    "transformer_dense",
    "transformer_sparse",
]


def freeze_schedule(
    folds, seeds=None, candidates=None, max_fits=600, seconds=21600, epochs=50
):
    seeds = SEEDS if seeds is None else seeds
    candidates = PRIMARY if candidates is None else candidates
    if (
        type(folds) is not int
        or folds < 1
        or not seeds
        or not candidates
        or len(set(candidates)) != len(candidates)
        or not set(candidates) <= set(PRIMARY + SECONDARY)
        or len(set(seeds)) != len(seeds)
        or any(type(s) is not int for s in seeds)
        or not 1 <= max_fits <= 600
        or not 1 <= seconds <= 21600
        or not 1 <= epochs <= 50
    ):
        raise ValueError("INVALID_SCHEDULE")
    tasks, count = [], 0
    for fold in range(folds):
        for seed in seeds:
            for model in candidates:
                fits = (
                    0
                    if model in ["cash", "holding", "momentum"]
                    else 3
                    if model == "ensemble"
                    else 1
                )
                count += fits
                tasks.append(dict(fold=fold, seed=seed, model=model, fits=fits))
    if count > max_fits:
        raise ValueError("FIT_BUDGET_EXCEEDED")
    return dict(
        tasks=tasks,
        fits=count,
        max_fits=max_fits,
        seconds=seconds,
        epochs=epochs,
        batch_size=32,
        patience=5,
        seeds=seeds,
        candidates=candidates,
    )
