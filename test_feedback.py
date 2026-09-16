import json,os,tempfile,unittest
from unittest.mock import patch
import app

class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=patch.object(app,'DB_PATH',self.tmp.name+'/db');self.p.start()
    def tearDown(self):self.p.stop();self.tmp.cleanup()
    def test_range_is_one_passage(self):
        out=app.import2({'text':'Иоанна 3:16–17','translation':'ru'})['passages'];self.assertEqual(1,len(out));self.assertEqual(2,len(out[0]['id'].split('~')));self.assertEqual('Иоанна 3:16–17',out[0]['reference'])
    def test_catalog_has_ten_valid_ranges_per_topic_in_both_languages(self):
        self.assertEqual(15,len(app.CATALOG['topics']))
        for topic in app.CATALOG['topics']:
            for lang in ('ru','uk'):
                passages=[app.convert(app.local_import2(r,'ru')[0],lang) for r in topic['references']]
                self.assertGreaterEqual(len(passages),10,(topic['id'],lang))
                self.assertTrue(all(p['translation']==lang for p in passages))
    def test_prepared_bank_and_daily_quotes(self):
        self.assertEqual(30,len(app.CATALOG['exercises']));self.assertEqual(15,len(app.CATALOG['daily']))
        for exercise in app.CATALOG['exercises']:
            for lang in ('ru','uk'):self.assertTrue(app.ready_passage(exercise,lang)['text'])
        for ref in app.CATALOG['daily']:
            for lang in ('ru','uk'):self.assertTrue(app.convert(app.local_import2(ref,'ru')[0],lang)['text'])
    def test_range_conversion_and_canonical_identity(self):
        ru=app.local_import2('Иоанна 3:16-17','ru')[0];uk=app.convert(ru,'uk')
        self.assertEqual('Івана 3:16–17',uk['reference']);self.assertEqual(app.canonical(ru),app.canonical(uk));self.assertEqual(ru,app.convert(uk,'ru'))
    def test_numbering_boundary(self):
        ru=app.local_import2('Числа 13:1-2','ru')[0];uk=app.convert(ru,'uk')
        self.assertEqual(['uk|Numbers|12|16','uk|Numbers|13|1'],uk['id'].split('~'));self.assertEqual(app.canonical(ru),app.canonical(uk))
    def test_free_answer_accepts_a_different_valid_passage(self):
        target=app.local_import2('Притчи 15:1-2','ru')[0];answer=app.local_import2('Иакова 1:19-20','ru')[0]
        payload={'translation':'ru','target':target,'situation':{'ru':'Спор','uk':'Суперечка'}}
        with patch.object(app,'ask',return_value={'correct':True,'chosen_id':answer['id'],'explanation':{'ru':'Подходит','uk':'Підходить'},'alternatives':[]}):
            out=app.evaluate2(payload,'Иакова 1:19-20',[answer['id']]);self.assertTrue(out['correct']);self.assertEqual(25,out['xp']);self.assertEqual(10,out['mastery']);self.assertEqual(app.canonical(answer),out['evaluatedID'])
    def test_single_verse_answer_rewards_library_range(self):
        target=app.local_import2('Притчи 15:1-2','ru')[0];answer=app.local_import2('Притчи 15:1','ru')[0]
        with patch.object(app,'ask',return_value={'correct':True,'chosen_id':answer['id'],'explanation':{'ru':'Да','uk':'Так'},'alternatives':[]}):
            result=app.evaluate2({'translation':'ru','target':target,'situation':{}},'Притчи 15:1',[target['id']]);self.assertEqual(10,result['mastery']);self.assertEqual(app.canonical(target),result['evaluatedID'])
    def test_free_answer_idempotent_and_language_locked(self):
        data={'quiz_id':'local-test-attempt','exercise_id':'ready-01','answer_text':'Притчи 3:5-6','translation':'ru','library_ids':[]}
        grade={'correct':True,'explanation':{'ru':'Да','uk':'Так'},'passage':None,'alternatives':[],'xp':25,'mastery':0,'evaluatedID':None}
        with patch.object(app,'evaluate2',return_value=grade)as mock:
            self.assertEqual(grade,app.answer2(data,'owner'));self.assertEqual(grade,app.answer2(data,'owner'));self.assertEqual(1,mock.call_count)
            with self.assertRaises(app.Error):app.answer2(dict(data,translation='uk'),'owner')
            with self.assertRaises(app.Error):app.answer2(data,'someone-else')
    def test_failure_allows_retry(self):
        data={'quiz_id':'retry-attempt','exercise_id':'ready-01','answer_text':'Притчи 3:5-6','translation':'ru','library_ids':[]}
        with patch.object(app,'evaluate2',side_effect=app.Error('Unavailable',503)):
            with self.assertRaises(app.Error):app.answer2(data,'owner')
        with app.db()as db:self.assertIsNone(db.execute('SELECT answer_id FROM quizzes WHERE id=?',(data['quiz_id'],)).fetchone()[0])
    def test_reflection_rejects_outside_library(self):
        p=app.local_import2('Матфея 6:34','ru')[0]
        with patch.object(app,'ask',return_value={'summary':{'ru':'Итог','uk':'Підсумок'},'suggestions':[{'id':'ru|John|3|16','reason':{},'action':{}}]}):
            with self.assertRaises(app.Error):app.reflect2({'text':'Сегодня был непростой день.','scope':'library','ids':[p['id']],'translation':'ru'})

if __name__=='__main__':unittest.main()
