"""Intelligente Nachbearbeitung des Diktats (offline, regelbasiert, ohne Zusatz-Modell).

process(text) macht aus dem rohen Whisper-Text:
  * Selbstkorrekturen:  "Treffen am Dienstag, nein, ich meinte Mittwoch"  ->  "Treffen am Mittwoch"
                        "um 14 Uhr, nein, 15 Uhr"                          ->  "um 15 Uhr"
                        "ich meinte nicht rot, sondern blau"               ->  ersetzt "rot" durch "blau"
                        "..., ich meinte das nicht so, sondern <Satz>"     ->  ersetzt den letzten Satz
                        "... vergiss das" / "scratch that"                 ->  streicht den letzten Satz
  * Stichpunkte:        "Einkaufen neuer Stichpunkt Milch neuer Stichpunkt Brot"  ->  Zeilen mit "- "
                        "nummerierte Liste anfangen ..."                          ->  "1." "2." ...
                        "Ende der Liste" beendet die Liste
  * Befehle:            "neue Zeile", "neuer Absatz"
  * Füllwörter:         "äh", "ähm", "hmm"

Bewusst konservativ: Wörter wie "nein" oder "ich meine" kommen im normalen Satz oft vor und
lösen deshalb nur unter engen Bedingungen eine Korrektur aus.
"""
import re

# ----------------------------------------------------------------------
# Hilfen
# ----------------------------------------------------------------------
_SENT_END = re.compile(r"(?<!\d)[.!?](?=\s|$)|\n")          # "5. Mai" zählt nicht als Satzende
_CLAUSE_END = re.compile(r"[,;!?]|(?<!\d)\.(?=\s|$)|\n")
_EDGE = " \t,;:-–—"


def _norm(w):
    return re.sub(r"\W+", "", w.lower())


def _cut_last_sentence(prefix):
    """prefix ohne den letzten Satz bzw. Satzteil."""
    p = prefix.rstrip(_EDGE).rstrip(".!?").rstrip(_EDGE)
    last = None
    for m in _SENT_END.finditer(p):
        last = m
    return p[:last.end()].rstrip() if last else ""


def _split_clause(after):
    """(Korrekturtext, Rest) - der Korrekturtext reicht bis zum nächsten Komma/Satzende."""
    after = after.lstrip(_EDGE + ".")
    m = _CLAUSE_END.search(after)
    if not m:
        y = after.strip()
        if y[-1:] in (".", "!", "?"):    # "15." am Textende: Punkt ist Satzzeichen, nicht Ordinalzahl
            return y[:-1].rstrip(), y[-1]
        return y, ""
    return after[:m.start()].strip(), after[m.start():]


def _split_sentence(after):
    """(nächster Satz inkl. Satzzeichen, Rest)."""
    after = after.lstrip(_EDGE + ".")
    m = _SENT_END.search(after)
    if not m:
        return after.strip(), ""
    return after[:m.end()].strip(), after[m.end():]


