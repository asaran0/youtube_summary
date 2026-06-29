# QA Mode — Input File Format Guide

This is the reference for how to write `.txt` files for `qa_mode` (interview-prep /
Q&A videos). Keep this file in `qa_mode/` so it's easy to find later — it documents
every format feature currently supported, including the code-block and explanation
features added most recently.

Sample files live in `questions/*.txt`.

---

## 1. Basic Q/A pairs

Two label styles are accepted — use whichever you prefer, even mixed in the same file:

```
Q: What is an Abstract Class?
A: An abstract class can have both abstract methods and concrete methods.

Q: What is Kafka?
A: Kafka is a distributed event streaming platform.
```

or numbered:

```
Q1: What is an Abstract Class?
A1: An abstract class can have both abstract methods and concrete methods.

Q2: What is Kafka?
A2: Kafka is a distributed event streaming platform.
```

Rules:
- Each `Q:`/`Qn:` must be followed by exactly one `A:`/`An:` before the next question.
- Blank lines between pairs are optional but recommended for readability.
- The question number shown on screen (`QA_QUESTION_LABEL_TEMPLATE` in
  `qa_mode/config.py`) uses the explicit number if you wrote one (`Q5:`), otherwise
  falls back to its position in the file.

---

## 2. Language — Hindi, English, or Hinglish

Set in `qa_mode/config.py`:

```python
LANGUAGE = "en"    # English — Latin font, English-style TTS voice
LANGUAGE = "hi"    # Hindi — Devanagari font, Hindi TTS voice
LANGUAGE = "hig"   # Hinglish — Devanagari font, same voice set as "hi"
```

This one setting controls **both** the font used to render text on screen and which
voice the TTS backend picks (see `KOKORO_VOICES` / `MACOS_TTS_VOICES` etc. in config).
You write the actual question/answer text in whichever script matches — the loader
doesn't translate anything, it just renders what you write:

```
Q1: एक developer ने गलती से buggy code main branch में push कर दिया। आप इसे कैसे handle करेंगे?
A: अगर code पहले से push हो गया है और बाकी developers ने pull कर लिया है, तो मैं `git revert` का use करूंगा।
```

Code blocks and the `>` explanation syntax (below) work identically regardless of
`LANGUAGE` — write code in English/Latin as normal even inside a Hindi answer; only
the surrounding prose needs to match your `LANGUAGE` setting's script.

---

## 3. Parentheses — shown, but not spoken

Anything in `(...)` is displayed on screen but skipped by the narrator. Useful for
extra on-screen detail you don't want cluttering the voice-over:

```
A: An abstract class can have both abstract methods (without a body)
   and concrete methods (with a body).
```

The narrator says: *"An abstract class can have both abstract methods and concrete
methods."* — but the viewer sees the parenthetical detail too. The word-by-word
highlight stays in sync because parenthetical words are excluded from the timing
calculation, not just hidden.

---

## 4. Bullet points

Lines starting with `-` or `•` become their own bulleted line on screen:

```
A: Key features of Java include:
   - Object-oriented
   - Platform-independent
   - Multithreaded
```

---

## 5. Code blocks (commands, snippets — any language)

Wrap code in triple backticks, optionally naming the language right after the
opening fence (the name shown as a tag on the card — `bash`, `python`, `java`,
`sql`, anything):

```
A: I would use `git revert` to undo the change safely.

​```bash
git revert <commit-id>
git push origin main
​```

I avoid `git reset` in shared branches because it rewrites history.
```

What this gives you:
- **Exact original line breaks are preserved** — each line of code appears on its
  own line on screen, never reflowed or merged.
- **Rendered as a distinct card**: dark background, monospace font, rounded
  corners, a terminal-style 🔴🟡🟢 dot header, and the language tag in the corner.
- **The code itself is never read aloud** — the narrator speaks the prose before
  and after the block, and the card just appears at that point in the video. This
  works for git commands, Linux shell, Python, Java, SQL — anything.
- A short inline mention like `` `git revert` `` (single backticks, no fence) is
  just normal text — it's still spoken as part of the sentence. Only **triple-backtick
  fenced blocks** get the silent-card treatment.

---

## 6. Explaining a code block out loud (`>` blockquote)

A code block on its own is silent — good for a quick one-liner, but for anything
that needs walking through (the way you'd narrate it in a real interview — *"first
we do this, then this, to get the result"*), add a `>` line immediately after the
closing fence:

```
​```bash
git revert <commit-id>
git push origin main
​```
> First, git revert creates a new commit that undoes the buggy changes without
> rewriting history. Then we push that revert commit so everyone on the team gets
> the fix.

I avoid `git reset` in shared branches because it rewrites history.
```

What this gives you:
- The explanation **is spoken by the narrator**, right after the code card appears
  — exactly where you'd say it out loud in an interview.
- It's shown on screen as a **visually distinct callout** (different bullet `»`
  and accent colour) directly under the code card, so it reads clearly as
  "this text explains that code" rather than blending into the regular answer.
- It still gets the normal word-by-word highlight, perfectly synced to the voice.
- Multiple `>` lines in a row are joined into one explanation (don't leave a blank
  line between them, or the rest will be treated as a separate, plain paragraph
  instead of part of the callout):

```
​```bash
docker build -t myapp .
docker run -p 8080:80 myapp
​```
> docker build packages the app into an image using the Dockerfile.
> docker run then starts a container from that image and maps port 8080 to it.
```

- The `>` explanation is **optional**. Skip it for trivial one-liners where the
  code speaks for itself; add it whenever the *why*/*order of operations* matters
  for the viewer to understand the answer.

---

## 7. Full worked example (English, mixing every feature)

```
Q1: A developer accidentally pushed buggy code to the main branch. How would you handle it?

A: If the code is already pushed and other developers may have pulled it,
I would use `git revert` to create a new commit that undoes the changes
(this is safer than rewriting history).

​```bash
git revert <commit-id>
git push origin main
​```
> First, git revert creates a new commit that undoes the buggy changes without
> rewriting history. Then we push that revert commit so everyone on the team
> gets the fix.

I avoid `git reset` in shared branches because it rewrites history and can
affect other developers.
```

This single answer will, in the final video:
1. Speak + highlight the opening sentence word-by-word.
2. Show `(this is safer than rewriting history)` on screen only — not spoken.
3. Show the `git revert` / `git push` commands as a terminal-style card — not spoken.
4. Speak the explanation aloud while showing it as a highlighted callout under the card.
5. Continue speaking + highlighting the closing sentence normally.

---

## Quick reference

| You write                                   | Spoken by narrator? | How it looks on screen                  |
|----------------------------------------------|----------------------|------------------------------------------|
| Plain sentence                                | Yes, word-highlighted | Normal bulleted text                     |
| `(text in parens)`                            | No                   | Shown inline, normal style, no highlight |
| `- bullet` / `• bullet`                       | Yes                  | Own bullet line                          |
| `` `inline code` `` (single backtick)         | Yes                  | Normal text (backticks shown as typed)   |
| ` ```lang ... ``` ` (triple-backtick fence)   | No                   | Dark monospace code card with lang tag   |
| `> explanation` right after a fence           | Yes                  | Cyan `»` callout under the code card     |
