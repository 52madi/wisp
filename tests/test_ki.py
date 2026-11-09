import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import ki  # noqa: E402


class Hinweis(unittest.TestCase):
    def test_erkennt_korrekturen(self):
        self.assertTrue(ki.braucht_ki("Das ist rot, nein, ich meinte blau."))
        self.assertTrue(ki.braucht_ki("Das ist rot, besser gesagt blau."))

    def test_normaler_satz_bleibt_lokal(self):
        self.assertFalse(ki.braucht_ki("Kommst du morgen? Nein, ich bleibe zu Hause."))
        self.assertFalse(ki.braucht_ki("Ich komme heute vorbei."))
        self.assertFalse(ki.braucht_ki("Ich meine, das ist eine gute Idee."))

    def test_alltagssprache_bleibt_lokal(self):
        self.assertFalse(ki.braucht_ki("Das ist eigentlich ganz gut."))
        self.assertFalse(ki.braucht_ki("Ich meinte, dass wir früher gehen sollten."))
        self.assertFalse(ki.braucht_ki("Das ist nicht nur schön, sondern auch praktisch."))

    def test_nein_mitten_im_satz(self):
        self.assertTrue(ki.braucht_ki("Wir brauchen drei Stühle, nein, vier, und einen Tisch."))


class Plausibilitaet(unittest.TestCase):
    def test_gute_antwort(self):
        self.assertTrue(ki.plausibel("Wir treffen uns am Dienstag, nein, ich meinte Mittwoch.",
                                     "Wir treffen uns am Mittwoch."))

    def test_zu_lang(self):
        self.assertFalse(ki.plausibel("Kurz.", "Kurz. " + "Das ist ein langer Zusatz. " * 10))

    def test_fremder_inhalt(self):
        self.assertFalse(ki.plausibel("Wir treffen uns am Dienstag im Büro.",
                                      "Die Wetterlage verschlechtert sich deutlich in Bayern."))


class Aufruf(unittest.TestCase):
    def test_ohne_schluessel_kein_netz(self):
        # Auch eine vorhandene schluessel.txt darf den Test nicht beeinflussen.
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(ki, "SCHLUESSEL_DATEI", os.path.join("nicht", "vorhanden.txt")), \
             mock.patch("urllib.request.urlopen") as up:
            self.assertIsNone(ki.korrigiere("Text", "groq"))
            up.assert_not_called()

    def test_fehler_gibt_none(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "x"}), \
             mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            self.assertIsNone(ki.korrigiere("Text", "groq"))

    def test_erfolg(self):
        antwort = mock.MagicMock()
        antwort.__enter__.return_value.read.return_value = b""
        body = b'{"choices":[{"message":{"content":"Wir treffen uns am Mittwoch."}}]}'
        antwort.__enter__.return_value = mock.MagicMock(**{"read.return_value": body})
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "x"}), \
             mock.patch("urllib.request.urlopen", return_value=antwort):
            out = ki.korrigiere("Wir treffen uns am Dienstag, nein, ich meinte Mittwoch.", "groq")
        self.assertEqual(out, "Wir treffen uns am Mittwoch.")

    def test_speichere_schluessel(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "schluessel.txt")
            with mock.patch.dict(os.environ, {}, clear=True), \
                 mock.patch.object(ki, "SCHLUESSEL_DATEI", pfad):
                ki.speichere_schluessel("GROQ_API_KEY", "gsk_123")
                ki.speichere_schluessel("OPENROUTER_API_KEY", "sk_456")
                self.assertEqual(ki.schluessel("GROQ_API_KEY"), "gsk_123")
                self.assertEqual(ki.schluessel("OPENROUTER_API_KEY"), "sk_456")
                ki.speichere_schluessel("GROQ_API_KEY", "gsk_neu")
                self.assertEqual(ki.schluessel("GROQ_API_KEY"), "gsk_neu")
                ki.speichere_schluessel("OPENROUTER_API_KEY", "")
                self.assertEqual(ki.schluessel("OPENROUTER_API_KEY"), "")


if __name__ == "__main__":
    unittest.main()
