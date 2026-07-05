"""
core/lang/roman_hindi.py — Roman-script Hinglish preprocessor for TTS.

Used ONLY when cfg.LANGUAGE == "hig" AND the TTS backend is Kokoro (or any
English-voice backend).  Input is Roman-script Hinglish like:

    "Microservices ek architectural style hai jisme hum ek bade application
     ko multiple chhote-chhote independent services me divide kar dete hain."

The English voice handles English technical terms natively.  The Hindi
connectors and verb forms need phonetic nudges so the English voice
pronounces them the way a Hindi speaker would expect, not the way the
English lexicon would decode them.

Design principles
─────────────────
• Only touch Hindi words — English technical terms (microservices,
  deployment, scalability, gRPC …) are left exactly as-is.
• Map word-by-word, case-insensitively, whole-word only.
• Compound/hyphenated tokens are not split — they're left as-is, which is
  usually fine ("loosely-coupled", "e-commerce").
• The map is intentionally conservative: if we're not sure a substitution
  helps, we leave the word alone (English TTS's guess is often acceptable).
• Other modes (en, hi) never call anything in this file.
"""

import re

# ─────────────────────────────────────────────────────────────────────────────
#  PHONETIC MAP  —  Roman Hindi word  →  English-TTS-friendly phonetic form
#
#  Reading guide for the right-hand side:
#    "ay"  = the vowel in "pay"
#    "ee"  = the vowel in "feet"
#    "oo"  = the vowel in "food"
#    "uh"  = schwa as in "about"
#    "oh"  = the vowel in "go"
#    "ow"  = the vowel in "now"  (used sparingly)
#
#  Only include words where the English TTS default would be noticeably
#  wrong.  Entries are grouped by grammatical / semantic category.
# ─────────────────────────────────────────────────────────────────────────────
ROMAN_HINDI_PHONETICS: dict[str, str] = {

    # ── Copula / existence ───────────────────────────────────────────────────
    "hai":      "hay",       # है  — English reads as "hi" (greeting)
    "hain":     "hain",      # हैं — acceptable as-is
    "hoga":     "hogaa",
    "hogi":     "hogee",
    "hoge":     "hogay",
    "tha":      "thaa",      # था
    "thi":      "thee",      # थी  — English reads as "thy"
    "the":      "thay",      # थे  — English reads as "thee" (article)
    "hota":     "hota",      # होता — OK
    "hoti":     "hotee",     # होती
    "hote":     "hotay",     # होते
    "hona":     "hona",      # होना — OK

    # ── Postpositions / case markers ─────────────────────────────────────────
    "me":       "meh",       # में  — English reads as "me" (pronoun, "mee")
    "mein":     "meh",       # में  — variant spelling
    "ke":       "kay",       # के   — English "key"
    "ki":       "kee",       # की   — English "ky"/"kai"
    "ka":       "kaa",       # का   — English "ka" OK-ish; lengthen for clarity
    "ko":       "koh",       # को   — English "koh" OK
    "se":       "say",       # से   — English "see"
    "par":      "pur",       # पर   — English "par" (golf term)
    "pe":       "pay",       # पे   — English "pee"
    "tak":      "tuk",       # तक
    "ne":       "neh",       # ने   — English "nee" or "knee"
    "hi":       "hee",       # ही   — English "hi" (greeting)
    "bhi":      "bhee",      # भी   — English would mangle "bhi"
    "ya":       "yaa",       # या   — English "ya" OK, lengthen
    "ya":       "yaa",
    "bina":     "bina",      # बिना — OK

    # ── Conjunctions / discourse markers ────────────────────────────────────
    "aur":      "or",        # और   — near-homophone of English "or"
    "lekin":    "lekin",     # लेकिन — OK
    "kyunki":   "kyunkee",   # क्योंकि
    "isliye":   "isleeyeh",  # इसलिए
    "to":       "toh",       # तो   — English "to"/"too" (wrong vowel)
    "agar":     "ugur",      # अगर  — "uh-gur" not "ay-gar"
    "jabki":    "jubkee",    # जबकि
    "jabtak":   "jubtuk",    # जबतक
    "jaise":    "jaisay",    # जैसे
    "jab":      "jub",       # जब   — English "jab" (punch) has short vowel
    "tab":      "tub",       # तब   — English "tab" OK but lengthened
    "phir":     "phir",      # फिर  — OK
    "phir":     "phir",
    "jo":       "jo",        # जो   — OK
    "kyun":     "kyoon",     # क्यों
    "kaise":    "kaisay",    # कैसे
    "fir":      "phir",      # alternate spelling

    # ── Common pronouns / demonstratives ────────────────────────────────────
    "yeh":      "yeh",       # यह/ये — OK
    "ye":       "yeh",
    "woh":      "voh",       # वह   — English "woh" nonstandard
    "wo":       "voh",       # वो   — variant
    "hum":      "hum",       # हम   — OK
    "aap":      "aap",       # आप   — OK
    "iska":     "iska",      # इसका — OK
    "iski":     "iskee",
    "iske":     "iskay",
    "uska":     "uska",
    "uski":     "uskee",
    "uske":     "uskay",
    "unka":     "unka",
    "unki":     "unkee",
    "unke":     "unkay",
    "unko":     "unkoh",

    # ── Quantifiers / degree ────────────────────────────────────────────────
    "ek":       "uk",        # एक   — "eck" sounds like disgust; "uk" is closer
    "do":       "doh",       # दो   — English "do" (musical note / verb)
    "sab":      "sub",       # सब   — English "sab" (abbreviation) wrong
    "koi":      "koyee",     # कोई  — English "coy"
    "kuch":     "kuch",      # कुछ  — OK
    "bahut":    "bahoot",    # बहुत — English "ba-hut" wrong
    "zyada":    "zyaada",    # ज़्यादा
    "kam":      "kum",       # कम   — English "cam" wrong
    "sirf":     "sirf",      # सिर्फ — OK
    "bilkul":   "bilkul",    # बिल्कुल — OK
    "kaafi":    "kaafee",    # काफी
    "kafi":     "kaafee",
    "thoda":    "thoda",     # थोड़ा — OK
    "thodi":    "thodee",
    "puri":     "pooree",    # पूरी  — English "pyoo-ree" wrong
    "poori":    "pooree",
    "poora":    "poora",     # OK

    # ── Verbs — infinitive / stem ────────────────────────────────────────────
    "karna":    "kurna",     # करना
    "karte":    "kartay",    # करते
    "karti":    "kartee",    # करती
    "karta":    "karta",     # OK
    "karke":    "kurkay",    # करके
    "karna":    "kurna",
    "karo":     "kuroh",
    "kare":     "kuray",
    "kiya":     "kiya",      # OK
    "kiye":     "kiyay",
    "kiya":     "kiya",
    "dena":     "dayna",     # देना
    "dete":     "daytay",    # देते
    "deti":     "daytee",
    "deta":     "dayta",
    "lena":     "layna",     # लेना
    "lete":     "laytay",
    "jana":     "jaana",     # जाना
    "jata":     "jaata",
    "jati":     "jaatee",
    "aana":     "aana",      # आना — OK
    "aata":     "aata",
    "rehna":    "rayhna",    # रहना
    "rehte":    "rayhtay",
    "rehti":    "rayhtee",
    "rakhna":   "rukna",     # रखना
    "rakhte":   "ruktay",
    "bolna":    "bolna",     # बोलना — OK
    "bolein":   "bolain",    # बोलें
    "sunna":    "sunna",     # सुनना — OK
    "chalana":  "chalana",   # OK
    "chalate":  "chalatay",
    "milna":    "milna",     # OK
    "milkar":   "milkur",    # मिलकर
    "milte":    "miltay",
    "banana":   "banana",    # बनाना — same as fruit, OK here
    "banate":   "banatay",
    "banane":   "bananay",
    "chalana":  "chalana",

    # ── Adjectives / descriptors ────────────────────────────────────────────
    "bada":     "bada",      # OK
    "badi":     "badee",
    "bade":     "baday",
    "chhota":   "chhota",    # OK
    "chhoti":   "chhotee",
    "chhote":   "chhotay",
    "naya":     "naya",      # OK
    "nayi":     "nayee",
    "purana":   "purana",    # OK
    "alag":     "alag",      # OK
    "mushkil":  "mushkil",   # OK
    "aasaan":   "aasaan",    # OK
    "simple":   "simple",    # English — leave as-is
    "important": "important",

    # ── Common nouns in Hinglish conversation ───────────────────────────────
    "matlab":   "mutlub",    # मतलब — English "mat-lab" sounds like MATLAB
    "wajah":    "waajuh",    # वजह
    "fayda":    "fayda",     # OK
    "kaam":     "kaam",      # OK
    "cheez":    "cheez",     # OK (sounds like "cheese")
    "taraf":    "taraf",     # OK
    "zaruri":   "zaroree",   # ज़रूरी
    "zaroorat": "zarorat",
    "maahol":   "maahol",
    "tarike":   "tarikaay",  # तरीके
    "tarika":   "tarika",    # OK
    "khayal":   "khayaal",
    "naam":     "naam",      # OK
    "khabar":   "khabar",    # OK

    # ── Negation ────────────────────────────────────────────────────────────
    "nahi":     "nahee",     # नहीं — English "nah-hi" wrong
    "nahin":    "naheen",
    "mat":      "mut",       # मत   — English "mat" (doormat)

    # ── Time / sequence ─────────────────────────────────────────────────────
    "pehle":    "pehlay",    # पहले
    "baad":     "baad",      # OK
    "abhi":     "ubhee",     # अभी
    "ab":       "ub",        # अब
    "kabhi":    "kabhee",    # कभी
    "hamesha":  "hamesha",   # OK
    "aakhir":   "aakhir",    # OK
    "tabhi":    "tubhee",    # तभी
    "isi":      "isee",      # इसी
    "isi":      "isee",
    "yahi":     "yahee",     # यही
    "wahi":     "vahee",     # वही

    # ── More verb conjugations (from interview QA patterns) ─────────────────
    "karne":    "kurnay",    # करने
    "karne":    "kurnay",
    "karni":    "kurnee",
    "padega":   "padayga",   # पड़ेगा
    "padegi":   "padaygee",  # पड़ेगी
    "padenge":  "padayngay",
    "padta":    "pudta",
    "padti":    "pudtee",
    "padna":    "pudna",
    "padna":    "pudna",
    "rakhna":   "rukna",
    "rakhte":   "ruktay",
    "rakhti":   "ruktee",
    "bolta":    "bolta",
    "bolte":    "boltay",
    "bolti":    "boltee",
    "bolein":   "bolain",
    "chahiye":  "chahiyeh",  # चाहिए
    "chahte":   "chaahtay",
    "chahti":   "chaahtee",
    "sakta":    "sukta",     # सकता
    "sakti":    "suktee",
    "sakte":    "suktay",
    "sakein":   "sukain",
    "bana":     "bana",
    "banai":    "banayee",
    "banate":   "banatay",
    "banati":   "banatee",
    "doosri":   "doosree",   # दूसरी
    "doosra":   "doosra",
    "doosre":   "doosray",
    "jisme":    "jismeh",    # जिसमें
    "jisme":    "jismeh",
    "jisne":    "jisneh",
    "jisko":    "jiskoh",
    "jinka":    "jinkaa",
    "jinke":    "jinkay",
    "jinki":    "jinkee",
    "unhe":     "unhay",     # उन्हें
    "unhen":    "unhen",
    "inhe":     "inhay",
    "use":      "usay",      # उसे  — English "use" (verb) is wrong
    "ise":      "isay",      # इसे
    "har":      "hur",       # हर   — "every"
    "puri":     "pooree",
    "bhi":      "bhee",
    "aise":     "aisay",     # ऐसे
    "aisa":     "aisa",
    "waisa":    "waisa",
    "zarurat":  "zarorat",   # ज़रूरत
    "zaroorat": "zarorat",

    # ── Hinglish sentence connectors ────────────────────────────────────────
    "matlab":   "mutlub",    # duplicate kept for clarity (was above)
    "yani":     "yaanee",    # यानी = "that is"
    "warna":    "warna",     # OK
    "phir":     "phir",
    "dono":     "donoh",     # दोनों = both
    "sabhi":    "subhee",    # सभी = all
    "kisi":     "kisee",     # किसी = someone's
    "kiske":    "kiskay",
    "kiski":    "kiskee",
    "kiska":    "kiska",
    "kab":      "kub",       # कब = when
    "kahan":    "kahaan",    # कहाँ = where
    "kaise":    "kaisay",
    "kitna":    "kitna",     # OK
    "kitni":    "kitnee",
    "kitne":    "kitnay",
    "basically": "basically",  # English — leave
    "actually":  "actually",
    "generally": "generally",
    "usually":   "usually",
    "mainly":    "mainly",
    "mostly":    "mostly",

    # ── Sentence-final particles ─────────────────────────────────────────────
    "na":       "naa",       # ना  (tag question) — not "nuh"
    "haan":     "haan",      # हाँ — OK
    "accha":    "ucchaa",    # अच्छा
    "theek":    "theek",     # OK
    "sahi":     "sahee",     # सही
}

