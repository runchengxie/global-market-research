"""Shared LSTM encoding followed by small genuinely dispatched FFN experts."""

import torch
from torch import nn
from .lstm import routing, balance_loss


class SharedEncoderMoE(nn.Module):
    def __init__(self, features=10, lookback=20, units=64, experts=3, top_k=2):
        super().__init__()
        self.config = dict(
            kind="shared_encoder",
            features=features,
            lookback=lookback,
            units=units,
            experts=experts,
            top_k=top_k,
        )
        self.encoder = nn.LSTM(features, units, batch_first=True)
        self.router = nn.Linear(units, experts)
        self.experts = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(units, units), nn.GELU(), nn.Linear(units, units)
                )
                for _ in range(experts)
            ]
        )
        self.head = nn.Linear(units, 1)

    def forward(self, windows):
        encoded = self.encoder(windows)[0][:, -1]
        p = self.router(encoded).softmax(-1)
        w = routing(p, self.config["top_k"])
        result = torch.zeros_like(encoded)
        counts, probes = [], []
        for i, expert in enumerate(self.experts):
            selected = torch.nonzero(w[:, i] > 0, as_tuple=True)[0]
            counts.append(len(selected))
            if len(selected):
                h = expert(encoded[selected])
                result = result.index_add(0, selected, h * w[selected, i, None])
                probes.append(h.detach().mean(0))
            else:
                probes.append(result.new_zeros(result.shape[-1]))
        return dict(
            logits=self.head(result).squeeze(-1),
            probabilities=p,
            weights=w,
            processed=counts,
            probes=torch.stack(probes),
            auxiliary=balance_loss(p, w),
        )
