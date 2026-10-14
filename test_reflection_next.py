import unittest
from unittest.mock import patch
import app

class NextReflectionTests(unittest.TestCase):
    def setUp(self):
        self.old=app.local_import2('Иакова 1:19–20','ru')[0]
        self.new=app.local_import2('Притчи 15:1','ru')[0]
        self.words={'ru':'Уважительно ответь в разговоре.','uk':'Шанобливо відповідай у розмові.'}
    def ref(self,p):
        return dict(book=p['book'],chapter=p['chapter'],first=p['verse'],last=int(p['id'].split('~')[-1].split('|')[-1]))
    def ask(self,refs,seen):
        def mocked(prompt,data,schema,**kwargs):
            seen.append(data)
            if 'references' in schema['properties']:return {'references':refs}
            return {'summary':self.words,'suggestions':[{'id':p['id'],'reason':self.words,'action':self.words,'shortAction':self.words} for p in data['passages']]}
        return mocked
    def test_initial_two_then_one_new_support_and_exclusions_in_prompt(self):
        seen=[]
        with patch.object(app,'ask',side_effect=self.ask([self.ref(self.old),self.ref(self.new)],seen)):
            result=app.reflect2(dict(text='Мы поспорили с другом о сложном разговоре.',translation='ru',scope='all',ids=[]))
        self.assertEqual(2,len(result['suggestions']))
        other=app.local_import2('Римлянам 12:18','ru')[0]
        seen=[]
        with patch.object(app,'ask',side_effect=self.ask([self.ref(self.old),self.ref(other),self.ref(self.new)],seen)):
            result=app.reflect2(dict(text='Мы поспорили с другом о сложном разговоре.',translation='ru',scope='all',exclude_ids=[self.old['id'],self.new['id']]))
        self.assertEqual([other['id']],[s['passage']['id'] for s in result['suggestions']])
        self.assertEqual(2,len(seen[0]['rejected']))
    def test_overlapping_range_is_excluded_across_translations(self):
        old=app.local_import2('Псалтирь 61:9','ru')[0]
        translated=app.convert(old,'uk')
        safe=app.convert(self.new,'uk');seen=[]
        with patch.object(app,'ask',side_effect=self.ask([self.ref(translated),self.ref(safe)],seen)):
            result=app.reflect2(dict(text='Хочу найти новую опору для своего разговора.',translation='uk',scope='all',exclude_ids=[old['id']]))
        self.assertEqual([safe['id']],[s['passage']['id'] for s in result['suggestions']])
        overlap=app.local_import2('Иакова 1:20–21','ru')[0]
        with patch.object(app,'ask',return_value={'references':[self.ref(overlap)]}) as ask:
            result=app.reflect2(dict(text='Хочу найти новую опору для своего разговора.',translation='ru',scope='all',exclude_ids=[self.old['id']]))
        self.assertEqual([],result['suggestions']);self.assertEqual(1,ask.call_count)
    def test_bad_exclusions_rejected_before_provider_and_library_unchanged(self):
        for value in ['bad',[None],['fake'],[self.old['id']]*101]:
            with self.subTest(value=value),patch.object(app,'ask',side_effect=AssertionError('No provider request')):
                with self.assertRaises(app.Error):app.reflect2(dict(text='Хочу опору для сложного разговора.',translation='ru',scope='all',exclude_ids=value))
        seen=[]
        with patch.object(app,'ask',side_effect=self.ask([],seen)):
            result=app.reflect2(dict(text='Хочу опору для сложного разговора.',translation='ru',scope='library',ids=[self.old['id']]))
        self.assertEqual(1,len(result['suggestions']))

if __name__=='__main__':unittest.main()
