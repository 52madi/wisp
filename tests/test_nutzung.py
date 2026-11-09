import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nutzung  # noqa: E402


class Nutzung(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.pfad = os.path.join(d, "nutzung.jsonl")

    def tearDown(self):
        if os.path.exists(self.pfad):
            os.remove(self.pfad)

    def test_schreiben_und_laden(self):
        nutzung.schreibe({"quelle": "cloud", "audio_s": 12.5}, self.pfad)
        nutzung.schreibe({"quelle": "lokal", "audio_s": 3.0, "ki_tokens": 120}, self.pfad)
        e = nutzung.lade(self.pfad)
        self.assertEqual([x["quelle"] for x in e], ["cloud", "lokal"])

    def test_kaputte_zeile_und_fehlende_datei(self):
        with open(self.pfad, "w", encoding="utf-8") as f:
            f.write("kein json\n{\"t\": 1.0, \"quelle\": \"cloud\"}\n[1]\n")
        self.assertEqual(len(nutzung.lade(self.pfad)), 1)
        self.assertEqual(nutzung.lade(self.pfad + ".fehlt"), [])

    def test_pro_tag_summen(self):
        jetzt = time.time()
        e = [{"t": jetzt, "quelle": "cloud", "audio_s": 30},
             {"t": jetzt, "quelle": "cloud", "audio_s": 3},          # zählt mit 10 s (Mindestabrechnung)
             {"t": jetzt, "quelle": "lokal", "audio_s": 20, "ki_tokens": 100},
             {"t": jetzt - 3 * 86400, "quelle": "lokal", "audio_s": 5}]
        tage = nutzung.pro_tag(e)
        self.assertEqual(len(tage), 2)
        z = tage[0]
        self.assertEqual((z["diktate"], z["cloud"], z["lokal"]), (3, 2, 1))
        self.assertEqual(z["cloud_s"], 40)
        self.assertEqual((z["ki"], z["ki_tokens"]), (1, 100))

    def test_heute_und_stunde(self):
        jetzt = time.time()
        e = [{"t": jetzt - 10, "quelle": "cloud", "audio_s": 60},
             {"t": jetzt - 7200, "quelle": "cloud", "audio_s": 100},   # nicht in der letzten Stunde
             {"t": jetzt - 5, "quelle": "lokal", "audio_s": 999}]      # lokal zählt nicht gegen Groq
        h = nutzung.heute(e, jetzt)
        self.assertEqual(h["stunde_s"], 60)
        self.assertEqual(h["anfragen"], 1 + (1 if time.strftime("%Y-%m-%d", time.localtime(jetzt - 7200))
                                             == time.strftime("%Y-%m-%d", time.localtime(jetzt)) else 0))

    def test_groq_stand(self):
        e = [{"t": 1.0, "quelle": "cloud", "rl_limit": 2000, "rl_rest": 1990},
             {"t": 2.0, "quelle": "lokal"},
             {"t": 3.0, "quelle": "cloud", "rl_limit": 2000, "rl_rest": 1985}]
        self.assertEqual(nutzung.groq_stand(e), {"limit": 2000, "rest": 1985, "t": 3.0})
        self.assertIsNone(nutzung.groq_stand([{"t": 1.0, "quelle": "lokal"}]))

    def test_dauer(self):
        self.assertEqual(nutzung.dauer(45), "45 s")
        self.assertEqual(nutzung.dauer(725), "12 min 05 s")
        self.assertEqual(nutzung.dauer(3900), "1 h 05 min")


if __name__ == "__main__":
    unittest.main()
