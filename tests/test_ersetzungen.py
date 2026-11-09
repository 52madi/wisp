import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ersetzungen  # noqa: E402


def regeln(inhalt):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(inhalt)
    try:
        return ersetzungen.lade(f.name)
    finally:
        os.remove(f.name)


class Ersetzungen(unittest.TestCase):
    def test_phrase_case_insensitive(self):
        r = regeln("cloud code = Claude Code\n")
        self.assertEqual(ersetzungen.ersetze("Ich nutze Cloud Code täglich.", r), "Ich nutze Claude Code täglich.")
        self.assertEqual(ersetzungen.ersetze("cloud-code läuft", r), "Claude Code läuft")

    def test_einzelnes_cloud_bleibt(self):
        r = regeln("cloud code = Claude Code\n")
        self.assertEqual(ersetzungen.ersetze("Die Cloud ist schnell, Codex auch.", r), "Die Cloud ist schnell, Codex auch.")

    def test_wortgrenze(self):
        r = regeln("cloud code = Claude Code\n")
        self.assertEqual(ersetzungen.ersetze("Cloud Codes sind neu", r), "Cloud Codes sind neu")

    def test_kommentar_und_leere_zeilen(self):
        self.assertEqual(len(regeln("# Kommentar\n\nfalsch = richtig\nkaputt\n")), 1)

    def test_fehlende_datei(self):
        self.assertEqual(ersetzungen.lade("Z:/gibt/es/nicht.txt"), [])


if __name__ == "__main__":
    unittest.main()
