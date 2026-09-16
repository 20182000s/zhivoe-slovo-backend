import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import app

class SlovoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dbpatch=patch.object(app,'DB_PATH',self.tmp.name+'/test.sqlite3');self.dbpatch.start()
        self.env=patch.dict(os.environ,{'API_TOKEN':'test-token-longer-than-24-characters','OPENAI_API_KEY':''});self.env.start()
        self.p=app.PASSAGES['ru|Proverbs|15|1'];self.q=app.PASSAGES['ru|James|1|19']
    def tearDown(self):self.env.stop();self.dbpatch.stop();self.tmp.cleanup()
    def request(self,path,data,auth=True):
        body=json.dumps(data).encode();env={'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
        if auth:env['HTTP_AUTHORIZATION']='Bearer '+os.environ['API_TOKEN']
        status=[];result=b''.join(app.application(env,lambda s,h:status.append(s)))
        return int(status[0].split()[0]),json.loads(result)
    def test_two_translations(self):
        for version in ('ru','uk'):
            self.assertEqual(66,len([b for b in app.BOOKS if b['translation']==version]))
            self.assertGreater(sum(p['translation']==version for p in app.PASSAGES.values()),30000)
    def test_range_and_alias(self):
        p=app.local_import('Мф. 6:33–34; Иак 1:19','ru')
        self.assertEqual([x['verse'] for x in p],[33,34,19])
        p=app.local_import('Ів. 3:16-17','uk');self.assertEqual(len(p),2);self.assertEqual(p[0]['translation'],'uk')
    def test_bad_reference_never_partially_imports(self):
        with self.assertRaises(app.Error):app.local_import('Матфея 6:34-99','ru')
        self.assertEqual([],app.local_import('Матфея 6:34; неизвестный стих','ru'))
    def test_invalid_ai_reference_is_rejected(self):
        with patch.object(app,'ask',return_value={'references':[{'book':'Invented','chapter':1,'first':1,'last':1}]}):
            status,_=self.request('/v1/import',{'text':'диктовка','translation':'ru'});self.assertEqual(400,status)
    def test_authentication_required(self):
        status,_=self.request('/v1/import',{'text':'Мф 6:34'},auth=False);self.assertEqual(status,401)
    def test_missing_api_key_honest_error(self):
        status,result=self.request('/v1/reflect',{'text':'Сегодня я переживал из-за разговора.','scope':'all','translation':'ru'})
        self.assertEqual(status,503);self.assertIn('ключ OpenAI',result['error'])
    def test_unknown_library_id_rejected(self):
        status,_=self.request('/v1/practice',{'ids':['unknown'],'translation':'ru'});self.assertEqual(status,400)
    def test_reflection_cannot_escape_library(self):
        with patch.object(app,'ask',return_value={'summary':'Итог','suggestions':[{'id':self.q['id'],'reason':'Причина','action':'Действие'}]}):
            status,_=self.request('/v1/reflect',{'text':'Непростой разговор с коллегой сегодня.','ids':[self.p['id']],'scope':'library'});self.assertEqual(status,502)
    def test_quiz_answer_idempotency_and_owner(self):
        def generate(task,data,schema):
            return {'situation':'Коллега критикует. Как ответить?','correct_ids':[data['target']['id']],'explanation':'Попробуй ответить спокойно.'}
        with patch.object(app,'ask',side_effect=generate):
            quiz=app.make_practice({'ids':[self.p['id'],self.q['id']]},'alice')
        self.assertNotIn('correct_ids',quiz)
        with app.db() as conn:payload=json.loads(conn.execute('SELECT payload FROM quizzes WHERE id=?',(quiz['id'],)).fetchone()[0])
        good=payload['target']['id'];other=next(x['id'] for x in quiz['options'] if x['id']!=good)
        with self.assertRaises(app.Error):app.answer({'quiz_id':quiz['id'],'answer_id':good},'bob')
        first=app.answer({'quiz_id':quiz['id'],'answer_id':good},'alice')
        self.assertEqual(25,first['xp']);self.assertEqual(10,first['mastery'])
        self.assertEqual(first,app.answer({'quiz_id':quiz['id'],'answer_id':good},'alice'))
        with self.assertRaises(app.Error):app.answer({'quiz_id':quiz['id'],'answer_id':other},'alice')
    def test_wrong_answer_no_reward(self):
        with patch.object(app,'ask',side_effect=lambda task,data,schema:{'situation':'Ситуация','correct_ids':[data['target']['id']],'explanation':'Разбор'}):quiz=app.make_practice({'ids':[self.p['id'],self.q['id']]},'alice')
        with app.db() as conn:payload=json.loads(conn.execute('SELECT payload FROM quizzes WHERE id=?',(quiz['id'],)).fetchone()[0])
        wrong=next(p['id'] for p in quiz['options'] if p['id'] not in payload['correct_ids'])
        result=app.answer({'quiz_id':quiz['id'],'answer_id':wrong},'alice');self.assertFalse(result['correct']);self.assertEqual((0,0),(result['xp'],result['mastery']))
    def test_alternate_correct_answer(self):
        with patch.object(app,'ask',side_effect=lambda task,data,schema:{'situation':'Ситуация','correct_ids':[p['id'] for p in data['options']],'explanation':'Оба стиха уместны.'}):quiz=app.make_practice({'ids':[self.p['id'],self.q['id']]},'alice')
        result=app.answer({'quiz_id':quiz['id'],'answer_id':self.q['id']},'alice');self.assertTrue(result['correct']);self.assertEqual(self.q,result['passage'])
    def test_rate_limit(self):
        for _ in range(30):self.assertEqual(200,self.request('/v1/status',{})[0])
        self.assertEqual(429,self.request('/v1/status',{})[0])
    def test_structured_responses_request(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self):return json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':'{"answer":"ok"}'}]}]}).encode()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}),patch('urllib.request.urlopen',return_value=Response()) as http:
            self.assertEqual({'answer':'ok'},app.ask('task',{},app.object_schema({'answer':app.STRING})))
            body=json.loads(http.call_args.args[0].data);self.assertFalse(body['store']);self.assertTrue(body['text']['format']['strict'])
    def test_no_empty_or_non_object_body(self):
        self.assertEqual(400,self.request('/v1/status',[])[0])

if __name__=='__main__':unittest.main()
