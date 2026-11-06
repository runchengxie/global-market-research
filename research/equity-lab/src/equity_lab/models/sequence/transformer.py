"""Small historical-window Transformer, with token-level FFN dispatch."""

import torch
from torch import nn
from .lstm import routing, balance_loss


class TokenExperts(nn.Module):
    def __init__(self, width, top_k):
        super().__init__()
        self.router = nn.Linear(width, 4)
        self.experts = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(width, width * 2), nn.GELU(), nn.Linear(width * 2, width)
                )
                for _ in range(4)
            ]
        )
        self.top_k = top_k

    def forward(self, x):
        shape = x.shape
        flat = x.reshape(-1, shape[-1])
        probs = self.router(flat).softmax(-1)
        weights = routing(probs, self.top_k)
        result = torch.zeros_like(flat)
        processed = []
        for i, expert in enumerate(self.experts):
            selected = torch.nonzero(weights[:, i] > 0, as_tuple=True)[0]
            processed.append(len(selected))
            if len(selected):
                result = result.index_add(
                    0, selected, expert(flat[selected]) * weights[selected, i, None]
                )
        return result.reshape(shape), probs, weights, processed


class SequenceTransformer(nn.Module):
    def __init__(self, features=10, lookback=60, top_k=2, width=64):
        super().__init__()
        self.config = dict(
            kind="transformer",
            features=features,
            lookback=lookback,
            top_k=top_k,
            width=width,
        )
        self.embed = nn.Linear(features, width)
        self.position = nn.Parameter(torch.zeros(1, lookback, width))
        self.attention = nn.ModuleList(
            [nn.MultiheadAttention(width, 4, batch_first=True) for _ in range(2)]
        )
        self.norms = nn.ModuleList([nn.LayerNorm(width) for _ in range(4)])
        self.ffn = nn.ModuleList([TokenExperts(width, top_k) for _ in range(2)])
        self.head = nn.Linear(width, 1)

    def forward(self, windows):
        x = self.embed(windows) + self.position
        processed, probabilities, weights, losses = [], [], [], []
        for i, (attention, ffn) in enumerate(zip(self.attention, self.ffn)):
            x = self.norms[2 * i](x + attention(x, x, x, need_weights=False)[0])
            y, p, w, counts = ffn(x)
            x = self.norms[2 * i + 1](x + y)
            processed.extend(counts)
            probabilities.append(p)
            weights.append(w)
            losses.append(balance_loss(p, w))
        return dict(
            logits=self.head(x[:, -1]).squeeze(-1),
            probabilities=torch.cat(probabilities),
            weights=torch.cat(weights),
            processed=processed,
            probes=x.detach().mean(0),
            auxiliary=torch.stack(losses).mean(),
        )
