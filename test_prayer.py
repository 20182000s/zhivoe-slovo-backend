import unittest
from unittest.mock import patch
import app

class PrayerTests(unittest.TestCase):
    def test_grounded_bilingual_prayer(self):
        for language in ('ru','uk'):
            refs={'references':[{'book':'Psalms','chapter':22,'first':1,'last':1},{'book':'Matthew','chapter':6,'first':34,'last':34}]}
            def response(task,data,schema,**kwargs):
                if 'books' in data:return refs
                return {'prayer':{'ru':'Господи, помоги мне доверять Тебе.','uk':'Господи, допоможи мені довіряти Тобі.'},'reasons':[{'id':p['id'],'reason':{'ru':'Опора в тревоге.','uk':'Опора в тривозі.'}} for p in data['passages']]}
            with patch.object(app,'ask',side_effect=response):result=app.prayer2({'text':'Тревожусь о завтрашнем дне','translation':language})
            self.assertEqual(len(result['suggestions']),2)
            for suggestion in result['suggestions']:
                self.assertEqual(suggestion['passage']['translation'],language)
                self.assertEqual(suggestion['passage']['text'],app.read_passage(suggestion['passage']['id'])['text'])
    def test_duplicate_references_rejected(self):
        ref={'book':'Matthew','chapter':6,'first':34,'last':34}
        with patch.object(app,'ask',return_value={'references':[ref,ref]}):
            with self.assertRaises(app.Error):app.prayer2({'text':'Тревога','translation':'ru'})
    def test_missing_reasons_rejected(self):
        refs={'references':[{'book':'Matthew','chapter':6,'first':34,'last':34},{'book':'James','chapter':1,'first':19,'last':20}]}
        with patch.object(app,'ask',side_effect=[refs,{'prayer':{'ru':'Текст','uk':'Текст'},'reasons':[]}]):
            with self.assertRaises(app.Error):app.prayer2({'text':'Тревога','translation':'ru'})
