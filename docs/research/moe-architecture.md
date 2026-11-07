# MoE and LSTM, explained visually

[简体中文](moe-architecture.zh-CN.md) · [Interactive topic](https://runchengxie.github.io/global-market-research/research/moe-architecture/)

The independent teaching topic explains a window of history, last-row routing, complete LSTM experts, weighted hidden representations and one shared output head. Existing stock and crypto research pages link to it without replacing their evidence or charts. The related CNN link does not imply the CNN study uses MoE.

Play one pass, pause, step backward/forward, choose any numbered stage, or switch the toy history and routing mode. Expert buttons open a small LSTM memory lens. Dense and equal modes process every expert; top-2 dispatch skips the unselected expert. Equal allocation is fixed. Hidden notes are not three independently calibrated probabilities.

Every input, gate, note and score is handcrafted. Five input cards and two displayed note coordinates compress much larger real tensors. The scalar memory lens illustrates the LSTM cell/hidden-state equations separately from those note coordinates. It is not a trained forward pass, economic explanation of neurons, research result or investment forecast. Actual research uses its own windows, features, dimensions and targets.

Motion runs once when the diagram enters view, pauses offscreen or in a hidden tab, and respects reduced-motion preferences both at load and when changed. Manual steps remain available with reduced motion. Without scripts the page retains a full static overview and six-step text explanation. No model, training, provider request or research snapshot is changed.
