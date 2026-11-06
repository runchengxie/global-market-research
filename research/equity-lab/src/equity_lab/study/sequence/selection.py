"""Fit-only feature-trajectory ablations; independent small SOM implementation."""

import numpy as np


def select_features(x, fit, mode="all"):
    if mode == "all":
        return list(range(x.shape[-1]))
    values = x[fit].reshape(-1, x.shape[-1]).astype(float)
    low = values.min(0)
    span = np.ptp(values, axis=0)
    values = (values - low) / np.where(span > 0, span, 1)
    points = values.T
    if mode == "correlation":
        chosen = []
        for i, point in enumerate(points):
            if np.std(point) == 0:
                continue
            if all(abs(np.corrcoef(point, points[j])[0, 1]) < 0.95 for j in chosen):
                chosen.append(i)
        return chosen or [0]
    if mode == "kmeans":
        from sklearn.cluster import KMeans
        from threadpoolctl import threadpool_limits

        with threadpool_limits(limits=2):
            model = KMeans(
                n_clusters=min(5, len(points)), random_state=42, n_init=10
            ).fit(points)
        centers, labels = model.cluster_centers_, model.labels_
    elif mode == "som":
        rng = np.random.default_rng(42)
        centers = points[rng.integers(0, len(points), size=9)].copy()
        grid = np.array([(i, j) for i in range(3) for j in range(3)])
        for step in range(100):
            point = points[rng.integers(len(points))]
            winner = np.argmin(((centers - point) ** 2).sum(1))
            decay = np.exp(-step / 100)
            neighborhood = np.exp(
                -((grid - grid[winner]) ** 2).sum(1) / (2 * (0.5 * decay) ** 2)
            )
            centers += (0.5 * decay * neighborhood[:, None]) * (point - centers)
        labels = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(2).argmin(1)
    else:
        raise ValueError("UNKNOWN_SELECTOR")
    chosen = []
    for cluster in sorted(set(labels)):
        members = np.flatnonzero(labels == cluster)
        chosen.append(
            int(members[((points[members] - centers[cluster]) ** 2).sum(1).argmin()])
        )
    return chosen
