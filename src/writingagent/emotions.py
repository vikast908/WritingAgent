"""Emotions as craft, not a dictionary (plan §23).

A symptom dictionary ('fear = racing heart, sweaty palms') is a CLICHÉ GENERATOR - those
exact phrases are the most overused emotion-writing there is, and feeding them to a weak
model makes prose less believable, not more. So this module is the INVERSE:

- `avoid` : the stock phrases to flag and cut per emotion (a deny-list, wired into the
  cliché detector in craft.py), and
- `cue`   : the one craft technique that actually makes the emotion land (subtext, the
  physical tell, the turn) - injected as a per-run writing cue by the compositor.

Believable emotion is then carried by the show-don't-tell surgical pass (surgery.py) and
the deny-list, not by a glossary of feelings. See
docs/proposal-personas-emotions-composition.md.
"""
from __future__ import annotations

# Each emotion: the cliché phrases to AVOID (deny-list) and the craft cue (how to land it).
_EMOTIONS: dict[str, dict] = {
    "fear": {
        "avoid": ["heart raced", "heart pounded", "heart hammered", "blood ran cold",
                  "cold sweat", "palms sweaty", "sweaty palms", "time stood still",
                  "frozen in place", "froze in fear", "shiver down", "spine tingled",
                  "hair stood on end"],
        "cue": ("Fear: render it in what the body does without permission and the small thing "
                "the mind fixates on; let the threat stay mostly off the page. Do not name it."),
    },
    "anger": {
        "avoid": ["saw red", "blood boiled", "clenched fists", "clenched jaw", "veins popped",
                  "seething with rage", "white-hot anger", "trembled with rage"],
        "cue": ("Anger: show it leaking through control - the too-even voice, the precise small "
                "cruelty, the held stillness - not the volcano. Restraint reads hotter."),
    },
    "grief": {
        "avoid": ["wave of grief", "crushing weight", "hole in his heart", "tears streamed",
                  "world came crashing", "numb with grief", "heart shattered", "wracked with sobs"],
        "cue": ("Grief: anchor it to a concrete object or habit the loss has emptied of meaning; "
                "the ordinary detail that no longer has a reason to exist. Understate."),
    },
    "joy": {
        "avoid": ["heart soared", "on cloud nine", "over the moon", "couldn't stop smiling",
                  "burst with happiness", "grinning from ear to ear", "jumped for joy"],
        "cue": ("Joy: catch it in a specific, slightly silly particular - what the body or the "
                "attention does when it forgets to be guarded. Specific beats ecstatic."),
    },
    "love": {
        "avoid": ["butterflies in her stomach", "weak in the knees", "heart skipped a beat",
                  "lost in his eyes", "electricity between them", "world melted away"],
        "cue": ("Love: show it in attention - what the character notices, remembers, forgives, "
                "or rearranges their day around. Desire is in the noticing, not the adjectives."),
    },
    "shame": {
        "avoid": ["cheeks burned", "face flushed red", "wanted to disappear", "stomach dropped",
                  "sank into the floor", "burning with embarrassment"],
        "cue": ("Shame: render the small avoidance - the thing not looked at, the over-correction, "
                "the joke made to get ahead of the judgment. It hides; let it hide on the page."),
    },
    "tension": {
        "avoid": ["you could cut the tension", "tension was palpable", "pregnant pause",
                  "deafening silence", "air was thick", "on the edge of their seats"],
        "cue": ("Tension: withhold. Slow the clock with concrete, neutral detail while the reader "
                "waits for the thing you have promised and not yet delivered. Subtext over statement."),
    },
    "hope": {
        "avoid": ["light at the end of the tunnel", "ray of hope", "hope blossomed",
                  "spark of hope", "against all odds", "glimmer of hope"],
        "cue": ("Hope: ground it in one small, plausible piece of evidence the character lets "
                "themselves believe - tentative, easily lost. Earn it; don't announce it."),
    },
    "disgust": {
        "avoid": ["stomach turned", "stomach churned", "bile rose", "wave of nausea",
                  "skin crawled", "curled her lip", "wrinkled her nose", "turned her stomach",
                  "made her sick to her stomach"],
        "cue": ("Disgust: locate it in one precise sensory particular the body recoils from, and in "
                "the small thing the character does to put distance between themselves and it. "
                "Specific revulsion, not adjectives."),
    },
    "surprise": {
        "avoid": ["eyes went wide", "eyes widened", "jaw dropped", "mouth fell open",
                  "couldn't believe her eyes", "caught off guard", "stopped dead in her tracks",
                  "did a double take", "frozen in shock", "out of nowhere"],
        "cue": ("Surprise: render the half-second the mind spends catching up - the wrong assumption "
                "still running, the small task that stalls - before the new fact lands. Show the "
                "recalibration, not the gasp. (Covers awe/wonder: hold on the thing, not the awe.)"),
    },
    "jealousy": {
        "avoid": ["green with envy", "pang of jealousy", "green-eyed monster", "burned with jealousy",
                  "consumed by envy", "eaten up with jealousy", "pang of envy"],
        "cue": ("Jealousy: show it as distorted attention - the comparison the character can't stop "
                "making, the generosity they perform while keeping score. It poses as something "
                "nobler; let it pose, and let the reader catch it."),
    },
    "pride": {
        "avoid": ["swelled with pride", "puffed up with pride", "beamed with pride", "chest swelled",
                  "glowed with pride", "stood a little taller", "burst with pride"],
        "cue": ("Pride: catch it in the small tell the character would deny - the rehearsed modesty, "
                "the detail they steer the talk toward, the keepsake kept in view. Understate; let "
                "the reader award it."),
    },
}

