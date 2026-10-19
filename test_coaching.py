import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import app

class CoachingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=patch.object(app,'DB_PATH',self.tmp.name+'/test.db');self.db.start()
        self.p=app.local_import2('Иакова 1:19','ru')[0]
        self.w={'ru':'Главная мысль верна. Покажите связь со слушанием.','uk':'Головна думка правильна. Покажіть зв’язок зі слуханням.'}
        self.data={'ids':[self.p['id']],'translation':'ru','criterion':'meaning','text':'Нужно спокойно выслушать человека'}
    def tearDown(self):self.db.stop();self.tmp.cleanup()
    def test_valid_grounded_grade_cached_and_owner_isolated(self):
        with patch.object(app,'ask',return_value={'score':4,'feedback':self.w}) as ask:
            self.assertEqual(4,app.meditation2(self.data,'a')['score'])
            app.meditation2(self.data,'a');self.assertEqual(1,ask.call_count)
            app.meditation2(self.data,'b');self.assertEqual(2,ask.call_count)
            self.assertEqual(self.p['text'],ask.call_args.args[1]['passage']['text'])
    def test_bad_grades_never_cached(self):
        for value in (0,6,True,'5'):
            with patch.object(app,'ask',return_value={'score':value,'feedback':self.w}):
                with self.assertRaises(app.Error):app.meditation2(self.data,'a')
    def test_invalid_inputs_never_call_ai(self):
        for override in ({'criterion':'recall'},{'text':''},{'ids':[]},{'ids':[self.p['id']]*2},{'text':'a'*6001}):
            with patch.object(app,'ask',side_effect=AssertionError('No AI for invalid input')):
                with self.assertRaises(app.Error):app.meditation2(dict(self.data,**override),'a')
    def test_provider_failure_does_not_cache(self):
        with patch.object(app,'ask',side_effect=app.Error('unavailable',503)):
            with self.assertRaises(app.Error):app.meditation2(self.data,'a')
        with patch.object(app,'ask',return_value={'score':5,'feedback':self.w}) as ask:
            self.assertEqual(5,app.meditation2(self.data,'a')['score']);self.assertEqual(1,ask.call_count)
    def test_uk_application_uses_database_text(self):
        with patch.object(app,'ask',return_value={'score':3,'feedback':self.w}) as ask:
            app.meditation2(dict(self.data,translation='uk',criterion='application'),'a')
            self.assertEqual('uk',ask.call_args.args[1]['passage']['translation'])
    def test_library_prompt_addresses_reader(self):
        payload={k:self.w for k in ('situation','focus','reason','application')}
        with patch.object(app,'ask',return_value=payload) as ask:
            app.practice2({'ids':[self.p['id']],'translation':'ru','scope':'library'},'a')
            self.assertIn('Вымышленные имена запрещены',ask.call_args.args[0])
    def test_personal_action_cached(self):
        data={'ids':[self.p['id']],'translation':'ru','action':self.w,'shortAction':self.w}
        with patch.object(app,'ask',return_value={'action':self.w,'shortAction':self.w}) as ask:
            app.personal_application2(data,'a');app.personal_application2(data,'a')
            self.assertEqual(1,ask.call_count);self.assertIn('Вы',ask.call_args.args[0])
    def test_routes_require_auth(self):
        for path in ('/v2/meditation','/v2/application'):
            captured=[]
            with patch.dict(os.environ,{'API_TOKEN':'test-only-long-secret-0000000000000'}):
                app.application({'PATH_INFO':path,'REQUEST_METHOD':'POST','wsgi.input':io.BytesIO(b'{}'),'CONTENT_LENGTH':'2'},lambda status,headers:captured.append(status))
            self.assertTrue(captured[0].startswith('401'))
