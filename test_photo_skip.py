import base64, io, json, os, tempfile, unittest
from unittest.mock import patch
from PIL import Image
import app

class PhotoSkipTests(unittest.TestCase):
    def photo(self, size=(400,300)):
        output=io.BytesIO();Image.new('RGB',size,'white').save(output,'PNG')
        return base64.b64encode(output.getvalue()).decode()
    def test_photo_resolves_only_model_references_to_exact_corpus(self):
        for lang in ('ru','uk'):
            encoded=self.photo()
            with patch.object(app,'ask',return_value={'references':[dict(book='John',chapter=3,first=16,last=17)]}) as ask:
                result=app.import_photo2({'image':encoded,'instructions':'Подчёркнутое местописание','translation':lang})
            p=result['passages'][0]
            self.assertEqual(f'{lang}|John|3|16~{lang}|John|3|17',p['id'])
            self.assertEqual(app.read_passage(p['id'])['text'],p['text'])
            self.assertEqual('Подчёркнутое местописание',ask.call_args.args[1]['selection'])
            self.assertEqual('data:image/png;base64,'+encoded,ask.call_args.kwargs['image_url'])
    def test_invalid_image_and_missing_selection_never_call_provider(self):
        for data in [{'image':'notbase64','instructions':'Маркер'}, {'image':self.photo(),'instructions':''}, {'image':self.photo((5000,4000)),'instructions':'Маркер'}]:
            with patch.object(app,'ask') as ask:
                with self.assertRaises(app.Error):app.import_photo2(data)
            ask.assert_not_called()
    def test_ambiguous_photo_and_unknown_reference_rejected(self):
        for response in [{'references':[]},{'references':[dict(book='John',chapter=3,first=999,last=999)]}]:
            with patch.object(app,'ask',return_value=response):
                with self.assertRaises(app.Error):app.import_photo2({'image':self.photo(),'instructions':'Выделенное'})
    def test_photo_limit_100_not_silently_truncated(self):
        ref=dict(book='John',chapter=3,first=16,last=16)
        with patch.object(app,'ask',return_value={'references':[ref]*101}):
            with self.assertRaises(app.Error) as caught:app.import_photo2({'image':self.photo(),'instructions':'Все выделенные'})
        self.assertIn('101',str(caught.exception))
    def test_image_wire_format(self):
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self):return json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':'{"references":[]}'}]}]}).encode()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}), patch.object(app,'ai_budget'),patch.object(app.urllib.request,'urlopen',return_value=Reply()) as urlopen:
            app.ask('test',{'selection':'Маркер'},app.object_schema({'references':{'type':'array','items':app.REF2}}),image_url='data:image/png;base64,'+self.photo())
        body=json.loads(urlopen.call_args.args[0].data)
        self.assertEqual('input_image',body['input'][0]['content'][1]['type'])
        self.assertEqual('high',body['input'][0]['content'][1]['detail'])
        self.assertFalse(body['store'])
    def test_skipping_prepared_answer_is_local_unrewarded_and_final(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DB_PATH',folder+'/test.db'),patch.object(app,'ask',side_effect=AssertionError('No provider calls')):
            for lang in ('ru','uk'):
                exercise=app.CATALOG['exercises'][0]
                data=dict(quiz_id='skip-'+lang,exercise_id=exercise['id'],answer_text='  ',translation=lang,library_ids=[])
                result=app.answer2(data,'owner')
                self.assertFalse(result['correct']);self.assertEqual(0,result['xp']);self.assertEqual(0,result['mastery'])
                self.assertTrue(result['passage']['text']);self.assertTrue(result['alternatives'])
                self.assertEqual(exercise['reason'],result['explanation'])
                self.assertEqual(result,app.answer2(data,'owner'))
                with self.assertRaises(app.Error):app.answer2(dict(data,answer_text='Иоанна 3:16'),'owner')
    def test_skipping_generated_library_answer_reveals_target_without_provider(self):
        p=app.read_passage('ru|John|3|16');payload=dict(translation='ru',target=p,situation={'ru':'Ситуация','uk':'Ситуація'})
        with patch.object(app,'ask',side_effect=AssertionError('No provider calls')):
            result=app.evaluate2(payload,'',[])
        self.assertEqual(p,result['passage']);self.assertEqual(0,result['xp'])
