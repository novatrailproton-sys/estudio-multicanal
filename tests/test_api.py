import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from estudio.media import plan_basic
from estudio.pipeline import Pipeline
from estudio.server import create_app
from conftest import api_project, image_bytes, wav_bytes


def test_csrf_host_and_read_session(tmp_path):
    app=create_app(tmp_path,start_worker=False)
    with TestClient(app) as client:
        assert client.get('/api/state').status_code==403
        assert client.post('/api/channels',json={"name":"x"}).status_code==403
        assert client.get('/',headers={"Host":"attacker.example"}).status_code==403
        response=client.get('/')
        assert 'Content-Security-Policy' in response.headers
        assert 'httponly' in response.headers['set-cookie'].lower()
        headers={"X-Studio-Token":app.state.token,"Origin":"https://attacker.example"}
        assert client.post('/api/channels',json={"name":"x"},headers=headers).status_code==403


def test_import_audio_prepare_scene_edit_and_rights(client):
    p=api_project(client)
    store=client.app.state.store
    pipeline=Pipeline(store,client.app.state.vault)
    from estudio.providers import Providers,Blocked
    provider=Providers(store,client.app.state.vault)
    with pytest.raises(Blocked):
        pipeline.prepare(p['id'],provider,lambda:False,lambda _:None)
    p=client.get('/api/projects/'+p['id']).json()
    assert p['scenes']
    response=client.post('/api/projects/'+p['id']+'/assets?role=narration&rights=own',files={'file':('voice.wav',wav_bytes(),'audio/wav')})
    assert response.status_code==200,response.text
    pipeline.prepare(p['id'],provider,lambda:False,lambda _:None)
    p=client.get('/api/projects/'+p['id']).json()
    assert p['scenes'][-1]['end']==8
    scene=p['scenes'][0]
    response=client.post('/api/projects/'+p['id']+'/assets?role=scene&rights=own&scene_id='+scene['id'],files={'file':('../../escape.png',image_bytes(),'image/png')})
    assert response.status_code==200,response.text
    assert not (store.root.parent/'escape.png').exists()
    p=client.get('/api/projects/'+p['id']).json()
    assert 'path' not in p['assets'][0]
    assert client.get('/media/'+response.json()['id']).status_code==200
    scenes=p['scenes']
    scenes[0]['prompt']='A small planet above a bright blue sky, natural documentary photograph.'
    assert client.put('/api/projects/'+p['id']+'/scenes',json={'revision':1,'scenes':scenes}).status_code==400
    result=client.put('/api/projects/'+p['id']+'/scenes',json={'revision':p['revision'],'scenes':scenes})
    assert result.status_code==200,result.text
    assert result.json()['scenes'][0]['visual_asset']==p['scenes'][0]['visual_asset']


def test_cross_project_assets_rejected(client):
    a,b=api_project(client),api_project(client)
    asset=client.post('/api/projects/'+a['id']+'/assets?role=reference&rights=own',files={'file':('reference.png',image_bytes())}).json()
    store=client.app.state.store
    scenes=plan_basic(b['script'],8,'narration')
    scenes[0]['reference_ids']=[asset['id']]
    result=client.put('/api/projects/'+b['id']+'/scenes',json={'revision':b['revision'],'scenes':scenes})
    assert result.status_code==400


def test_invalid_import_and_no_secret_readback(client):
    p=api_project(client)
    r=client.post('/api/projects/'+p['id']+'/assets?role=narration',files={'file':('broken.wav',b'not media')})
    assert r.status_code==400
    assert client.post('/api/connections/key',json={'name':'openrouter','key':'example-very-private-token','remember':False}).status_code==200
    r=client.get('/api/connections')
    assert r.json()['keys']['openrouter'] is True
    assert 'example-very-private-token' not in r.text
    package=client.get('/api/projects/'+p['id']+'/package')
    assert package.status_code==200,package.text
    import zipfile
    with zipfile.ZipFile(io.BytesIO(package.content)) as z:
        assert all('example-very-private-token' not in z.read(name).decode('utf-8','ignore') for name in z.namelist())


def test_scene_gap_and_early_playback_review_rejected(client):
    p=api_project(client)
    scenes=plan_basic(p['script'],8,'narration')
    scenes[0]['start']=2
    result=client.put('/api/projects/'+p['id']+'/scenes',json={'revision':p['revision'],'scenes':scenes})
    assert result.status_code==400
    result=client.put('/api/projects/'+p['id']+'/review',json={'revision':p['revision'],'review':{'playback':True}})
    assert result.status_code==400


def test_publication_requires_real_export_and_consent(client):
    p=api_project(client)
    url='/api/projects/'+p['id']+'/publish'
    assert client.post(url,json={'platform':'youtube','title':'Prueba','authorize':False}).status_code==400
    assert client.post(url,json={'platform':'youtube','title':'Prueba','authorize':True}).status_code==400


def test_example_starts_free_generation_without_approving_content(client):
    response=client.post('/api/example')
    assert response.status_code==200,response.text
    p=response.json()
    assert p['audio_source']=='riva' and p['image_source']=='sdxl'
    assert p['planner']=='manual' and p['format']=='pilot'
    assert p['review']=={} and not p['output_asset']
    jobs=client.app.state.store.jobs(p['id'])
    assert len(jobs)==1 and jobs[0]['kind']=='generate' and jobs[0]['status']=='queued'
