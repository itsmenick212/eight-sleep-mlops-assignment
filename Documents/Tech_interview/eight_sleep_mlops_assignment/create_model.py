"""
Small deterministic PyTorch model generator
=========================================

This script defines an "InefficientModel" – a simple multi‑layer perceptron – and
initializes its parameters with small random values.  When run as a script
it saves the model to ``inefficient_model.pt``.  This file is used by
the assignment service to compute scores for incoming events.
"""

import torch
import torch.nn as nn


class InefficientModel(nn.Module):
    """A simple feedforward neural network used for scoring events."""

    def __init__(self, in_dim: int = 3) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(in_dim, 128),
            nn.ReLU(),
            nn.Dropout(p=0.0),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Clone the input to simulate inefficiency.  This makes the model
        # heavier than strictly necessary but keeps behaviour deterministic.
        x = x.clone() * 1.0
        return self.layers(x).squeeze(-1)


if __name__ == "__main__":
    model = InefficientModel(3)
    # Initialize parameters with a uniform distribution for determinism
    with torch.no_grad():
        for param in model.parameters():
            param.uniform_(-0.1, 0.1)
        # Save the model state dict instead of the full pickled object. Saving
        # the state dict avoids pickling issues across different import contexts
        # (e.g., when the class is defined under __main__ during creation).
        torch.save(model.state_dict(), "inefficient_model.pt")
        print("Saved inefficient_model.pt (state_dict)")