# A small synonym map so a free-text emotional_role ('dread', 'fury') resolves to a key.
_ALIASES = {
    "afraid": "fear", "scared": "fear", "terror": "fear", "dread": "fear", "anxiety": "fear",
    "anxious": "fear", "fury": "anger", "rage": "anger", "angry": "anger", "irritation": "anger",
    "sorrow": "grief", "loss": "grief", "mourning": "grief", "sadness": "grief", "sad": "grief",
    "happiness": "joy", "happy": "joy", "delight": "joy", "elation": "joy",
    "desire": "love", "longing": "love", "romance": "love", "tenderness": "love",
    "embarrassment": "shame", "guilt": "shame", "humiliation": "shame",
    "suspense": "tension", "unease": "tension", "menace": "tension",
    "optimism": "hope", "yearning": "hope",
    "revulsion": "disgust", "repulsion": "disgust", "nausea": "disgust", "loathing": "disgust",
    "distaste": "disgust", "contempt": "disgust", "disgusted": "disgust",
    "shock": "surprise", "shocked": "surprise", "astonishment": "surprise", "amazement": "surprise",
    "awe": "surprise", "wonder": "surprise", "startled": "surprise", "astonished": "surprise",
    "envy": "jealousy", "jealous": "jealousy", "envious": "jealousy", "covetous": "jealousy",
    "proud": "pride", "triumph": "pride", "vanity": "pride", "satisfaction": "pride",
}


def names() -> list[str]:
    return list(_EMOTIONS)


def get(name: str | None) -> dict | None:
    """Resolve an emotion (with alias + substring tolerance for free-text roles); None if
    nothing matches, so a blueprint's free-text emotional_role degrades gracefully."""
    if not name:
        return None
    key = str(name).strip().lower()
    if key in _EMOTIONS:
        return _EMOTIONS[key]
    if key in _ALIASES:
        return _EMOTIONS[_ALIASES[key]]
    for token, target in _ALIASES.items():     # substring: 'a sense of dread' -> fear
        if token in key:
            return _EMOTIONS[target]
    for ekey in _EMOTIONS:
        if ekey in key:
            return _EMOTIONS[ekey]
    return None


def cue(name: str | None) -> str:
    e = get(name)
    return e["cue"] if e else ""


def avoid_phrases(name: str | None = None) -> list[str]:
    """The cliché deny-list for one emotion, or the union of all (the default) - fed to the
    craft cliché detector so 'her heart raced' is flagged wherever it appears."""
    if name:
        e = get(name)
        return list(e["avoid"]) if e else []
    out: list[str] = []
    for e in _EMOTIONS.values():
        out.extend(e["avoid"])
    return out
