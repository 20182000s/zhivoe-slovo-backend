import unittest
from unittest.mock import patch
import app

class SourceTests(unittest.TestCase):
    def grade(self, answer, parsed, version='ru'):
        ident=f'{version}|Proverbs|15|1~{version}|Proverbs|15|2'
        with patch.object(app,'ask',return_value=parsed) as ai:
            result=app.source2({'translation':version,'passage_id':ident,'answer':answer})
        self.assertNotIn('target',ai.call_args.args[1])
        self.assertEqual(answer,ai.call_args.args[1]['answer'])
        return result['mastery']
    def test_partial_and_complete_both_languages(self):
        for version in ('ru','uk'):
            for answer,chapter,first,last,expected in [('притчей',0,0,0,2),('притчи 15',15,0,0,3),('притчи 15:1-2',15,1,2,4),('притчи 15:1',15,1,1,3),('притчи 16',16,0,0,2)]:
                self.assertEqual(expected,self.grade(answer,dict(book='Proverbs',chapter=chapter,first=first,last=last),version))
    def test_wrong_or_missing_book(self):
        for book in ('John',''):
            self.assertEqual(0,self.grade('ответ',dict(book=book,chapter=15,first=1,last=2)))
    def test_invalid_ai_result_does_not_award(self):
        with self.assertRaises(app.Error):self.grade('притчи',dict(book='Proverbs',chapter=-1,first=0,last=0))
    def test_language_mismatch_rejected_before_ai(self):
        with patch.object(app,'ask') as ai:
            with self.assertRaises(app.Error):app.source2({'translation':'uk','passage_id':'ru|Proverbs|15|1','answer':'Притчи'})
        ai.assert_not_called()
    def test_reflection_all_retains_two(self):
        refs={'references':[dict(book='Proverbs',chapter=15,first=1,last=1),dict(book='James',chapter=1,first=19,last=19)]}
        words={'ru':'Текст','uk':'Текст'}
        suggestions=[dict(id=i,reason=words,action=words,shortAction=words) for i in ['ru|Proverbs|15|1','ru|James|1|19']]
        with patch.object(app,'ask',side_effect=[refs,dict(summary=words,suggestions=suggestions)]):
            result=app.reflect2(dict(text='Сегодня был непростой разговор',translation='ru',scope='all',ids=[]))
        self.assertEqual(2,len(result['suggestions']))
