# Bakeoff episode prompt (identical for all five authors)

You are writing ONE short episode of a two-host AI news podcast. The audience
is a smart, busy listener who wants to understand what happened in AI this
week, laugh at least once, and come away with a sense of what actually
matters. Your source material is the RESEARCH PACKET below: transcripts of
real podcast episodes. You are curating and explaining what those episodes
said. You have no other sources.

## Output contract

- Output ONLY dialogue lines, nothing else: no title, no headings, no notes,
  no stage directions outside tags, no closing remarks about the script.
- Every line starts with `SPEAKER_1:` or `SPEAKER_2:` followed by one turn.
- Separate turns with one blank line.
- Length: 4,300 to 4,900 characters in total, including tags. That is about
  five minutes of audio. Never under 3,800 or over 5,500.

## Hosts

Name binding is absolute: SPEAKER_1 is Alexis, SPEAKER_2 is Brandon. If they
introduce themselves, SPEAKER_1 says "I'm Alexis" and SPEAKER_2 says
"I'm Brandon", never the reverse.

- **Alexis (SPEAKER_1)**: journalist instincts. Warm, quick, genuinely funny.
  Leads with the human story, the money, and who benefits or gets hurt.
  Skeptical of hype; shorter, punchier sentences.
- **Brandon (SPEAKER_2)**: the technical host. Precise, curious, a little
  nerdy. Leads with how the thing actually works. Gets excited by elegant
  engineering and is openly unimpressed by mediocre execution.
- They enjoy working together. Different lenses, not manufactured conflict.
  Turns vary: some one sentence, some four or five.

## Shape of the episode

1. A cold open with a hook (no "welcome to the show" boilerplate).
2. Two or three stories from the packet, chosen for what matters most, each
   with concrete names, numbers, and the mechanism explained in plain words.
3. At least one genuinely funny beat that grows out of the material, not a
   bolted-on joke.
4. At least one moment of real gravitas: a story that deserves weight gets
   it. Slow down, let it land, no jokes in that stretch.
5. A short close: one specific thing to watch, then a natural sign-off.

The emotional range should move: curiosity, amusement, concern, conviction.

## Delivery tags (ElevenLabs v4)

The script is voiced by Eleven v4, which reads square-bracket audio tags as
delivery directions and does not speak them. Use them to carry the emotional
range:

- Tags you may use: [laughs], [laughs harder], [sighs], [exhales], [whispers],
  [sarcastic], [curious], [excited], [mischievously], [pause], [long pause].
- Put a tag right after the speaker label or right before the words it
  colors: `SPEAKER_2: [curious] So how does that actually work?`
- Budget: 8 to 14 tags in the whole episode. At most one tag per turn and no
  tag on more than a third of the turns.
- Also shape delivery with punctuation: ellipses (...) for a beat of weight,
  an occasional CAPITALIZED word for emphasis, short sentences for pace.
- Never use SSML or angle-bracket markup such as <break>. Never use sound
  effect tags.

## Attribution and authority

- Attribute opinions to the sources: "the host argued", "their guest's point
  was", "according to the episode". The hosts curate; they do not claim
  expertise or independent knowledge.
- Never invent facts, numbers, quotes, people, or sources absent from the
  packet. If the packet does not settle something, say so plainly.
- Do not manufacture disagreement between the hosts.
- Spell numbers the way a person says them aloud when that reads naturally.

## Writing rules

Write like two people talking, not like an AI summarizing. These phrases and
patterns are banned:

{BANNED_LIST}

## Research packet

{PACKET}
