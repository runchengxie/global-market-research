"""State-dict checkpoints with architecture metadata; no executable pickle loads."""

import torch


def build_model(config):
    config = config.copy()
    kind = config.pop("kind", "lstm")
    if kind == "lstm":
        from .lstm import SequenceModel

        return SequenceModel(**config)
    if kind == "shared_encoder":
        from .shared import SharedEncoderMoE

        return SharedEncoderMoE(**config)
    if kind == "transformer":
        from .transformer import SequenceTransformer

        return SequenceTransformer(**config)
    raise ValueError("UNKNOWN_MODEL_KIND")


def save_checkpoint(model, path, metadata):
    torch.save(
        dict(config=model.config, state=model.state_dict(), metadata=metadata), path
    )


def load_checkpoint(path):
    saved = torch.load(path, weights_only=True, map_location="cpu")
    model = build_model(saved["config"])
    model.load_state_dict(saved["state"])
    model.eval()
    return model, saved["metadata"]
