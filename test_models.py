import contextlib, io, json, os, unittest
from unittest.mock import patch
import app

class ModelRoutingTests(unittest.TestCase):
    def test_disabled_preserves_deployed_model(self):
        with patch.dict(os.environ, {'OPENAI_MODEL':'existing-model'}, clear=True):
            for role in ('general','reference','complex'):
                self.assertEqual(app.model_for(role),'existing-model')

    def test_roles_and_overrides(self):
        with patch.dict(os.environ, {'OPENAI_ROUTING_ENABLED':'true'}, clear=True):
            self.assertEqual(app.model_for(),'gpt-6-sol')
            self.assertEqual(app.model_for('reference'),'gpt-6-sol')
            self.assertEqual(app.model_for('complex'),'gpt-6-astra')
            with patch.dict(os.environ, {'OPENAI_REFERENCE_MODEL':'gpt-6-luna'}):
                self.assertEqual(app.model_for('reference'),'gpt-6-luna')

    def test_usage_is_measured_without_private_content(self):
        response={'status':'completed','output':[{'content':[{'type':'output_text','text':'{"ok":true}'}]}],
                  'usage':{'input_tokens':50,'output_tokens':20,'output_tokens_details':{'reasoning_tokens':8}}}
        stream=io.StringIO()
        with patch.dict(os.environ, {'OPENAI_API_KEY':'TEST-KEY','OPENAI_ROUTING_ENABLED':'true'},clear=True), \
             patch.object(app,'ai_budget'), patch.object(app.urllib.request,'urlopen') as call, contextlib.redirect_stdout(stream):
            call.return_value.__enter__.return_value=io.StringIO(json.dumps(response))
            self.assertEqual(app.ask('PRIVATE INSTRUCTION',{'day':'PRIVATE STORY'},app.object_schema({'ok':{'type':'boolean'}})),{'ok':True})
            request=json.loads(call.call_args.args[0].data)
            self.assertEqual(request['model'],'gpt-6-sol')
            self.assertFalse(request['store'])
        output=stream.getvalue()
        self.assertNotIn('PRIVATE',output);self.assertNotIn('TEST-KEY',output)
        self.assertEqual(json.loads(output)['reasoning_tokens'],8)

if __name__=='__main__':unittest.main()
