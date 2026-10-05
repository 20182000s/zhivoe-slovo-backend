import contextlib, io, json, os, unittest
from unittest.mock import patch
import app

class ModelRoutingTests(unittest.TestCase):
    def test_all_workloads_use_the_approved_model_despite_old_routing_variables(self):
        for env in ({}, {'OPENAI_MODEL':'gpt-6-astra'},
                    {'OPENAI_ROUTING_ENABLED':'true','OPENAI_REFERENCE_MODEL':'gpt-6-luna'}):
            with patch.dict(os.environ,env,clear=True):
                for purpose in ('general','reference','complex'):
                    self.assertEqual(app.model_for(purpose),'gpt-6.1-sol')

    def test_usage_is_measured_without_private_content(self):
        response={'status':'completed','output':[{'content':[{'type':'output_text','text':'{"ok":true}'}]}],
                  'usage':{'input_tokens':50,'output_tokens':20,'output_tokens_details':{'reasoning_tokens':8}}}
        stream=io.StringIO()
        with patch.dict(os.environ, {'OPENAI_API_KEY':'TEST-KEY','OPENAI_ROUTING_ENABLED':'true'},clear=True), \
             patch.object(app,'ai_budget'), patch.object(app.urllib.request,'urlopen') as call, contextlib.redirect_stdout(stream):
            call.return_value.__enter__.return_value=io.StringIO(json.dumps(response))
            self.assertEqual(app.ask('PRIVATE INSTRUCTION',{'day':'PRIVATE STORY'},app.object_schema({'ok':{'type':'boolean'}})),{'ok':True})
            request=json.loads(call.call_args.args[0].data)
            self.assertEqual(request['model'],'gpt-6.1-sol')
            self.assertFalse(request['store']);self.assertEqual(request['reasoning'],{'effort':'medium'})
        output=stream.getvalue()
        self.assertNotIn('PRIVATE',output);self.assertNotIn('TEST-KEY',output)
        self.assertEqual(json.loads(output)['reasoning_tokens'],8)

if __name__=='__main__':unittest.main()