# ─────────────────────────────────────────────────────────────────────────────
#  Words that are BOTH valid English AND common Hindi Roman words.
#  For these we use context-free substitution — be conservative.
#  Words omitted here are left as-is (English TTS handles them).
# ─────────────────────────────────────────────────────────────────────────────
# "to"  — also English preposition; substituted to "toh" (safe)
# "the" — also English article; substituted to "thay" (risky — skip)
# "hi"  — also English greeting; substituted to "hee" (fine in Hinglish context)
# "do"  — also English verb; substituted to "doh" (context-dependent — included)

# Protect these English words from substitution even if they appear in the map.
# Add any word here that you DO NOT want substituted.
_ALWAYS_ENGLISH: frozenset[str] = frozenset({
    "simple", "important", "basically", "actually", "generally",
    "usually", "mainly", "mostly", "really", "clearly", "directly",
    "easy", "hard", "fast", "slow", "real", "new", "old",
    # common tech terms that happen to look like Hindi
    "tab",      # HTML <tab> — but in Hinglish prose "tab" = "tub" → included
})

# Regex: match a whole word (including hyphenated compounds intact)
_WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")


def preprocess_roman_hinglish(text: str) -> str:
    """
    Apply phonetic substitutions to Roman-script Hinglish text so that
    Kokoro's English voice pronounces Hindi words naturally.

    Rules:
    - Only substitutes whole words (no partial matches).
    - Case-insensitive lookup; output preserves original capitalisation of
      the first letter (so "Hai" stays capitalised → "Hay").
    - Hyphenated tokens (e.g. "chhote-chhote", "loosely-coupled") are left
      intact — the English voice handles them fine.
    - Words in _ALWAYS_ENGLISH are never substituted.
    - If a word has no entry in ROMAN_HINDI_PHONETICS, it's left as-is;
      the English voice's own guess is usually acceptable for technical terms.
    """
    def _replace(m: re.Match) -> str:
        word = m.group(0)
        # Skip hyphenated compounds — treat as English/technical
        if "-" in word:
            return word
        lower = word.lower()
        if lower in _ALWAYS_ENGLISH:
            return word
        phonetic = ROMAN_HINDI_PHONETICS.get(lower)
        if phonetic is None:
            return word
        # Preserve capitalisation of the original first letter
        if word[0].isupper():
            return phonetic[0].upper() + phonetic[1:]
        return phonetic

    return _WORD_RE.sub(_replace, text)


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience: set of all Roman Hindi words we know about.
#  Callers can use this to decide whether a word is "Hindi" or "English".
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_ROMAN_HINDI_WORDS: frozenset[str] = frozenset(ROMAN_HINDI_PHONETICS.keys())