_DAYS = {"montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag",
         "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
_MONTHS = {"januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
           "oktober", "november", "dezember", "january", "february", "march", "june", "july",
           "october", "december"}
_NUMW = {"null", "eins", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun",
         "zehn", "elf", "zwölf", "zwanzig", "dreißig", "vierzig", "fünfzig", "hundert", "tausend",
         "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
_ANCHORS = {"um", "am", "im", "in", "bis", "ab", "auf", "nach", "vor", "von", "zu", "mit", "für",
            "bei", "an", "aus", "über", "unter", "den", "dem", "der", "die", "das", "ein", "eine",
            "einen", "at", "on", "to", "for", "from", "by", "the", "a", "an"}
# Wörter, mit denen eine "nein, ..."-Antwort beginnt, die KEINE Korrektur ist
_GUARD = {"ich", "du", "er", "sie", "es", "wir", "ihr", "das", "dass", "danke", "bitte", "aber",
          "doch", "ja", "nein", "und", "oder", "wirklich", "also", "naja", "gut", "okay", "ok",
          "i", "you", "he", "she", "it", "we", "they", "thanks", "please", "but", "yes"}


def _cls(w):
    n = _norm(w)
    if n in _DAYS:
        return "day"
    if n in _MONTHS:
        return "month"
    if re.fullmatch(r"\d+", n) or n in _NUMW:
        return "num"
    return None


def _align(words, y_words, x=None):
    """Welcher Teil [i, j) von words wird durch y_words ersetzt?"""
    n = len(words)
    if x:
        nx = [_norm(w) for w in x.split()]
        nw = [_norm(w) for w in words]
        for i in range(n - len(nx), -1, -1):
            if nw[i:i + len(nx)] == nx:
                return i, i + len(nx)
    y0 = _norm(y_words[0])
    c = _cls(y_words[0])
    if c:   # gleiche Wortart: Wochentag->Wochentag, Zahl->Zahl
        for i in range(n - 1, -1, -1):
            if _cls(words[i]) == c:
                return i, min(n, i + len(y_words))
    if y0 in _ANCHORS:   # "um 14 Uhr" -> "um 15 Uhr": am letzten gleichen Funktionswort ansetzen
        for i in range(n - 1, -1, -1):
            if _norm(words[i]) == y0:
                return i, min(n, i + len(y_words))
    k = min(len(y_words), n)
    return n - k, n


# ----------------------------------------------------------------------
# Selbstkorrekturen
# ----------------------------------------------------------------------
_FIL = r"(?:(?:ä+h+m*|ö+h+m*|h+m+|u+h+m*|oh+|ach)\b[\s,]*)*"
_NEG = r"(?:nein|nee|ne|quatsch|sorry|entschuldigung|pardon|moment|stopp|halt|warte|falsch)"
_SEPS = r"[\s,:;.!\-]*"
_NEGS = rf"(?:{_NEG}\b{_SEPS})"
_EN_NEG = r"(?:no|sorry|oops|wait|hold\s+on)"

# (kind, tier, hat_x, regex) - Reihenfolge = Priorität bei gleicher Startposition
#   kind: span = nur die letzten Wörter ersetzen, sentence = ganzen letzten Satz ersetzen, delete = Satz streichen
#   tier 1 = eindeutiger Marker; tier 2 = nur "nein"/"nee" (strenger geprüft)
_PATTERNS = [
    ("sentence", 1, False, rf"(?:{_NEGS})*\bich\s+meinte\s+(?:das\s+)?(?:eigentlich\s+)?(?:nicht\s+so|anders)\b{_SEPS}"
                           rf"(?:sondern\b{_SEPS}(?:(?:so|eher|zwar)\b{_SEPS})?)?"),
    ("sentence", 1, False, rf"\b(?:ich\s+)?formuliere\s+(?:das\s+)?(?:noch\s*mal\s+)?(?:neu|anders)\b{_SEPS}"),
    ("sentence", 1, False, rf"\bnoch\s*mal\s+von\s+vorne\b{_SEPS}"),
    ("sentence", 1, False, rf"\blet\s+me\s+rephrase(?:\s+that)?\b{_SEPS}"),
    ("delete", 1, False, r"\b(?:vergiss|vergesst)\s+(?:das|es)\b(?!\s+nicht)"),
    ("delete", 1, False, r"\bstreich(?:e)?\s+(?:das|den\s+(?:letzten\s+)?satz)\b"),
    ("delete", 1, False, r"\blösch(?:e)?\s+(?:das|den\s+(?:letzten\s+)?satz)\b"),
    ("delete", 1, False, r"\bdas\s+(?:letzte\s+)?(?:streichen|löschen)\b"),
    ("delete", 1, False, r"\b(?:scratch|delete|forget)\s+that\b"),
    ("span", 1, True, rf"(?:(?:{_NEGS})+(?:ich\s+(?:meinte|meine)\b{_SEPS})?|ich\s+(?:meinte|meine)\b{_SEPS})"
                      rf"nicht\s+(?P<x>[^,.;!?]+?)[\s,]*sondern\b{_SEPS}"),
    ("span", 1, True, rf"(?:(?:{_EN_NEG}\b{_SEPS})+(?:I\s+(?:meant|mean)\b{_SEPS})?|I\s+(?:meant|mean)\b{_SEPS})"
                      rf"not\s+(?P<x>[^,.;!?]+?)[\s,]*but\b{_SEPS}"),
    ("span", 1, False, rf"{_FIL}(?:{_NEGS})+ich\s+(?:meinte|meine|wollte(?:\s+(?:eigentlich\s+)?sagen)?)\b"
                       rf"(?:\s+(?:eigentlich|natürlich|doch|ja|damit))?"),
    ("span", 1, False, r"\bich\s+meinte\b(?!\s+(?:dass|daß|damit|ob|nicht|es|das\s+(?:nicht|so)))"
                       r"(?:\s+(?:eigentlich|natürlich|doch|ja))?"),
    ("span", 1, False, r"\boder\s+(?:besser\s+gesagt|vielmehr)\b|\bbeziehungsweise\s+nein\b|\bkorrektur\b"),
    ("span", 1, False, rf"{_FIL}(?:{_EN_NEG}\b{_SEPS})+I\s+(?:meant|mean)\b"),
    ("span", 1, False, r"\bI\s+meant\b(?!\s+(?:that|to|it))"),
    ("span", 1, False, r"\bor\s+rather\b|\bno\s+wait\b|\bwait\s+no\b|\bactually\s+no\b|\bcorrection\b"),
    ("span", 2, False, rf"{_FIL}(?:nein|nee|quatsch|falsch)\b"),
]
_PATTERNS = [(k, t, x, re.compile(p, re.I)) for k, t, x, p in _PATTERNS]


def _next_marker(text, pos):
    best = None
    for idx, (kind, tier, _hx, rx) in enumerate(_PATTERNS):
        m = rx.search(text, pos)
        if m and (best is None or m.start() < best[0].start()):
            best = (m, kind, tier)
    return best


def _apply_span(text, m, tier):
    prefix, after = text[:m.start()], text[m.end():]
    y, rest = _split_clause(after)
    p = prefix.rstrip(_EDGE)
    term = ""
    if p and p[-1] in ".!?":
        if tier == 2:
            return None
        term = p[-1]
        p = p.rstrip(".!?" + _EDGE)
    y_words = y.split()
    if not p or not y_words:
        return None
    if tier == 2 and (len(y_words) > 3 or _norm(y_words[0]) in _GUARD):
        return None
    last = None
    for s in _SENT_END.finditer(p):
        last = s
    head = p[:last.end()] if last else ""
    words = (p[last.end():] if last else p).split()
    if not words:
        return None
    x = m.groupdict().get("x")
    i, j = _align(words, y_words, x)
    left = (head + " " if head else "") + " ".join(words[:i] + y_words + words[j:])
    if term and not rest.strip():
        rest = term
    return left + rest, len(left)


def _apply_sentence(text, m):
    keep = _cut_last_sentence(text[:m.start()])
    y, rest = _split_sentence(text[m.end():])
    if not y:
        return None
    left = (keep + " " if keep else "") + y
    return left + (" " + rest.lstrip() if rest.strip() else ""), len(left)


def _apply_delete(text, m):
    keep = _cut_last_sentence(text[:m.start()])
    rest = re.sub(r"^[\s,;:.!?\-]+", "", text[m.end():])
    left = keep
    return (left + " " + rest).strip(), len(left)


def apply_corrections(text, max_rounds=20):
    pos = 0
    for _ in range(max_rounds):
        found = _next_marker(text, pos)
        if not found:
            break
        m, kind, tier = found
        if kind == "span":
            res = _apply_span(text, m, tier)
        elif kind == "sentence":
            res = _apply_sentence(text, m)
        else:
            res = _apply_delete(text, m)
        if res is None:
            pos = m.end()       # kein sinnvoller Treffer: Text so lassen
            continue
        text, pos = res
    return text


# ----------------------------------------------------------------------
# Stichpunkte, Absätze
# ----------------------------------------------------------------------
_TOKENS = [
    ("end", r"\bende\s+der\s+(?:liste|aufzählung)\b|\b(?:liste|aufzählung)\s+(?:beenden|schließen)\b"
            r"|\blistenende\b|\bend\s+(?:of\s+)?(?:the\s+)?list\b"),
    ("start", r"\b(?:(?P<num>nummerierte[nr]?)\s+(?:stichpunkte|liste|aufzählung)"
              r"|stichpunkte|bullet[\s-]?points|(?:liste|aufzählung)\s+(?:anfangen|beginnen|starten|eröffnen))"
              r"(?:\s+(?:anfangen|beginnen|starten))?\b"),
    ("item", r"\b(?:(?:neuer|neuen|nächster|nächsten|weiterer|weiteren|new|next)\s+)?"
             r"(?:stichpunkt|spiegelstrich|aufzählungspunkt|listenpunkt|bullet[\s-]?point|bullet)\b"),
    ("punkt", r"\b(?:neuer|nächster|weiterer|neue|nächste)\s+punkt\b|\b(?:new|next)\s+point\b"),
    ("para", r"\bneuer\s+absatz\b|\bnew\s+paragraph\b"),
    ("nl", r"\bneue\s+zeile\b|\bnew\s+line\b"),
]
_TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _TOKENS), re.I)
_NOT_ITEM_PREV = {"einen", "den", "diesen", "jeden", "dem", "einem", "keinen", "ein", "diesem",
                  "this", "a", "an", "the", "each", "every"}
