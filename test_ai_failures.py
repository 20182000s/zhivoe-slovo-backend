import contextlib
import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch
import app


class AIFailureTests(unittest.TestCase):
    def call_failure(self, exception):
        output=io.StringIO()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'PRIVATE-KEY'}), patch.object(app,'ai_budget'), \
             patch.object(app.urllib.request,'urlopen',side_effect=exception), contextlib.redirect_stdout(output):
            with self.assertRaises(app.Error) as caught:
                app.ask('PRIVATE-TASK',{'text':'PRIVATE-ANSWER'},app.object_schema({'ok':app.STRING}))
        self.assertNotIn('PRIVATE',output.getvalue())
        return caught.exception,json.loads(output.getvalue())

    def http(self,status,code=None):
        return urllib.error.HTTPError('https://api.openai.com/v1/responses',status,'error',{},
            io.BytesIO(json.dumps({'error':{'code':code,'message':'PRIVATE-UPSTREAM-TEXT'}}).encode()))

    def test_upstream_http_errors_are_not_called_timeouts(self):
        for status in (400,401,403,429,500,503):
            with self.subTest(status=status):
                error,event=self.call_failure(self.http(status))
                self.assertNotIn('вовремя',str(error))
                self.assertEqual('http',event['kind']);self.assertEqual(status,event['http_status'])
                self.assertTrue(error.uk)

    def test_quota_is_distinct_from_rate_limit(self):
        error,event=self.call_failure(self.http(429,'credit_balance_exhausted'))
        self.assertIn('баланс',str(error));self.assertEqual(503,error.status)
        self.assertEqual('credit_balance_exhausted',event['code'])
        error,_=self.call_failure(self.http(429,'rate_limit_exceeded'))
        self.assertIn('частоту',str(error));self.assertEqual(429,error.status)

    def test_only_actual_timeout_has_timeout_message(self):
        for exception in (TimeoutError(),urllib.error.URLError(TimeoutError())):
            error,event=self.call_failure(exception)
            self.assertEqual(504,error.status);self.assertIn('вовремя',str(error))
            self.assertEqual('timeout',event['kind'])
        error,event=self.call_failure(urllib.error.URLError('PRIVATE-CONNECTION'))
        self.assertEqual('connection',event['kind']);self.assertIn('связаться',str(error))

    def test_deadline_bounds_each_upstream_call(self):
        token=app.AI_DEADLINE.set(time.monotonic()+12)
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'TEST'}),patch.object(app,'ai_budget'), \
                 patch.object(app.urllib.request,'urlopen',side_effect=TimeoutError()) as call, \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(app.Error):app.ask('task',{},app.object_schema({'ok':app.STRING}))
                self.assertGreater(call.call_args.kwargs['timeout'],0)
                self.assertLessEqual(call.call_args.kwargs['timeout'],12)
        finally:app.AI_DEADLINE.reset(token)


class PracticeFailureTests(unittest.TestCase):
    def setUp(self):
        self.target=app.local_import2('Иакова 4:11','ru')[0]
        self.other=app.local_import2('Ефесянам 4:29','ru')[0]
        self.words={'ru':'Связь с поступком героя.','uk':'Зв’язок із вчинком героя.'}
        self.payload={'version':2,'translation':'ru','target':self.target,'situation':self.words,
            'reason':self.words,'application':self.words}

    def test_exact_generated_target_is_checked_without_api(self):
        with patch.object(app,'ask',side_effect=AssertionError('No provider')):
            for text in (self.target['reference'],self.target['text']):
                result=app.evaluate2(self.payload,text,[self.target['id']])
                self.assertTrue(result['correct']);self.assertEqual((5,2),(result['xp'],result['mastery']))
                self.assertEqual(self.words,result['reason']);self.assertEqual(self.words,result['application'])

    def assessment(self):
        return {'correct':True,'chosen_id':self.other['id'],'explanation':self.words,'reason':self.words,
            'application':self.words,'alternatives':[{'reference':{'book':'James','chapter':1,'first':19,'last':19},
            'reason':self.words,'action':self.words}]}

    def test_optional_suggestions_failure_does_not_lose_finished_assessment(self):
        with patch.object(app,'ask',side_effect=[self.assessment(),app.Error('Unavailable',503)]) as ask:
            result=app.evaluate2(self.payload,self.other['reference'],[])
        self.assertEqual(2,ask.call_count);self.assertTrue(result['correct'])
        self.assertEqual([],result['alternatives']);self.assertEqual(self.words,result['reason'])
        self.assertEqual(self.words,result['application']);self.assertEqual(5,result['xp'])

    def test_optional_call_is_skipped_when_deadline_is_near(self):
        with patch.object(app,'ask',return_value=self.assessment()) as ask,patch.object(app,'ai_remaining',return_value=10):
            result=app.evaluate2(self.payload,self.other['reference'],[])
        self.assertEqual(1,ask.call_count);self.assertTrue(result['correct']);self.assertEqual([],result['alternatives'])

    def test_failed_assessment_can_be_retried_without_committing_wrong_grade(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(app,'DB_PATH',directory+'/quiz.db'):
            with app.db() as connection:
                connection.execute('INSERT INTO quizzes VALUES (?,?,?,?,NULL,NULL)',
                    ('quiz','owner',time.time(),json.dumps(self.payload)))
            data={'quiz_id':'quiz','translation':'ru','answer_text':self.other['reference'],'library_ids':[]}
            with patch.object(app,'ask',side_effect=app.Error('Unavailable',503)):
                with self.assertRaises(app.Error):app.answer2(data,'owner')
            with app.db() as connection:
                self.assertEqual((None,None),connection.execute('SELECT answer_id,result FROM quizzes').fetchone())
            assessment=dict(self.assessment(),alternatives=[])
            with patch.object(app,'ask',return_value=assessment):result=app.answer2(data,'owner')
            with patch.object(app,'ask',side_effect=AssertionError('Result cached')):
                self.assertEqual(result,app.answer2(data,'owner'))
            self.assertTrue(result['correct'])


if __name__=='__main__':unittest.main()
