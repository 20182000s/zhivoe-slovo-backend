import json, os, tempfile, unittest
from unittest.mock import patch
import app

class PracticeReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dbpatch=patch.object(app,'DB_PATH',self.tmp.name+'/test.db');self.dbpatch.start()
        self.env=patch.dict(os.environ,{'API_TOKEN':'test-secret-'+'a'*40});self.env.start()
        self.passages=[app.local_import2(r,'ru')[0] for r in ['Галатам 5:19–20','Матфея 5:23–24','Римлянам 12:15']]
        self.words={'ru':'Помоги Андрею выбрать шаг к примирению.','uk':'Допоможи Андрію обрати крок до примирення.'}
        self.generated=dict(situation=self.words,focus=self.words,reason=self.words,application=self.words)
    def tearDown(self):
        self.env.stop();self.dbpatch.stop();self.tmp.cleanup()
    def create(self,**extra):
        with patch.object(app,'ask',return_value=self.generated):
            return app.practice2(dict(scope='library',translation='ru',ids=[p['id'] for p in self.passages],**extra),'alice')
    def test_recovery_after_server_database_is_lost_keeps_original_situation(self):
        quiz=self.create(target_id=self.passages[0]['id'])
        self.assertEqual(quiz['focus'],self.words)
        self.assertNotIn('target',quiz);self.assertNotIn('Галатам',quiz['recovery'])
        with app.db() as db:db.execute('DELETE FROM quizzes')
        request=dict(quiz_id=quiz['id'],recovery=quiz['recovery'],translation='ru',answer_text='',library_ids=[])
        with patch.object(app,'ask',side_effect=AssertionError('Recovery cannot regenerate a question')):
            result=app.answer2(request,'alice')
            self.assertEqual(result['passage'],self.passages[0]);self.assertEqual(result['reason'],self.words)
            self.assertEqual(result['application'],self.words);self.assertEqual((0,0),(result['xp'],result['mastery']))
            self.assertEqual(app.answer2(request,'alice'),result)
    def test_recovery_is_bound_to_owner_id_language_and_cannot_be_modified(self):
        quiz=self.create()
        for token,ident,owner,lang in [(quiz['recovery'],'different','alice','ru'),(quiz['recovery'],quiz['id'],'bob','ru'),
                                     (quiz['recovery'],quiz['id'],'alice','uk'),('x'+quiz['recovery'][1:],quiz['id'],'alice','ru')]:
            with self.assertRaises(app.Error):app.recover_quiz(token,ident,owner,lang)
    def test_recovery_expires_and_does_not_accept_arbitrary_client_payload(self):
        quiz=self.create()
        with patch.object(app.time,'time',return_value=app.time.time()+8*86400):
            with self.assertRaises(app.Error):app.recover_quiz(quiz['recovery'],quiz['id'],'alice','ru')
        with self.assertRaises(app.Error):app.answer2(dict(quiz_id='fake',translation='ru',answer_text='',library_ids=[],recovery='fake'),'alice')
    def test_server_fallback_visits_each_passage_once_per_round(self):
        chosen=[]
        for _ in range(15):
            quiz=self.create()
            with app.db() as db:payload=json.loads(db.execute('SELECT payload FROM quizzes WHERE id=?',(quiz['id'],)).fetchone()[0])
            chosen.append(payload['target']['id'])
        for i in range(0,15,3):self.assertEqual(set(chosen[i:i+3]),{p['id'] for p in self.passages})
    def test_explicit_target_must_belong_to_current_library(self):
        with self.assertRaises(app.Error):self.create(target_id='ru|John|3|16')
    def test_failed_generation_does_not_consume_fairness_count(self):
        with patch.object(app,'ask',side_effect=app.Error('Provider unavailable',502)):
            with self.assertRaises(app.Error):app.practice2(dict(scope='library',translation='ru',ids=[self.passages[0]['id']]),'alice')
        with app.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM practice_shown').fetchone()[0],0)
    def test_subset_and_superset_are_removed_but_distinct_passages_remain(self):
        expanded=app.local_import2('Галатам 5:19–21','ru')[0]
        narrowed=app.local_import2('Галатам 5:20','ru')[0]
        other=self.passages[1]
        items=[dict(passage=p,reason=self.words,action=self.words) for p in [expanded,narrowed,other]]
        self.assertEqual([other],[s['passage'] for s in app.distinct_suggestions(items,[self.passages[0]])])
        for version in ['ru','uk']:
            payload=dict(version=2,translation=version,target=app.convert(self.passages[0],version),
                         accepted_answers=[app.convert(p,version) for p in [self.passages[0],expanded,narrowed,other]],reason=self.words)
            result=app.evaluate2(payload,'',[])
            self.assertEqual([other['book']],[s['passage']['book'] for s in result['alternatives']])

if __name__=='__main__':unittest.main()