_FILLER = re.compile(r"\b(?:ä+h+m*|ö+h+m*|h+m+|u+h+m*)\b[,.]?\s*", re.I)


_STOTTER = re.compile(r"\b(\w{1,4})(?:[\s,-]+\1\b)+", re.I)   # "ich ich", "w-wir wir" -> einmal


def _tidy(s):
    s = _FILLER.sub("", s)
    s = _STOTTER.sub(r"\1", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"([,;])(\s*[,;])+", r"\1", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def _clean_segment(seg, item=False, capitalize=False):
    seg = seg.strip()
    capitalize = capitalize or bool(_FILLER.match(seg))
    seg = _tidy(apply_corrections(seg))
    seg = seg.strip(_EDGE + ".") if item else seg.strip(_EDGE)
    if (item or capitalize) and seg:
        seg = seg[0].upper() + seg[1:]
    return seg


def _structure(text):
    blocks = []                 # ("text"|"item", inhalt, break_davor)
    state = {"list": False, "num": False, "item": False, "br": 0, "n": 0}

    def add(seg):
        item = state["item"]
        seg = _clean_segment(seg, item, capitalize=bool(state["br"]) and not item)
        if not seg:
            return
        if item:
            state["n"] += 1
            blocks.append(("item", seg, f"{state['n']}. " if state["num"] else "- "))
        else:
            blocks.append(("text", seg, state["br"]))
            state["br"] = 0

    seg_start = scan = 0
    while True:
        m = _TOKEN_RE.search(text, scan)
        if not m:
            break
        kind = m.lastgroup if m.lastgroup != "num" else "start"
        for name in ("end", "start", "item", "punkt", "para", "nl"):
            if m.group(name):
                kind = name
                break
        before = text[:m.start()].rstrip()
        prev = before.split()[-1].lower() if before else ""
        skip = ((kind == "item" and prev in _NOT_ITEM_PREV)
                or (kind == "start" and before and before[-1] not in ".:!?,;")
                or (kind == "punkt" and not state["list"]))
        if skip:
            scan = m.end()
            continue
        add(text[seg_start:m.start()])
        seg_start = scan = m.end()
        if kind == "start":
            state.update(list=True, num=bool(m.group("num")), item=True, n=0, br=1)
        elif kind in ("item", "punkt"):
            if not state["list"]:
                state.update(list=True, num=False, n=0)
            state.update(item=True, br=1)
        elif kind == "end":
            state.update(list=False, item=False, br=1)
        else:
            state.update(item=False, br=2 if kind == "para" else max(state["br"], 1))
    add(text[seg_start:])

    lines = []
    for i, (kind, s, extra) in enumerate(blocks):
        if kind == "item":
            lines.append(extra + s)
        else:
            if extra == 2 and lines:
                lines.append("")
            if s.endswith(".") and i + 1 < len(blocks) and blocks[i + 1][0] == "item":
                s = s[:-1] + ":"        # Einleitungssatz vor einer Liste
            lines.append(s)
    return "\n".join(lines)


def process(text):
    """Rohtext von Whisper -> bereinigter Text. Bei jedem Fehler kommt der Rohtext unverändert zurück."""
    if not text or not text.strip():
        return text
    try:
        return _structure(re.sub(r"\s+", " ", text.strip())) or text
    except Exception:
        return text
