import torch
from transformers import pipeline

device = "mps" if torch.backends.mps.is_available() else "cpu"
print("Device:", device)

pipe = pipeline(
    "text-to-speech",
    model="RXD03/indic-parler-tts"
)

print("Model loaded successfully!")