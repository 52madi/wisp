import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from postprocess import process  # noqa: E402


class Corrections(unittest.TestCase):
    def check(self, raw, expected):
        self.assertEqual(process(raw), expected)

    def test_weekday(self):
        self.check("Wir treffen uns am Dienstag, nein, ich meinte Mittwoch.",
                   "Wir treffen uns am Mittwoch.")

    def test_weekday_no_commas(self):
        self.check("Wir treffen uns am Dienstag nein ich meinte Mittwoch",
                   "Wir treffen uns am Mittwoch")

    def test_time_with_anchor(self):
        self.check("Das Meeting ist um 14 Uhr, nein, um 15 Uhr.", "Das Meeting ist um 15 Uhr.")

    def test_time_number_only(self):
        self.check("Das Meeting ist um 14 Uhr, nein, 15 Uhr.", "Das Meeting ist um 15 Uhr.")
        self.check("Das Meeting ist um 14 Uhr, ich meinte 15.", "Das Meeting ist um 15 Uhr.")

    def test_keeps_tail(self):
        self.check("Wir treffen uns am Dienstag, ich meinte Mittwoch, und gehen essen.",
                   "Wir treffen uns am Mittwoch, und gehen essen.")

    def test_not_x_but_y(self):
        self.check("Das Auto ist rot und schnell, nein, ich meinte nicht rot, sondern blau.",
                   "Das Auto ist blau und schnell.")

    def test_sentence_rephrase(self):
        self.check("Das Projekt ist ein Desaster. Ich meinte das nicht so, sondern: Das Projekt hat Potenzial.",
                   "Das Projekt hat Potenzial.")

    def test_cross_sentence(self):
        self.check("Treffen am Dienstag. Nein, ich meinte Mittwoch.", "Treffen am Mittwoch.")

    def test_forget_that(self):
        self.check("Ich komme morgen. Vergiss das. Ich komme heute.", "Ich komme heute.")

    def test_two_corrections(self):
        self.check("Am Montag, nein, ich meinte Dienstag, um 9 Uhr, nein, ich meinte 10 Uhr.",
                   "Am Dienstag, um 10 Uhr.")

    def test_english(self):
        self.check("Let's meet on Tuesday, no wait, Wednesday.", "Let's meet on Wednesday.")
        self.check("The car is red, sorry I meant blue.", "The car is blue.")

    def test_stutter(self):
        self.check("Ich ich glaube, das passt.", "Ich glaube, das passt.")
        self.check("Wir wir sollten gehen.", "Wir sollten gehen.")

    def test_fillers(self):
        self.check("Ähm, ich glaube, äh, das passt.", "Ich glaube, das passt.")


class NoFalsePositives(unittest.TestCase):
    def same(self, s):
        self.assertEqual(process(s), s)

    def test_plain_sentences(self):
        for s in ["Ich komme morgen vorbei.",
                  "Kommst du morgen? Nein, ich bleibe zu Hause.",
                  "Ich meine, das ist eine gute Idee.",
                  "Ich meinte, dass wir früher anfangen sollten.",
                  "Das ist nicht rot, sondern blau.",
                  "Vergiss das nicht!",
                  "Ich weiß es nicht, nein, das glaube ich wirklich nicht.",
                  "Nein, danke.",
                  "Sorry für die Verspätung.",
                  "Ich habe einen Stichpunkt aufgeschrieben.",
                  "Die Stichpunkte sind klar.",
                  "Am 5. Mai um 14 Uhr."]:
            with self.subTest(s=s):
                self.same(s)


class Lists(unittest.TestCase):
    def check(self, raw, expected):
        self.assertEqual(process(raw), expected)

    def test_bullets(self):
        self.check("Einkaufen. Neuer Stichpunkt. Milch. Neuer Stichpunkt. Brot. Neuer Stichpunkt. Eier.",
                   "Einkaufen:\n- Milch\n- Brot\n- Eier")

    def test_start_word(self):
        self.check("Stichpunkte: Milch, neuer Stichpunkt, Brot, neuer Stichpunkt, Eier.",
                   "- Milch\n- Brot\n- Eier")

    def test_correction_inside_item(self):
        self.check("Stichpunkte Milch neuer Stichpunkt Brot nein ich meinte Butter neuer Stichpunkt Eier",
                   "- Milch\n- Butter\n- Eier")

    def test_correction_does_not_cross_items(self):
        self.check("Neuer Stichpunkt Milch. Neuer Stichpunkt Nein, ich meinte Butter.",
                   "- Milch\n- Nein, ich meinte Butter")

    def test_numbered(self):
        self.check("Nummerierte Liste anfangen Aufstehen nächster Stichpunkt Frühstücken nächster Stichpunkt Arbeiten",
                   "1. Aufstehen\n2. Frühstücken\n3. Arbeiten")

    def test_end_of_list(self):
        self.check("Stichpunkte Milch neuer Stichpunkt Brot Ende der Liste Danach gehe ich nach Hause.",
                   "- Milch\n- Brot\nDanach gehe ich nach Hause.")

    def test_new_line_and_paragraph(self):
        self.check("Hallo Peter neue Zeile Wie geht es dir neuer Absatz Viele Grüße",
                   "Hallo Peter\nWie geht es dir\n\nViele Grüße")


if __name__ == "__main__":
    unittest.main()
