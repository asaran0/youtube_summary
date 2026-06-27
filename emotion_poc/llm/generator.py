"""
emotion_poc/llm/generator.py — Stage 1: Script generation via LLM.

Supported backends: ollama | llama_cpp | openai | mock
To add a new backend: add an elif branch in generate() — nothing else to change.
"""

import json
import os


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(cfg) -> str:
    style_map = {
        "story":        "a short motivational Hindi story",
        "speech":       "a short motivational speech",
        "book_summary": "an engaging audio book summary",
    }
    style = style_map.get(cfg.CONTENT_TYPE, "a short story")
    lang_instruction = {
        "hi":  "Write entirely in Hindi (Devanagari script).",
        "en":  "Write in English.",
        "hig": "Write in Hinglish (mix Hindi Devanagari and English naturally).",
    }.get(cfg.LANGUAGE, "Write in Hindi.")

    return f"""You are a professional scriptwriter. Write {style} about: {cfg.TOPIC}

{lang_instruction}
Target length: approximately {cfg.TARGET_WORDS} words.
Write naturally flowing paragraphs — no headers, no bullet points, no markdown.
Output only the story/speech text, nothing else."""


# ── Backend implementations ───────────────────────────────────────────────────

def _generate_ollama(prompt: str, cfg) -> str:
    import urllib.request
    payload = json.dumps({
        "model":  cfg.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": cfg.TARGET_WORDS * 3},
    }).encode()
    req = urllib.request.Request(
        f"{cfg.OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["response"].strip()


def _generate_llama_cpp(prompt: str, cfg) -> str:
    try:
        from llama_cpp import Llama
    except ImportError:
        raise RuntimeError(
            "llama-cpp-python not installed.\n"
            "Install: pip install llama-cpp-python --extra-index-url "
            "https://abetlen.github.io/llama-cpp-python/whl/metal"
        )
    llm = Llama(
        model_path=cfg.LLAMA_CPP_MODEL_PATH,
        n_gpu_layers=cfg.LLAMA_CPP_N_GPU_LAYERS,
        n_ctx=cfg.LLAMA_CPP_N_CTX,
        verbose=False,
    )
    out = llm(prompt, max_tokens=cfg.TARGET_WORDS * 4, temperature=0.8)
    return out["choices"][0]["text"].strip()


def _generate_openai(prompt: str, cfg) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    api_key  = cfg.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")
    base_url = cfg.OPENAI_BASE_URL or None
    client   = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=cfg.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=cfg.TARGET_WORDS * 4,
        temperature=0.8,
    )
    return resp.choices[0].message.content.strip()


def _generate_mock(prompt: str, cfg) -> str:
    """Returns hardcoded sample text — useful to test emotion/TTS stages alone."""
    if cfg.LANGUAGE == "hi":
        return (
            "एक छोटे से गाँव में राम नाम का किसान रहता था। "
            "उसकी ज़मीन सूखी थी, पर उसका हौसला नहीं। "
            "हर सुबह वह उठता और खेत में काम करता। "
            "लोग कहते — इस ज़मीन पर कुछ नहीं उगेगा। "
            "पर राम मुस्कुराता और कहता — देखना, एक दिन यहाँ फूल खिलेंगे। "
            "साल बीते। मेहनत रंग लाई। "
            "जहाँ कभी धूल थी, वहाँ अब हरियाली थी। "
            "राम की कहानी पूरे गाँव के लिए प्रेरणा बन गई।"
        )
    return (
        "In a small village lived a farmer named Ram. "
        "His land was dry, but his spirit was not. "
        "Every morning he rose and worked the fields. "
        "People said nothing would grow here. "
        "But Ram smiled and said — one day flowers will bloom. "
        "Years passed. His hard work paid off. "
        "Where dust once lay, green fields now spread. "
        "Ram's story became an inspiration for the entire village."
    )


# ── Public entry point ────────────────────────────────────────────────────────

def generate(cfg) -> str:
    """
    Run stage 1: generate script text.
    Returns raw text string.
    Raises RuntimeError with a clear message if the backend is unavailable.
    """
    prompt = _build_prompt(cfg)
    backend = cfg.LLM_BACKEND.lower()

    print(f"[llm] backend={backend}  topic={cfg.TOPIC[:50]}")

    if backend == "ollama":
        text = _generate_ollama(prompt, cfg)
    elif backend == "llama_cpp":
        text = _generate_llama_cpp(prompt, cfg)
    elif backend == "openai":
        text = _generate_openai(prompt, cfg)
    elif backend == "mock":
        text = _generate_mock(prompt, cfg)
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {backend!r}. "
                         "Choose: ollama | llama_cpp | openai | mock")

    print(f"[llm] generated {len(text.split())} words")
    return text
