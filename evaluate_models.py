"""Opt-in live RU/UK comparison on fictional inputs. Run on Render with its existing key.

python evaluate_models.py --live > /tmp/slovo-model-evaluation.json
Does not alter routing. Review answers manually before enabling a candidate.
"""
import argparse, contextlib, io, json, os, time
from unittest.mock import patch
import app

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    if not parser.parse_args().live:raise SystemExit('Live evaluation requires --live; paid API calls, fictional inputs only.')
    if not os.getenv('OPENAI_API_KEY'):raise SystemExit('Run in the server environment with OPENAI_API_KEY configured.')
    records=[];calls=0;original=app.ask
    original_open=app.urllib.request.urlopen
    @contextlib.contextmanager
    def observed_open(request,**kwargs):
        started=time.monotonic()
        with original_open(request,**kwargs) as response:body=json.load(response)
        print(json.dumps({'event':'evaluation_usage','model':json.loads(request.data)['model'],
                          'seconds':round(time.monotonic()-started,3),'usage':body.get('usage',{})}),flush=True)
        yield io.StringIO(json.dumps(body))
    def measured(task,data,schema,**kwargs):
        nonlocal calls
        calls+=1
        if calls>30:raise RuntimeError('Evaluation stopped at 30 calls')
        return original(task,data,schema,**kwargs)
    for model in ('gpt-6-astra','gpt-6-sol','gpt-6-luna'):
      for language in ('ru','uk'):
        for case in ('reference','grade','reflection'):
          started=time.monotonic();log=io.StringIO();out=None;error=None;passed=False
          try:
            with patch.dict(os.environ,{'OPENAI_ROUTING_ENABLED':'false','OPENAI_MODEL':model}), \
                 patch.object(app,'ask',side_effect=measured), \
                 patch.object(app.urllib.request,'urlopen',side_effect=observed_open), contextlib.redirect_stdout(log):
              if case=='reference':
                text={'ru':'добавь послание Иакова первую главу стихи девятнадцатый и двадцатый',
                      'uk':'додай послання Якова перший розділ вірші дев’ятнадцятий і двадцятий'}[language]
                out=app.import2({'text':text,'translation':language})
                ids={atom for p in out['passages'] for atom in p['id'].split('~')}
                passed=ids=={f'{language}|James|1|19',f'{language}|James|1|20'}
              elif case=='grade':
                target=app.convert(app.local_import2('Притчи 15:1','ru')[0],language)
                situation={'ru':'Коллега резко раскритиковал мою работу при всех. Хочется ответить оскорблением.',
                           'uk':'Колега різко розкритикував мою роботу при всіх. Хочеться відповісти образою.'}
                answer={'ru':'Иакова 1:19–20. Сначала выслушать, не отвечать в гневе, а затем спокойно обсудить претензию.',
                        'uk':'Якова 1:19–20. Спочатку вислухати, не відповідати в гніві, а потім спокійно обговорити претензію.'}[language]
                out=app.evaluate2({'translation':language,'target':target,'situation':situation},answer,[])
                passed=out['correct'] and out['xp']==5 and out['passage']['book']=='James'
              else:
                ids=[p['id'] for ref in ('Иакова 1:19–20','Притчи 15:1','Матфея 6:34')
                     for p in [app.convert(app.local_import2(ref,'ru')[0],language)]]
                text={'ru':'Сегодня я накричал на коллегу из-за замечания. Хочу в следующий раз сначала выслушать и спокойно ответить.',
                      'uk':'Сьогодні я накричав на колегу через зауваження. Хочу наступного разу спочатку вислухати й спокійно відповісти.'}[language]
                out=app.reflect2({'text':text,'scope':'library','ids':ids,'translation':language})
                passed=1<=len(out['suggestions'])<=2 and all(s['passage']['id'] in ids for s in out['suggestions'])
          except Exception as exc:error=type(exc).__name__+': '+str(exc)
          usage=[json.loads(line) for line in log.getvalue().splitlines() if line.startswith('{')]
          records.append({'model':model,'language':language,'case':case,'automatic_checks_passed':passed,
                          'seconds':round(time.monotonic()-started,2),'usage':usage,'output':out,'error':error})
    print(json.dumps({'calls':min(calls,30),'manual_review_required':True,'results':records},ensure_ascii=False,indent=2))

if __name__=='__main__':run()
