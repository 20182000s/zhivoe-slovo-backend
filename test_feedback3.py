import json
import os
import tempfile
import unittest
from unittest.mock import patch
import app

class SeptemberFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=patch.object(app,'DB_PATH',self.tmp.name+'/test.db');self.db.start()
        self.env=patch.dict(os.environ,{'API_TOKEN':'test-only-secret-longer-than-24-chars','ENABLE_DEVICE_SESSIONS':'true'});self.env.start()
        self.target=app.local_import2('Притчи 15:1','ru')[0]
    def tearDown(self):
        self.env.stop();self.db.stop();self.tmp.cleanup()
    def test_automatic_sessions_are_independent_and_signed(self):
        a=app.session_token({})['token'];b=app.session_token({})['token']
        owner=app.authorize({'HTTP_AUTHORIZATION':'Bearer '+a})
        self.assertNotEqual(owner,app.authorize({'HTTP_AUTHORIZATION':'Bearer '+b}))
        with self.assertRaises(app.Error):app.authorize({'HTTP_AUTHORIZATION':'Bearer '+a[:-1]+('a' if a[-1]!='a' else 'b')})
    def test_public_sessions_can_remain_disabled(self):
        with patch.dict(os.environ,{'ENABLE_DEVICE_SESSIONS':'false'}):
            with self.assertRaises(app.Error):app.session_token({})
    def test_daily_shared_budget_cannot_be_bypassed_by_new_session(self):
        with patch.dict(os.environ,{'AI_DAILY_CALL_LIMIT':'2'}):
            app.ai_budget();app.ai_budget()
            app.session_token({})
            with self.assertRaises(app.Error) as e:app.ai_budget()
            self.assertEqual(429,e.exception.status)
    def test_book_and_topic_filters_ground_target(self):
        for language in ('ru','uk'):
            for mode in ('book','topic','all'):
                topic=app.CATALOG['topics'][0]
                with patch.object(app,'ask',return_value={'situation':{'ru':'Ситуация','uk':'Ситуація'}}) as ask:
                    app.practice2({'translation':language,'scope':'all','filter':mode,'book':'John','topic':topic['id']},'test')
                    target=ask.call_args.args[1]['target']
                    self.assertEqual(language,target['translation'])
                    if mode=='book':self.assertEqual('John',target['book'])
                    if mode=='topic':self.assertIn(app.canonical(target),[app.canonical(app.local_import2(r,'ru')[0]) for r in topic['references']])
    def test_unrecognized_answer_shows_target(self):
        with patch.object(app,'parse_references',return_value=[]):
            grade=app.evaluate2({'translation':'ru','target':self.target},'не помню',[])
        self.assertEqual(self.target,grade['passage']);self.assertFalse(grade['correct']);self.assertEqual(0,grade['xp'])
    def test_incorrect_recognized_answer_shows_target(self):
        wrong=app.local_import2('Иоанна 3:16','ru')[0]
        with patch.object(app,'ask',return_value={'correct':False,'chosen_id':wrong['id'],'explanation':{'ru':'Не подходит','uk':'Не підходить'},'alternatives':[]}):
            grade=app.evaluate2({'translation':'ru','target':self.target,'situation':{}},'Иоанна 3:16',[])
        self.assertEqual(self.target,grade['passage']);self.assertEqual(app.canonical(self.target),grade['evaluatedID'])
    def test_reflection_caps_results_and_keeps_short_action(self):
        ps=[app.local_import2(r,'ru')[0] for r in ['Притчи 15:1','Иакова 1:19','Иоанна 3:16']]
        short={'ru':'Выслушать близкого без перебивания','uk':'Вислухати близького без перебивання'}
        items=[{'id':p['id'],'reason':short,'action':short,'shortAction':short} for p in ps]
        with patch.object(app,'ask',return_value={'summary':short,'suggestions':items}):
            result=app.reflect2({'translation':'ru','text':'Резко ответил близкому человеку','scope':'library','ids':[p['id'] for p in ps]})
        self.assertEqual(2,len(result['suggestions']));self.assertEqual(short,result['suggestions'][0]['shortAction'])
