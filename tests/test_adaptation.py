from estudio.media import plan_basic
from conftest import api_project, wav_bytes, image_bytes


def test_adaptation_reuses_resources_and_preserves_clip_offsets(client):
    p=api_project(client,format='long',duration=300)
    store=client.app.state.store
    audio=store.root/'assets'/'long.wav';audio.write_bytes(wav_bytes(110))
    visual=store.root/'assets'/'clip-placeholder.mp4';visual.write_bytes(b'offset-contract-fixture')
    aid=store.add_asset(p['id'],audio,{'kind':'audio','role':'narration','rights':'own'})['id']
    vid=store.add_asset(p['id'],visual,{'kind':'video','role':'scene','rights':'own'})['id']
    scenes=plan_basic(p['script'],110,'narration')
    scenes=[{**scenes[0],'start':0,'end':110,'kind':'clip','visual_asset':vid,'source_offset':3,
             'effects':[{'type':'chime','offset':5,'gain':.1},{'type':'whoosh','offset':20,'gain':.2}]}]
    store.change(p['id'],{'audio_asset':aid,'scenes':scenes})
    result=client.post('/api/projects/'+p['id']+'/adapt',json={'start':10,'end':100})
    assert result.status_code==200,result.text
    child=result.json()
    assert child['parent_id']==p['id']
    assert child['format']=='reel' and child['aspect']=='9:16'
    assert child['scenes'][0]['source_offset']==13
    assert child['scenes'][0]['start']==0 and child['scenes'][0]['end']==90
    assert child['scenes'][0]['effects']==[{'type':'whoosh','offset':10,'gain':.2}]
    assert child['review']=={}
    assert store.asset_path(child['scenes'][0]['visual_asset'],child['id'])==visual


def test_image_does_not_substitute_character_and_no_orphan(client):
    p=api_project(client,mode='characters')
    store=client.app.state.store
    scenes=plan_basic(p['script'],8,'characters')
    store.change(p['id'],{'scenes':scenes})
    result=client.post('/api/projects/'+p['id']+'/assets?role=scene&rights=own&scene_id='+scenes[0]['id'],files={'file':('image.png',image_bytes())})
    assert result.status_code==400
    assert not store.assets(p['id'])


def test_fifteen_minute_timeline_is_accepted_without_fake_render(client):
    from estudio.pipeline import validate_timeline
    p=api_project(client,format='long',duration=900)
    scenes=plan_basic(p['script'],900,'narration')
    assert not validate_timeline({**p,'scenes':scenes})
    assert max(s['end'] for s in scenes)==900
    # The production performance and a complete 15-minute render still need
    # hardware benchmarking; accepting this timeline isn't a performance claim.
