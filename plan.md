Good — video + audio streams both present now, ~49s, sentence-by-sentence timing is fixed. Let's look at a frame to ground my suggestions in what your current style actually looks like:Glad it's rendering correctly now — that flat gradient + static sentence + waveform combo is exactly why it reads as "boring line by line." The render is technically solid; what's missing is the stuff that actually makes reels/shorts feel *alive*. Here's how I'd prioritize fixing that, roughly in order of impact for view-time and retention:

**1. Voice is the single biggest lever, fix this first**
A flat, evenly-paced narration is the #1 reason it feels like "reading." For motivational/romantic/thriller content you need actual vocal performance — pitch rising on questions, pauses before reveals, faster pace during tension, slower/heavier on emotional lines. Of your existing TTS backends, XTTS (voice cloning) gives you the most expressive control if you feed it a reference voice that already has dramatic delivery. Kokoro/MMS are flatter by design. If virality matters more than "fully offline," consider letting XTTS do the heavy lifting and reserve Kokoro for quick drafts only.

**2. Kill the static sentence-on-screen, go word-by-word reveal**
Right now each full sentence appears all at once and just sits there. Swap to a karaoke-style word-by-word pop-in (word scales up 1.1x and snaps to size as it's spoken, rather than appearing instantly) — this alone makes it feel "alive" instead of "read aloud over a slide." Your `_render_sentence_frame` already tracks `active_word`; you'd extend it so each word animates in around when it's spoken rather than all words being static and just re-colored.

**3. Replace the flat gradient with moving backgrounds**
A static color gradient behind every sentence is the second-biggest "boring" signal. Options, roughly cheapest to richest:
- Subtle animated zoom/pan (Ken Burns effect) on the gradient itself, or on stock footage/AI-generated images matching each chunk's topic/mood
- Particle or light-leak overlay loops (cheap to generate once, loop like you already do for the waveform)
- For story content specifically: a relevant background image/clip per scene (e.g. a forest for a thriller line, sunrise for motivational) pulled from free stock APIs (Pexels/Pixabay have free APIs) or generated locally

**4. Add a hook in the first 2–3 seconds**
The algorithm (and viewers) decide to stay or scroll within 2-3 seconds. Don't open with scene-setting — open with the most shocking/emotional line, a question, or a bold claim, then go back to tell the story. This needs a content-structuring change in `summarizer.py`/`narration.py`, not just rendering.

**5. Background music with ducking**
Even a single quiet ambient/cinematic loop under the narration (ducked under TTS volume) massively changes the "feel." Silence except for voice + waveform reads as a tech demo, not content. ffmpeg can duck audio automatically (`sidechaincompress` filter) — I can wire this into `pipeline.py` if you want.

**6. Visual emphasis on punch words**
Right now every word gets the same highlight treatment. For motivational/dramatic content, punch words ("never," "die," "love," "broken") deserve a bigger pop — scale jump, color flash, maybe a quick shake — while connector words stay calm. This is a config-level tweak to `_render_sentence_frame` driven by a small list of "emphasis" keywords (could live in `core/lang/`).

**7. Pacing variation per chunk type**
Uniform fade/timing across every sentence (`STORY_SENTENCE_FADE`) makes pacing monotone. Vary it: quick punchy cuts for action/tension lines, slower lingering fades for emotional reveals. This pairs naturally with #1 (voice prosody) — match visual pace to vocal pace per sentence.

**8. Captions style matters more than content for shorts**
Bold, high-contrast, slightly larger-than-life captions (which you mostly have) plus *emoji accents* on key beats (🔥💔⚔️) noticeably lift retention on Reels/Shorts — cheap to add via a keyword→emoji map per sentence.

If you want, I can start implementing concretely — my suggestion would be **word-by-word reveal animation (#2)** and **background music with ducking (#5)** first, since those are pure rendering/pipeline changes I can do directly in your existing code without needing new assets. Want me to build those two now?