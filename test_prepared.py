import json
import tempfile
import unittest
from unittest.mock import patch
import app


class PreparedPracticeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db_patch=patch.object(app,'DB_PATH',self.tmp.name+'/quizzes.db')
        self.db_patch.start()
        answers=[]
        for ref in ('Притчи 15:1','Иакова 1:19'):
            ru=app.local_import2(ref,'ru')[0]
            answers.append({'ru':ru,'uk':app.convert(ru,'uk')})
        self.exercise={'id':'prepared-test','topic':'speech','reference':'Притчи 15:1',
            'situation':{'ru':'На тебя кричат. Как ответить?','uk':'На тебе кричать. Як відповісти?'},
            'answers':answers,'reason':{'ru':'Спокойный ответ и готовность слушать.','uk':'Спокійна відповідь і готовність слухати.'}}
        self.catalog=patch.object(app,'CATALOG',{'topics':[{'id':'speech'},{'id':'empty'}],
            'exercises':[self.exercise]})
        self.catalog.start()

    def tearDown(self):
        self.catalog.stop();self.db_patch.stop();self.tmp.cleanup()

    def attempt(self,language='ru',**selection):
        return app.practice2(dict(scope='all',translation=language,**selection),'owner')['id']

    def answer(self,ident,text,language='ru',**extra):
        return app.answer2(dict(quiz_id=ident,translation=language,answer_text=text,**extra),'owner')

    def test_both_prepared_answers_in_both_languages_without_api(self):
        with patch.object(app,'ask',side_effect=AssertionError('No paid calls')):
            for language in ('ru','uk'):
                for pair in self.exercise['answers']:
                    passage=pair[language]
                    result=self.answer(self.attempt(language),passage['reference'],language,
                                       library_ids=[passage['id']])
                    self.assertTrue(result['correct'])
                    self.assertEqual(passage,result['passage'])
                    self.assertEqual((5,2),(result['xp'],result['mastery']))
                    self.assertEqual(1,len(result['alternatives']))

    def test_filters_use_secondary_answer_book_and_reject_empty(self):
        with patch.object(app,'ask',side_effect=AssertionError('No paid calls')):
            self.attempt(filter='book',book='James')
            self.attempt(filter='topic',topic='speech')
            for selection in ({'filter':'book','book':'Genesis'},
                              {'filter':'topic','topic':'empty'},
                              {'filter':'book','book':'Unknown'},
                              {'filter':'topic','topic':'Unknown'},
                              {'filter':'unknown'}):
                with self.subTest(selection=selection),self.assertRaises(app.Error):
                    self.attempt(**selection)

    def test_attempt_hides_answers_and_snapshot_keeps_full_bank(self):
        with patch.object(app,'ask',side_effect=AssertionError('No paid calls')):
            quiz=app.practice2({'scope':'all'},'owner')
        self.assertEqual({'id','situation'},set(quiz))
        with app.db() as db:
            payload=json.loads(db.execute('SELECT payload FROM quizzes WHERE id=?',(quiz['id'],)).fetchone()[0])
        self.assertEqual(2,len(payload['accepted_answers']))

    def test_idempotency_owner_and_changed_answer(self):
        with patch.object(app,'ask',side_effect=AssertionError('No paid calls')):
            ident=self.attempt();result=self.answer(ident,'Иакова 1:19')
            self.assertEqual(0,result['mastery'])
            self.assertEqual(result,self.answer(ident,'Иакова 1:19'))
            with self.assertRaises(app.Error):self.answer(ident,'Притчи 15:1')
            with self.assertRaises(app.Error):
                app.answer2({'quiz_id':ident,'answer_text':'Иакова 1:19'},'other')

    def test_local_exercise_id_accepts_second_answer(self):
        with patch.object(app,'ask',side_effect=AssertionError('No paid calls')):
            result=self.answer('client-attempt','Иакова 1:19',exercise_id=self.exercise['id'])
        self.assertTrue(result['correct'])

    def test_wrong_answer_and_meaningful_alternative_use_semantic_review(self):
        for correct in (False,True):
            passage=app.local_import2('Ефесянам 4:29','ru')[0]
            with patch.object(app,'ask',return_value={'correct':correct,'chosen_id':passage['id'],
                    'explanation':{'ru':'Разбор','uk':'Розбір'},'alternatives':[]}) as ask:
                result=self.answer(self.attempt(),'Ефесянам 4:29')
            self.assertEqual(1,ask.call_count)
            self.assertEqual(correct,result['correct'])
            self.assertEqual(5 if correct else 0,result['xp'])
            self.assertEqual(passage if correct else self.exercise['answers'][0]['ru'],result['passage'])
            self.assertEqual(2,len(ask.call_args.args[1]['prepared_answers']))

    def test_explanation_with_prepared_reference_is_reviewed_not_blindly_accepted(self):
        passage=self.exercise['answers'][0]['ru']
        with patch.object(app,'ask',return_value={'correct':False,'chosen_id':passage['id'],
                'explanation':{'ru':'Неверное применение','uk':'Неправильне застосування'},'alternatives':[]}) as ask:
            result=self.answer(self.attempt(),'Притчи 15:1 — поэтому я буду кричать ещё громче.')
        self.assertFalse(result['correct']);self.assertEqual(1,ask.call_count)

    def test_library_generation_is_preserved(self):
        passage=self.exercise['answers'][0]['ru']
        with patch.object(app,'ask',return_value={'situation':self.exercise['situation']}) as ask:
            app.practice2({'scope':'library','ids':[passage['id']]},'owner')
        self.assertEqual(1,ask.call_count)
        self.assertEqual(passage,ask.call_args.args[1]['target'])

    def test_existing_quiz_without_prepared_fields_still_accepts_answer(self):
        passage=self.exercise['answers'][0]['ru']
        # Stored library quizzes from the previous release have no exercise_id,
        # reason or accepted_answers; their server-side target remains usable.
        with patch.object(app,'ask',return_value={'situation':self.exercise['situation']}):
            quiz=app.practice2({'scope':'library','ids':[passage['id']]},'owner')
        with patch.object(app,'ask',return_value={'correct':True,'chosen_id':passage['id'],
                'explanation':self.exercise['reason'],'alternatives':[]}):
            result=self.answer(quiz['id'],passage['reference'],library_ids=[passage['id']])
        self.assertTrue(result['correct'])
        self.assertEqual((5,2),(result['xp'],result['mastery']))

    def test_free_paraphrase_keeps_recognition_and_semantic_review(self):
        passage=self.exercise['answers'][1]['ru']
        with patch.object(app,'ask',side_effect=[
                {'references':[{'book':'James','chapter':1,'first':19,'last':19}]},
                {'correct':True,'chosen_id':passage['id'],'explanation':self.exercise['reason'],'alternatives':[]}
        ]) as ask:
            result=self.answer(self.attempt(),'Сначала выслушать человека, не спешить говорить и сердиться.')
        self.assertTrue(result['correct']);self.assertEqual(2,ask.call_count)

    def test_both_prepared_answers_shown_after_unrecognized_answer(self):
        with patch.object(app,'parse_references',return_value=[]), patch.object(app,'ask',side_effect=AssertionError('No API')):
            result=self.answer(self.attempt(),'Не помню')
        self.assertFalse(result['correct'])
        self.assertEqual(1,len(result['alternatives']))
        self.assertEqual(self.exercise['answers'][1]['ru'],result['alternatives'][0]['passage'])

    def test_exact_quote_is_local_but_extra_explanation_is_reviewed(self):
        p=self.exercise['answers'][0]['ru']
        with patch.object(app,'ask',side_effect=AssertionError('No API')):
            self.assertTrue(self.answer(self.attempt(),p['text'])['correct'])
        with patch.object(app,'parse_references',return_value=[p]), patch.object(app,'ask',return_value={
            'correct':False,'chosen_id':p['id'],'explanation':self.exercise['reason'],'alternatives':[]}) as ask:
            result=self.answer(self.attempt(),'Я не согласен: '+p['text'])
        self.assertEqual(1,ask.call_count)
        self.assertFalse(result['correct'])
        self.assertEqual(1,len(result['alternatives']))
