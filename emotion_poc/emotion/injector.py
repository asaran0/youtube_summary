"""
emotion_poc/emotion/injector.py — Stage 2: Emotion tagging.

Input : plain text (paragraph or sentences)
Output: list of dicts  {"text": "...", "emotion": "CALM", "description": "..."}

Supported backends: rule_based | llm_based | passthrough
"""

import re


# ── Sentence splitter ─────────────────────────────────────────────────────────

def split_sentences(text: str) -> list[str]:
    """Split on Hindi/English sentence endings. Handles Devanagari danda (।)."""
    parts = re.split(r'(?<=[.!?।])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


# ── Rule-based backend ────────────────────────────────────────────────────────

# Hindi + English keywords → emotion
_RULES = {
    "INTENSE": [
        "हार", "संघर्ष", "कठिन", "मुश्किल", "struggle", "hard", "fight",
        "never give up", "कभी नहीं", "चुनौती", "challenge",
    ],
    "HOPEFUL": [
        "उम्मीद", "आशा", "hope", "सपना", "dream", "विश्वास", "believe",
        "एक दिन", "one day", "भविष्य", "future", "खिलेंगे", "bloom",
    ],
    "SAD": [
        "दुख", "तकलीफ", "रोया", "आँसू", "sad", "grief", "pain",
        "अकेला", "alone", "खो", "lost", "टूट",
    ],
    "EXCITED": [
        "खुशी", "जश्न", "जीत", "जीतना", "victory", "success", "wow",
        "amazing", "शानदार", "wonderful", "हर्ष",
    ],
    "CALM": [
        "शांति", "सुबह", "morning", "slowly", "धीरे", "gentle",
        "प्रकृति", "nature", "peace", "सुकून",
    ],
}

def _rule_based_emotion(sentence: str) -> str:
    s = sentence.lower()
    scores = {emotion: 0 for emotion in _RULES}
    for emotion, keywords in _RULES.items():
        for kw in keywords:
            if kw.lower() in s:
                scores[emotion] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "NEUTRAL"


def _inject_rule_based(sentences: list[str], cfg) -> list[dict]:
    result = []
    for sent in sentences:
        emotion = _rule_based_emotion(sent)
        result.append({
            "text":        sent,
            "emotion":     emotion,
            "description": cfg.EMOTION_MAP.get(emotion, cfg.EMOTION_MAP["NEUTRAL"]),
        })
    return result


# ── LLM-based backend ─────────────────────────────────────────────────────────

def _inject_llm_based(sentences: list[str], cfg) -> list[dict]:
    """Ask the LLM to tag each sentence. Slower but richer."""
    import json as _json
    from llm.generator import _generate_ollama, _generate_openai, _generate_mock

    emotions_list = ", ".join(cfg.EMOTION_MAP.keys())
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))

    prompt = f"""Tag each sentence below with one emotion from: {emotions_list}

Sentences:
{numbered}

Reply ONLY with a JSON array of objects with keys "index" (1-based) and "emotion".
Example: [{{"index": 1, "emotion": "CALM"}}, {{"index": 2, "emotion": "INTENSE"}}]"""

    try:
        backend = cfg.LLM_BACKEND.lower()
        if backend == "ollama":
            raw = _generate_ollama(prompt, cfg)
        elif backend == "openai":
            raw = _generate_openai(prompt, cfg)
        else:
            raw = _generate_mock(prompt, cfg)

        # Extract JSON from response
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        tags = _json.loads(match.group()) if match else []
        tag_map = {t["index"]: t["emotion"] for t in tags}
    except Exception as e:
        print(f"[emotion] LLM tagging failed ({e}), falling back to rule-based")
        return _inject_rule_based(sentences, cfg)

    result = []
    for i, sent in enumerate(sentences, 1):
        emotion = tag_map.get(i, "NEUTRAL")
        if emotion not in cfg.EMOTION_MAP:
            emotion = "NEUTRAL"
        result.append({
            "text":        sent,
            "emotion":     emotion,
            "description": cfg.EMOTION_MAP[emotion],
        })
    return result


# ── Passthrough backend ───────────────────────────────────────────────────────

def _inject_passthrough(sentences: list[str], cfg) -> list[dict]:
    return [
        {"text": s, "emotion": "NEUTRAL",
         "description": cfg.EMOTION_MAP.get("NEUTRAL", "")}
        for s in sentences
    ]


# ── Public entry point ────────────────────────────────────────────────────────

def inject(text: str, cfg) -> list[dict]:
    """
    Run stage 2: split text into sentences and tag each with an emotion.

    Returns list of:
        {"text": str, "emotion": str, "description": str}

    The "description" field is the Parler-TTS voice style string for that emotion.
    Other TTS backends can ignore it and just use "emotion" for style selection.
    """
    sentences = split_sentences(text)
    backend   = cfg.EMOTION_BACKEND.lower()

    print(f"[emotion] backend={backend}  {len(sentences)} sentences")

    if backend == "rule_based":
        tagged = _inject_rule_based(sentences, cfg)
    elif backend == "llm_based":
        tagged = _inject_llm_based(sentences, cfg)
    elif backend == "passthrough":
        tagged = _inject_passthrough(sentences, cfg)
    else:
        raise ValueError(f"Unknown EMOTION_BACKEND: {backend!r}. "
                         "Choose: rule_based | llm_based | passthrough")

    # Summary log
    from collections import Counter
    counts = Counter(t["emotion"] for t in tagged)
    print(f"[emotion] tags: {dict(counts)}")
    return tagged
