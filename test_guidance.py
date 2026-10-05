import tempfile, unittest
from unittest.mock import patch
import app

class PracticeGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dbpatch=patch.object(app,'DB_PATH',self.tmp.name+'/test.db');self.dbpatch.start()
        first=app.local_import2('Притчи 15:1','ru')[0]
        second=app.local_import2('Иакова 1:19','ru')[0]
        self.reasons=[{'ru':'Кроткий ответ помогает не усилить ссору.','uk':'Лагідна відповідь допомагає не посилити сварку.'},
                      {'ru':'Готовность слушать помогает понять собеседника.','uk':'Готовність слухати допомагає зрозуміти співрозмовника.'}]
        self.application={'ru':'Выслушай человека, затем спокойно ответь.','uk':'Вислухай людину, а потім спокійно відповідай.'}
        self.exercise={'id':'guidance-test','topic':'speech','reference':first['reference'],
          'situation':{'ru':'Тебе резко отвечают.','uk':'Тобі різко відповідають.'},'reason':self.reasons[0],
          'answers':[{'ru':p,'uk':app.convert(p,'uk'),'reason':r} for p,r in zip([first,second],self.reasons)],
          'application':self.application}
        self.catalogpatch=patch.object(app,'CATALOG',{'topics':[{'id':'speech'}],'exercises':[self.exercise]});self.catalogpatch.start()
    def tearDown(self):
        self.catalogpatch.stop();self.dbpatch.stop();self.tmp.cleanup()
    def answer(self,text,lang='ru'):
        return app.answer2(dict(quiz_id='test-'+lang+'-'+text,exercise_id=self.exercise['id'],answer_text=text,
                               translation=lang,library_ids=[]),'owner')
    def test_each_catalog_answer_uses_its_own_reason_and_shared_application_without_api(self):
        with patch.object(app,'ask',side_effect=AssertionError('Catalog does not call provider')):
            for lang in ['ru','uk']:
                for i,pair in enumerate(self.exercise['answers']):
                    result=self.answer(pair[lang]['reference'],lang)
                    self.assertTrue(result['correct']);self.assertEqual(self.reasons[i],result['reason'])
                    self.assertEqual(self.application,result['application'])
                    self.assertEqual(self.reasons[1-i],result['alternatives'][0]['reason'])
                    self.assertEqual((5,0),(result['xp'],result['mastery']))
    def test_blank_answer_has_both_sections_and_no_rewards(self):
        with patch.object(app,'ask',side_effect=AssertionError('No provider')):
            for lang in ['ru','uk']:
                result=self.answer('',lang)
                self.assertFalse(result['correct']);self.assertEqual((0,0),(result['xp'],result['mastery']))
                self.assertEqual(self.reasons[0],result['reason']);self.assertEqual(self.application,result['application'])
    def test_other_suitable_reference_uses_ai_reason_and_application(self):
        p=app.local_import2('Ефесянам 4:29','ru')[0]
        reason={'ru':'Созидающая речь помогает ответить с заботой.','uk':'Повчальна мова допомагає відповісти з турботою.'}
        action={'ru':'Подбери слова, которые помогут разговору.','uk':'Добери слова, які допоможуть розмові.'}
        with patch.object(app,'ask',return_value={'correct':True,'chosen_id':p['id'],'explanation':reason,
                                               'reason':reason,'application':action,'alternatives':[]}) as ask:
            result=self.answer(p['reference'])
        self.assertTrue(result['correct']);self.assertEqual(p,result['passage'])
        self.assertEqual(reason,result['reason']);self.assertEqual(action,result['application'])
        self.assertEqual(1,ask.call_count)
        self.assertEqual(p,ask.call_args.args[1]['answer_passages'][0])
        self.assertEqual({'correct','chosen_id','explanation','reason','application','alternatives'},set(ask.call_args.args[2]['required']))
        self.assertEqual(self.reasons[0],result['alternatives'][0]['reason'])
    def test_rejected_answer_keeps_assessment_separate_from_authored_target_guidance(self):
        p=app.local_import2('Бытие 1:1','ru')[0]
        assessment={'ru':'Ответ не объясняет данный разговор.','uk':'Відповідь не пояснює цю розмову.'}
        with patch.object(app,'ask',return_value={'correct':False,'chosen_id':p['id'],'explanation':assessment,
             'reason':{'ru':'Не использовать','uk':'Не використовувати'},'application':{'ru':'Не использовать','uk':'Не використовувати'},'alternatives':[]}):
            result=self.answer(p['reference'])
        self.assertEqual(assessment,result['explanation']);self.assertEqual(self.reasons[0],result['reason'])
        self.assertEqual(self.application,result['application']);self.assertFalse(result['correct'])
    def test_unknown_text_still_reveals_catalog_guidance(self):
        with patch.object(app,'parse_references',return_value=[]),patch.object(app,'ask',side_effect=AssertionError('No provider')):
            result=self.answer('совсем непонятный ответ')
        self.assertEqual(self.reasons[0],result['reason']);self.assertEqual(self.application,result['application'])
    def test_generated_library_situation_keeps_guidance_for_blank_answer(self):
        p=self.exercise['answers'][0]['ru']
        with patch.object(app,'ask',return_value={'situation':self.exercise['situation'],'reason':self.reasons[0],'application':self.application}) as ask:
            quiz=app.practice2({'translation':'ru','scope':'library','ids':[p['id']]},'owner')
        self.assertEqual({'situation','focus','reason','application'},set(ask.call_args.args[2]['required']))
        self.assertNotIn('reason',quiz);self.assertNotIn('application',quiz)
        with patch.object(app,'ask',side_effect=AssertionError('Guidance is already stored')):
            result=app.answer2(dict(quiz_id=quiz['id'],translation='ru',answer_text='',library_ids=[]),'owner')
        self.assertEqual(self.reasons[0],result['reason']);self.assertEqual(self.application,result['application'])
    def test_older_unanswered_catalog_snapshot_receives_additive_guidance(self):
        payload=app.ready_payload(self.exercise,'ru')
        del payload['answer_reasons'];del payload['application']
        with patch.object(app,'ask',side_effect=AssertionError('No provider')):
            result=app.evaluate2(payload,'Иакова 1:19',[])
        self.assertEqual(self.reasons[1],result['reason']);self.assertEqual(self.application,result['application'])
        self.assertNotIn('answer_reasons',payload)
