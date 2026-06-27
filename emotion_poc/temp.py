import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer

device = "mps" if torch.backends.mps.is_available() else "cpu"
print("Device:", device)

model_name = "RXD03/indic-parler-tts"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_name)

print("Loading model...")
model = ParlerTTSForConditionalGeneration.from_pretrained(
    model_name
).to(device)

print("Loaded successfully!")