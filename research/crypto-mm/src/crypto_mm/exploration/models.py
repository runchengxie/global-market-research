"""Small regression LSTM mixtures; equal and learned gates share parameter budgets."""

import torch
from torch import nn

KINDS = ["ridge", "single", "matched", "equal", "dense"]


def parameter_count(width, experts):
    return (
        experts * 4 * width * (7 + width + 2)
        + (7 * experts + experts if experts > 1 else 0)
        + 12 * width
        + 1
    )


def matched_width():
    target = parameter_count(8, 3)
    return min(range(8, 65), key=lambda n: abs(parameter_count(n, 1) - target))


class Model(nn.Module):
    def __init__(self, kind):
        super().__init__()
        if kind not in KINDS[1:]:
            raise ValueError("INVALID_MODEL")
        self.kind = kind
        width = matched_width() if kind == "matched" else 8
        experts = 3 if kind in ["equal", "dense"] else 1
        self.experts = nn.ModuleList(
            [nn.LSTM(7, width, batch_first=True) for _ in range(experts)]
        )
        self.router = nn.Linear(7, experts) if experts > 1 else None
        self.head = nn.Linear(12 * width, 1)

    def forward(self, x):
        gate = (
            self.router(x[:, -1]).softmax(-1)
            if self.router is not None
            else x.new_ones((len(x), 1))
        )
        if self.kind == "equal":
            gate = torch.ones_like(gate) / 3
        representations = torch.stack([e(x)[0].flatten(1) for e in self.experts], dim=1)
        return self.head((representations * gate[:, :, None]).sum(1)).squeeze(-1), gate
