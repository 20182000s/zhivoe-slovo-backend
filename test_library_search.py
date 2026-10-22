import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import app
import library_search as search


def v(axis):
    result = [0.] * search.DIMENSIONS
    result[axis] = 1.
    return result


class LibrarySearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = self.temp.name + '/index.db'
        self.passages = list(app.PASSAGES.values())[:130]

    def test_cold_warm_and_changed_corpus_text(self):
        calls = []
        def embed(texts, *, purpose):
            calls.append((purpose, list(texts)))
            return [v(0) for _ in texts]
        for expected in (130, 0):
            result = search.Search(self.passages, 'PRIVATE DAY', embed, self.path, lambda:110)
            self.assertEqual(expected, result.misses)
        self.assertEqual(1, sum(p == 'library_index' for p, _ in calls))
        self.assertEqual(2, sum(p == 'library_query' for p, _ in calls))
        changed = [dict(p) for p in self.passages]
        changed[0]['text'] += ' Updated public text.'
        self.assertEqual(1, search.Search(changed, 'PRIVATE DAY', embed, self.path, lambda:110).misses)
        import sqlite3
        with sqlite3.connect(self.path) as c:
            self.assertNotIn('PRIVATE', repr(c.execute('SELECT * FROM passage_embeddings').fetchall()))
            self.assertEqual([('passage_embeddings',)], c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())

    def test_every_aspect_and_last_library_item_can_be_retrieved(self):
        passages = [dict(p, text=f'CORPUS{i}') for i, p in enumerate(self.passages)]
        def embed(texts, *, purpose):
            if purpose == 'library_query':return [v(1 if 'worry' in t else 2) for t in texts]
            return [v(1 if t.endswith('CORPUS129') else 2 if t.endswith('CORPUS128') else 0) for t in texts]
        result = search.Search(passages, 'worry. forgiveness.', embed, self.path, lambda:110)
        self.assertIn(passages[-1], result.candidates(30))
        self.assertIn(passages[-2], result.candidates(30))
        self.assertEqual(30, result.initial_count)

    def test_weak_scores_expand_and_preserve_saved_range(self):
        long = 'Точное местописание. ' * 4000
        passages = [dict(p) for p in self.passages]
        passages[-1].update(id='saved-range', text=long)
        def embed(texts, *, purpose):
            return [v(1 if purpose == 'library_query' else 0) for _ in texts]
        result = search.Search(passages, 'day', embed, self.path, lambda:110)
        self.assertTrue(result.weak)
        self.assertEqual(60, result.initial_count)
        candidate = result.prompt_passages(130)[-1]
        self.assertTrue(candidate['excerpt'])
        self.assertIn(candidate['text'], long)
        self.assertEqual('saved-range', result.candidates(130)[-1]['id'])
        self.assertEqual(long, result.candidates(130)[-1]['text'])

    def test_chunks_and_batches_obey_limits_without_losing_text(self):
        text = ('🕊' * 10000) + '\n' + ('абв ' * 20000)
        pieces = search.chunks(text)
        self.assertEqual(text, ''.join(pieces))
        self.assertTrue(all(len(t.encode()) <= 6000 for t in pieces))
        self.assertTrue(all(sum(len(t.encode()) for t in batch) <= 180000 and len(batch) <= 512
            for batch in search.batches(pieces * 4)))


class ReflectionRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(app, 'DB_PATH', self.temp.name + '/index.db')
        self.patch.start();self.addCleanup(self.patch.stop)
        self.ids = [p['id'] for p in list(app.PASSAGES.values())[:301]]
        self.words = {'ru':'Связь с ситуацией.', 'uk':'Зв’язок із ситуацією.'}

    def reply(self, task, data, schema, **kwargs):
        return {'summary':self.words, 'suggestions':[{'id':data['passages'][-1]['id'],
            'reason':self.words,'action':self.words,'shortAction':self.words}]}

    def test_boundary_99_direct_100_retrieval_and_over_300(self):
        for count in (99,100,301):
            with patch.object(app, 'embed', side_effect=lambda texts, **kw:[v(0) for _ in texts]) as embed, \
                 patch.object(app, 'ask', side_effect=self.reply) as ask, contextlib.redirect_stdout(io.StringIO()):
                result = app.reflect2({'scope':'library','text':'Private day story.', 'ids':self.ids[:count]})
            sent = ask.call_args.args[1]['passages']
            self.assertEqual(count == 99, embed.call_count == 0)
            self.assertEqual(99 if count == 99 else 60, len(sent))
            self.assertIn(result['suggestions'][0]['passage']['id'], self.ids[:count])

    def test_rejected_shortlist_expands_once_and_rejects_outside_id(self):
        sizes = []
        def reply(task, data, schema, **kw):
            sizes.append(len(data['passages']))
            return {'summary':self.words,'suggestions':[]} if len(sizes)==1 else self.reply(task,data,schema)
        with patch.object(app,'embed',side_effect=lambda texts, **kw:[v(0) for _ in texts]), \
             patch.object(app,'ask',side_effect=reply),contextlib.redirect_stdout(io.StringIO()):
            result = app.reflect2({'scope':'library','text':'Private day story.','ids':self.ids})
        self.assertEqual([60,120],sizes)
        self.assertEqual(1,len(result['suggestions']))
        with patch.object(app,'embed',side_effect=lambda texts, **kw:[v(0) for _ in texts]), \
             patch.object(app,'ask',return_value={'summary':self.words,'suggestions':[{'id':'ru|John|3|16'}]}):
            with self.assertRaises(app.Error):app.reflect2({'scope':'library','text':'Private day story.','ids':self.ids})

    def test_failed_search_does_not_generate_or_claim_no_support(self):
        with patch.object(app,'embed',side_effect=app.Error('Provider unavailable',503)),patch.object(app,'ask') as ask:
            with self.assertRaises(app.Error):app.reflect2({'scope':'library','text':'Private day story.','ids':self.ids})
        ask.assert_not_called()

    def test_embedding_response_order_usage_and_private_log_fields(self):
        response = {'data':[{'index':1,'embedding':v(1)},{'index':0,'embedding':v(0)}],
            'usage':{'prompt_tokens':7,'total_tokens':7}}
        output = io.StringIO()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'PRIVATE KEY'}),patch.object(app,'ai_budget'), \
             patch.object(app.urllib.request,'urlopen',return_value=io.StringIO(json.dumps(response))) as request, \
             contextlib.redirect_stdout(output):
            result = app.embed(['PRIVATE STORY','PRIVATE OTHER'],purpose='library_query')
        self.assertEqual([v(0),v(1)],result)
        self.assertNotIn('PRIVATE',output.getvalue())
        self.assertEqual(7,json.loads(output.getvalue())['input_tokens'])
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(('text-embedding-3-small',512),(payload['model'],payload['dimensions']))


if __name__ == '__main__':unittest.main()
