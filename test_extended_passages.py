import os
import unittest
from unittest.mock import patch
import app

class ExtendedPassageTests(unittest.TestCase):
    def passage(self, version, count):
        atoms=[p['id'] for p in app.PASSAGES.values() if p['translation']==version and p['book']=='Genesis'][:count]
        return app.read_passage('~'.join(atoms))

    def test_fragment_can_cross_old_hundred_verse_boundary(self):
        for version in ('ru','uk'):
            passage=self.passage(version,101)
            self.assertEqual(101,len(passage['id'].split('~')))
            self.assertEqual([passage],app.library2({'ids':[passage['id']]}))
            self.assertGreater(len(app.convert(passage,'uk' if version=='ru' else 'ru')['id'].split('~')),100)

    def test_long_fragment_recovery_still_binds_owner_and_language(self):
        payload={'version':2,'translation':'ru','target':self.passage('ru',1500),
            'situation':{'ru':'Ситуация','uk':'Ситуація'}}
        with patch.dict(os.environ,{'API_TOKEN':'test-secret-for-long-passage-0000'}):
            token=app.quiz_recovery('quiz','owner',payload)
            self.assertGreater(len(token),120000)
            self.assertEqual(payload,app.recover_quiz(token,'quiz','owner','ru'))
            with self.assertRaises(app.Error):app.recover_quiz(token,'quiz','other','ru')

    def test_source_practice_accepts_long_fragment_identifier(self):
        passage=self.passage('ru',300)
        self.assertGreater(len(passage['id']),4000)
        with patch.object(app,'ask',return_value={'book':'Genesis','chapter':0,'first':0,'last':0}):
            self.assertEqual(2,app.source2({'translation':'ru','passage_id':passage['id'],'answer':'Бытие'})['mastery'])

    def test_reader_keeps_upper_bound_and_translation_validation(self):
        first=self.passage('ru',1)['id'];other=self.passage('uk',1)['id']
        for ident in ('~'.join([first]*5001),first+'~'+other,first+'~unknown'):
            with self.assertRaises(app.Error):app.read_passage(ident)

if __name__=='__main__':unittest.main()
