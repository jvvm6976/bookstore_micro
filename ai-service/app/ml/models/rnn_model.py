from __future__ import annotations
import torch, torch.nn as nn
class RNNClassifier(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, num_layers=1, num_classes=10):
        super().__init__()
        self.rnn = nn.RNN(input_size=input_dim, hidden_size=hidden_dim, num_layers=num_layers,
                          batch_first=True, nonlinearity="tanh",
                          dropout=0.3 if num_layers > 1 else 0.0)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(hidden_dim, num_classes)
    def forward(self, x):
        out, _ = self.rnn(x)
        return self.fc(self.dropout(out[:, -1, :]))