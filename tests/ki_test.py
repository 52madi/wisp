"""Testet kostenlose KI-Dienste für die Nachkorrektur von Diktaten (ohne WISP-Integration).

    python tests/ki_test.py --liste                 # nur Modelle auflisten (kein Schlüssel nötig)
    python tests/ki_test.py                         # alle Testsätze mit den Standardmodellen
    python tests/ki_test.py --anbieter groq         # nur ein Anbieter

Schlüssel werden nur aus Umgebungsvariablen gelesen:
    OPENROUTER_API_KEY, GROQ_API_KEY
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ki  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAETZE = os.path.join(HERE, "ki_saetze.json")

ANBIETER = {
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "modelle_url": "https://openrouter.ai/api/v1/models",
        "key_env": "OPENROUTER_API_KEY",
        # sehr günstig (Cent-Bruchteile pro Million Token) bzw. kostenlos, Stand: Okt. 2026
        "modelle": ["openai/gpt-oss-20b",
                    "meta-llama/llama-3.1-8b-instruct",
                    "google/gemma-4-26b-a4b-it:free"],
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "modelle_url": "https://api.groq.com/openai/v1/models",
        "key_env": "GROQ_API_KEY",
        "modelle": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
    },
}

def anfrage(anbieter, modell, text, timeout=20):
    cfg = ANBIETER[anbieter]
    key = ki.schluessel(cfg["key_env"])
    body = json.dumps({
        "model": modell,
        "temperature": 0,
        "messages": [{"role": "system", "content": ki.SYSTEM}, {"role": "user", "content": text}],
        **ki.zusatz(modell),
    }).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        out = data["choices"][0]["message"]["content"].strip()
        return out, time.time() - start, None
    except urllib.error.HTTPError as e:
        return None, time.time() - start, f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
    except Exception as e:
        return None, time.time() - start, repr(e)


def modelle_listen(anbieter):
    cfg = ANBIETER[anbieter]
    req = urllib.request.Request(cfg["modelle_url"])
    key = ki.schluessel(cfg["key_env"])
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)["data"]
    return [m["id"] for m in data]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--liste", action="store_true", help="nur Modelle auflisten")
    ap.add_argument("--anbieter", choices=list(ANBIETER), help="nur diesen Anbieter testen")
    ap.add_argument("--modell", action="append", help="eigenes Modell (mehrfach möglich)")
    args = ap.parse_args()

    if args.liste:
        for name in ANBIETER:
            try:
                ids = modelle_listen(name)
                print(f"{name}: {len(ids)} Modelle")
                for i in ids:
                    if name != "openrouter" or i.endswith(":free"):
                        print("  ", i)
            except Exception as e:
                print(f"{name}: Liste nicht abrufbar ({e!r})")
        return

    saetze = json.load(open(SAETZE, encoding="utf-8"))
    for name in ([args.anbieter] if args.anbieter else ANBIETER):
        cfg = ANBIETER[name]
        if not ki.schluessel(cfg["key_env"]):
            print(f"[{name}] übersprungen: {cfg['key_env']} ist nicht gesetzt")
            continue
        modelle = args.modell or cfg["modelle"]
        for modell in modelle:
            print(f"\n=== {name} / {modell} ===")
            zeiten, treffer = [], 0
            for s in saetze:
                out, dauer, fehler = anfrage(name, modell, s["roh"])
                if fehler:
                    print(f"  FEHLER ({dauer:.1f}s): {fehler}")
                    if "429" in fehler:
                        print("  Limit erreicht, Rest dieses Modells wird übersprungen.")
                        break
                    continue
                zeiten.append(dauer)
                ok = out == s["soll"]
                treffer += ok
                print(f"  {'OK ' if ok else 'ANDERS'} {dauer:4.1f}s  {out!r}")
                if not ok:
                    print(f"           soll: {s['soll']!r}")
            if zeiten:
                print(f"  -> exakt getroffen: {treffer}/{len(saetze)}, "
                      f"Ø {sum(zeiten) / len(zeiten):.1f}s, max {max(zeiten):.1f}s")


if __name__ == "__main__":
    sys.exit(main())
