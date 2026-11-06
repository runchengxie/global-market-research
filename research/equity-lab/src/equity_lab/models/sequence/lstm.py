"""Independent implementation of full-window LSTM mixtures with real dispatch.

Architecture inspired by runchengxie/moe-lstm; original source is not copied.
PyTorch uses two LSTM biases, so match actual parameters instead of Keras formulas.
"""

import torch
from torch import nn


def routing(probabilities, top_k, equal=False):
    if equal:
        return torch.ones_like(probabilities) / probabilities.shape[-1]
    if top_k is None:
        return probabilities
    indices = probabilities.topk(top_k, dim=-1).indices
    weights = torch.zeros_like(probabilities).scatter(
        -1, indices, probabilities.gather(-1, indices)
    )
    # Top-1 retains softmax magnitude, preserving a task gradient for the router.
    return weights if top_k == 1 else weights / weights.sum(-1, keepdim=True)


def balance_loss(probabilities, weights):
    selected = (weights > 0).to(probabilities.dtype).detach()
    fractions = selected.sum(0) / selected.sum().clamp_min(1)
    return probabilities.shape[-1] * (fractions * probabilities.mean(0)).sum()


class SequenceModel(nn.Module):
    def __init__(
        self,
        features=10,
        lookback=20,
        units=64,
        experts=3,
        top_k=None,
        equal=False,
        shared_router=False,
    ):
        super().__init__()
        if min(features, lookback, units, experts) < 1 or (
            top_k is not None and not 1 <= top_k < experts
        ):
            raise ValueError("INVALID_MODEL_CONFIG")
        self.config = dict(
            kind="lstm",
            features=features,
            lookback=lookback,
            units=units,
            experts=experts,
            top_k=top_k,
            equal=equal,
            shared_router=shared_router,
        )
        self.experts = nn.ModuleList(
            [nn.LSTM(features, units, batch_first=True) for _ in range(experts)]
        )
        self.router = nn.Linear(features, experts)
        self.router_encoder = (
            nn.LSTM(features, features, batch_first=True) if shared_router else None
        )
        self.head = nn.Linear(lookback * units, 1)

    def forward(self, windows):
        context = (
            self.router_encoder(windows)[0][:, -1]
            if self.router_encoder
            else windows[:, -1]
        )
        probabilities = self.router(context).softmax(-1)
        weights = routing(probabilities, self.config["top_k"], self.config["equal"])
        combined = windows.new_zeros(
            (len(windows), self.config["lookback"] * self.config["units"])
        )
        processed, probes = [], []
        for index, expert in enumerate(self.experts):
            selected = torch.nonzero(weights[:, index] > 0, as_tuple=True)[0]
            processed.append(len(selected))
            if len(selected):
                representation = expert(windows.index_select(0, selected))[0].flatten(1)
                combined = combined.index_add(
                    0, selected, representation * weights[selected, index, None]
                )
                probes.append(representation.detach().mean(0))
            else:
                probes.append(combined.new_zeros(combined.shape[1]))
        return dict(
            logits=self.head(combined).squeeze(-1),
            probabilities=probabilities,
            weights=weights,
            processed=processed,
            probes=torch.stack(probes),
            auxiliary=balance_loss(probabilities, weights),
        )


def parameter_matched_width(config):
    def count(units, experts):
        return (
            experts * 4 * units * (config["features"] + units + 2)
            + config["features"] * experts
            + experts
            + config["lookback"] * units
            + 1
        )

    target = count(config["units"], config["experts"])
    return min(range(1, 1025), key=lambda u: abs(count(u, 1) - target))
