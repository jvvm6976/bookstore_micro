import torch
import torch.nn as nn

class LSTMModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=64, output_dim=100):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.fc(out)

# Mock inference function
def predict_next_product(user_behavior_tensor):
    """
    Mock inference function using the LSTM model.
    In a real scenario, the model would load trained weights via torch.load()
    and user_behavior_tensor would be a sequence of user interactions.
    """
    # Create an untrained instance just to demonstrate the architecture works
    model = LSTMModel()
    model.eval()
    
    with torch.no_grad():
        # output will be shape (batch_size, output_dim)
        predictions = model(user_behavior_tensor)
        
    return predictions
