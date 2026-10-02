import io, json, os, tempfile, unittest
from unittest.mock import patch
import app

class BulkImportTests(unittest.TestCase):
    def references(self, language, count):
        return [p for p in app.PASSAGES.values() if p['translation']==language][:count]
    def test_100_explicit_references_in_both_languages(self):
        for lang in ('ru','uk'):
            refs=self.references(lang,100)
            with patch.object(app,'ask',side_effect=AssertionError('No API needed')):
                result=app.import2({'translation':lang,'text':'\n'.join(p['reference'] for p in refs)})
            self.assertEqual([p['id'] for p in refs],[p['id'] for p in result['passages']])
    def test_copied_text_keeps_all_100_references(self):
        refs=self.references('ru',100)
        text='\n'.join(p['reference']+' — '+p['text'] for p in refs)
        with patch.object(app,'ask',side_effect=AssertionError('No API needed')):
            result=app.import2({'text':text,'translation':'ru'})
        self.assertEqual(100,len(result['passages']))
    def test_101_rejected_without_partial_result(self):
        for lang in ('ru','uk'):
            with self.assertRaises(app.Error) as caught:
                app.import2({'text':'\n'.join(p['reference'] for p in self.references(lang,101)), 'translation':lang})
            self.assertIn('101',str(caught.exception));self.assertIn('100',str(caught.exception))
            self.assertIn('перенеси 1',caught.exception.uk)
    def test_dictation_can_return_100(self):
        refs=self.references('ru',100)
        parsed=[dict(book=p['book'],chapter=p['chapter'],first=p['verse'],last=p['verse']) for p in refs]
        with patch.object(app,'ask',return_value={'references':parsed}) as ask:
            result=app.import2({'text':'Надиктованные названия и номера','translation':'ru'})
        self.assertEqual(100,len(result['passages']))
        self.assertGreaterEqual(ask.call_args.kwargs['max_output_tokens'],16000)
    def test_exact_character_limit_and_localized_http_error(self):
        self.assertEqual(200000,len(app.required_text({'text':'я'*200000},'text',maximum=200000)))
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'DB_PATH',folder+'/test.db'), patch.dict(os.environ,{'API_TOKEN':'test-token-longer-than-24-characters'}):
            for language in ('ru','uk'):
                body=json.dumps({'text':'я'*200003,'translation':language},ensure_ascii=False).encode()
                env={'PATH_INFO':'/v2/import','REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),'HTTP_AUTHORIZATION':'Bearer '+os.environ['API_TOKEN']}
                statuses=[]
                response=json.loads(b''.join(app.application(env,lambda s,h:statuses.append(s))))
                self.assertTrue(statuses[0].startswith('400'))
                for value in ('200000','200003','3'):self.assertIn(value,response['error'])
                self.assertIn('Ліміт' if language=='uk' else 'Лимит',response['error'])
                self.assertNotIn('text',response['error'])
