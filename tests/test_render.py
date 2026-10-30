import io
import json
from pathlib import Path
import zipfile

from estudio.media import plan_basic, probe, synthetic_effect, write_srt
from estudio.pipeline import Pipeline, quality
from conftest import image_bytes, wav_bytes


def production_fixture(store,project,duration=8):
    audio=store.root/'assets'/'narration.wav';audio.write_bytes(wav_bytes(duration))
    music=store.root/'assets'/'music.wav';music.write_bytes(wav_bytes(2))
    image=store.root/'assets'/'image.png';image.write_bytes(image_bytes())
    aid=store.add_asset(project['id'],audio,{'kind':'audio','rights':'own','role':'narration'})['id']
    mid=store.add_asset(project['id'],music,{'kind':'audio','rights':'own','role':'music'})['id']
    iid=store.add_asset(project['id'],image,{'kind':'image','rights':'own','role':'scene'})['id']
    scenes=plan_basic(project['script'],duration,'narration')
    for s in scenes:
        s.update(visual_asset=iid,prompt='A small planet in a clear blue sky.',effects=[{'type':'chime','offset':1,'gain':.1}],transition='fade')
    p=store.change(project['id'],{'audio_asset':aid,'music_asset':mid,'scenes':scenes})
    return store.change(p['id'],{'review':{'editorial':True,'rights':True,'timing':True,'continuity':True}},content=False)


def test_real_ffmpeg_export_subtitles_mix_and_package(store,vault,project):
    p=production_fixture(store,project)
    assert quality(store,p)['ok']
    pipeline=Pipeline(store,vault)
    pipeline.render(p['id'],lambda:False,lambda _:None)
    final=store.project(p['id'])
    assert final['state']=='ready'
    info=probe(store.asset_path(final['output_asset']))
    assert abs(info['duration']-8)<.3
    assert info['audio'] and info['video']
    assert info['width']==720 and info['height']==1280
    assert final['technical_report']['decoded']
    assert not quality(store,final,publishing=True)['ok'] # Needs final playback.
    final=store.change(p['id'],{'review':{**final['review'],'playback':True}},content=False)
    assert quality(store,final,publishing=True)['ok']
    package=pipeline.package(p['id'])
    with zipfile.ZipFile(package) as output:
        assert {'project.json','script.txt','subtitles.srt','provenance.json','timeline.csv','quality.json'}<=set(output.namelist())
        assert json.loads(output.read('quality.json'))['ok']
    segments=list((store.root/'work'/p['id']/'render').glob('[a-f0-9]'*64+'.mp4'))
    before={path:path.stat().st_mtime for path in segments}
    pipeline.render(p['id'],lambda:False,lambda _:None)
    assert all(path.stat().st_mtime==mtime for path,mtime in before.items())


def test_transcribed_captions_use_measured_words(tmp_path):
    path=tmp_path/'subtitles.srt'
    write_srt([{'text':'Hola mundo','start':0,'end':5}],path,[{'word':'Hola','start':1.2,'end':1.5},{'word':'mundo','start':2,'end':2.4}])
    assert '00:00:01,200 --> 00:00:02,400' in path.read_text()


def test_rights_and_character_review_are_real_gates(store,project):
    p=production_fixture(store,project)
    p['scenes'][0]['kind']='character'
    report=quality(store,p)
    assert not report['ok']
    assert any('labial' in e for e in report['errors'])
    assert any('identidad' in e for e in report['errors'])


def test_factual_needs_sources_and_review(store,project):
    p=production_fixture(store,project)
    p['content_type']='factual'
    assert any('fuentes' in e for e in quality(store,p)['errors'])
    p['sources']=[{'title':'Fuente primaria','url':'https://example.com/research','claim':'Afirmación revisada'}]
    p['review']['factual']=True
    assert quality(store,p)['ok']
