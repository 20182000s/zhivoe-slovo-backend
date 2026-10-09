import unittest
from unittest.mock import patch
import app

class CompactRangeTests(unittest.TestCase):
    def test_compact_cross_chapter_roundtrip_in_both_languages(self):
        for version in ('ru','uk'):
            atoms=[app.PASSAGES[f'{version}|Proverbs|22|29'],app.PASSAGES[f'{version}|Proverbs|23|1'],app.PASSAGES[f'{version}|Proverbs|23|2']]
            passage=app.grouped(atoms)
            self.assertTrue(passage['reference'].endswith('22:29–23:2'))
            self.assertEqual([passage],app.local_import2(passage['reference'],version))
            self.assertEqual(passage,app.exact_prepared_answer(passage['reference'],version,[passage]))
            with patch.object(app,'ask',side_effect=AssertionError('No paid import')):
                self.assertEqual([passage],app.import2({'text':passage['reference'],'translation':version})['passages'])
    def test_contiguous_groups_compact_without_filling_gaps(self):
        atoms=[app.PASSAGES[f'ru|Proverbs|23|{n}'] for n in (1,2,4,5)]
        passage=app.grouped(atoms)
        self.assertEqual('Притчи 23:1–2; Притчи 23:4–5',passage['reference'])
        self.assertNotIn('ru|Proverbs|23|3',passage['id'])
    def test_different_books_stay_separate(self):
        atoms=[app.PASSAGES['ru|Genesis|1|1'],app.PASSAGES['ru|Exodus|1|1']]
        self.assertEqual('Бытие 1:1; Исход 1:1',app.grouped(atoms)['reference'])
    def test_cross_chapter_reference_inside_free_answer(self):
        found=app.inline_import2('Вспомнил Притчи 22:29–23:2: важно проявить рассудительность.','ru')
        self.assertEqual(['Притчи 22:29–23:2'],[p['reference'] for p in found])
    def test_numbered_book_is_not_also_read_as_unnumbered_book(self):
        found=app.inline_import2('Мне подходит 1 Иоанна 3:17, ведь важна помощь.','ru')
        self.assertEqual(['ru|I John|3|17'],[p['id'] for p in found])
    def test_invalid_cross_chapter_references_are_rejected(self):
        for text in ('Притчи 23:2–22:29','Притчи 22:30–23:2','Притчи 22:29–40:1'):
            with self.assertRaises(app.Error):app.local_import2(text,'ru')

if __name__=='__main__':unittest.main()
