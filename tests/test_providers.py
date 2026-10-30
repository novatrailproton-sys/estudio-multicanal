import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import wave

import httpx
import pytest

from estudio.media import ffmpeg, plan_basic, probe, run
from estudio.pipeline import Pipeline, quality
from estudio.providers import Blocked, Providers
from conftest import image_bytes, wav_bytes


def test_sdxl_real_bytes_contract_and_cache(store,vault):
    calls=[]
    def respond(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200,content=image_bytes())
    provider=Providers(store,vault,transport=httpx.MockTransport(respond))
    first=provider.image('A bright blue ocean with a small white boat, cinematic natural light.')
    assert first.is_file()
    assert provider.image('A bright blue ocean with a small white boat, cinematic natural light.')==first
    assert len(calls)==1
    assert 'negative_prompt' in calls[0]


def test_riva_trusts_actual_wav_header(store,vault,tmp_path):
    def respond(req):
        value=json.loads(req.content)
        assert value['language_code']=='es-ES'
        return httpx.Response(200,content=wav_bytes(2,24000))
    provider=Providers(store,vault,transport=httpx.MockTransport(respond))
    target=tmp_path/'voice.wav'
    provider.tts_scene('[whispering] Un planeta azul aparece.', 'Spanish-ES-Male-1',target)
    with wave.open(str(target)) as audio:
        assert audio.getframerate()==24000
        assert audio.getnframes()==48000


def test_bridge_character_payload_cache_and_no_paid_fallback(store,vault,project,tmp_path):
    clip=tmp_path/'clip.mp4'
    run([ffmpeg(),'-y','-v','error','-f','lavfi','-i','testsrc2=size=160x284:rate=24','-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(clip)])
    ref=tmp_path/'ref.png';ref.write_bytes(image_bytes())
    audio=tmp_path/'voice.wav';audio.write_bytes(wav_bytes(2))
    config={'url':'https://media.example','model':'free-test','zero_cost_confirmed':True,'evidence_url':'https://media.example/terms',
            'valid_until':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'capabilities':['video','reference','lipsync']}
    store.save_setting('bridge',config)
    scene={**plan_basic(project['script'],2,'characters')[0],'prompt':'A consistent character speaks softly.','end':2}
    calls=[]
    def respond(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200,json={'cost':0,'kind':'video','b64_json':base64.b64encode(clip.read_bytes()).decode()})
    provider=Providers(store,vault,transport=httpx.MockTransport(respond))
    with pytest.raises(Blocked,match='referencia'):
        provider.bridge(scene,project,audio,[])
    path=provider.bridge(scene,project,audio,[ref])
    assert probe(path)['duration']>=2
    assert calls[0]['budget']=={'maximum_cost':0,'paid_fallback':False}
    assert calls[0]['references'][0]['b64_json']
    assert calls[0]['audio_b64']
    assert provider.bridge(scene,project,audio,[ref])==path
    assert len(calls)==1


def test_character_missing_connector_stays_character(store,vault,project):
    project=store.change(project['id'],{'mode':'characters','audio_source':'upload'})
    audio=store.root/'assets'/'voice.wav';audio.write_bytes(wav_bytes(8))
    asset=store.add_asset(project['id'],audio,{'kind':'audio','rights':'own','role':'narration'})
    scenes=plan_basic(project['script'],8,'characters')
    for s in scenes:s['prompt']='A character speaking in a bright room.'
    store.change(project['id'],{'audio_asset':asset['id'],'scenes':scenes})
    with pytest.raises(Blocked):
        Pipeline(store,vault).generate(project['id'],Providers(store,vault),lambda:False,lambda _:None)
    actual=store.project(project['id'])
    assert all(s['kind']=='character' and not s['visual_asset'] for s in actual['scenes'])


def test_plan_rejects_missing_scene_ids(store,vault,project):
    store.change(project['id'],{'planner':'openrouter'})
    class BadPlan:
        def text(self,*args):return {'visual_bible':'A blue room','scenes':[]}
    with pytest.raises(Blocked,match='omitió'):
        Pipeline(store,vault).prepare(project['id'],BadPlan(),lambda:False,lambda _:None)
    assert store.project(project['id'])['scenes']==[]
