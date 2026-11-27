from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json, os, sys, time
root=Path.cwd()
repo=root
sys.path[:0]=[str(repo/'src'),str(repo)]
os.environ['QT_QPA_PLATFORM']='offscreen'
for key in ('CLICKNTRANSLATE_LIBRETRANSLATE_API_KEY','CLICKNTRANSLATE_LIBRETRANSLATE_URL'):os.environ.pop(key,None)
import translater
source='Good morning. Thank you very much.'
def probe(provider):
    ctx=translater._TranslationCache('en','ru',config={})
    ctx.data_dir=None
    start=time.perf_counter()
    try:
        result=translater.translate_text(source,'en','ru',engine=provider,_context=ctx)
        record={'text':result,'received_russian':any('а'<=v.lower()<='я' for v in result)}
    except Exception as e:record={'error':str(e)[:600]}
    record['seconds']=round(time.perf_counter()-start,2)
    return provider,record
with ThreadPoolExecutor(max_workers=3) as pool:
    outcomes=dict(pool.map(probe,['Google','MyMemory','Lingva','LibreTranslate']))
(root/'online-providers.json').write_text(json.dumps({'input':source,'pair':'en→ru','candidate':'eec0ed7951b1dafbe6479701162b6ca0d57ee324','runner':'GitHub macos-15','providers':outcomes},ensure_ascii=False,indent=2),encoding='utf-8')
for name,v in outcomes.items():print(name,'OK' if v.get('received_russian') else str(v.get('error','invalid result'))[:190],v['seconds'])
