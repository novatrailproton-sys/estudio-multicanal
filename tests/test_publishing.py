import json
import httpx
import pytest

from estudio.db import uid
from estudio.models import PublishInput
from estudio.pipeline import Pipeline
from estudio.providers import Blocked
from estudio.publishing import allowed_upload, publications, publish, schedule
from test_render import production_fixture


def ready(store,project):
    p=production_fixture(store,project)
    video=store.root/'assets'/'output.mp4'
    # Publisher transport contract uses a bounded binary fixture. The renderer
    # itself is exercised separately with real FFmpeg and full decoding.
    video.write_bytes(b'test-video-content')
    asset=store.add_asset(p['id'],video,{'kind':'video','role':'output','rights':'project'})
    return store.change(p['id'],{'output_asset':asset['id'],'technical_report':{'decoded':True},'review':{**p['review'],'playback':True}},content=False)


def test_schedule_no_duplicates_and_stale_revision(store,vault,project):
    p=ready(store,project)
    config=PublishInput(platform='youtube',title='Prueba',authorize=True).model_dump()
    job=schedule(store,p,config)
    with pytest.raises(ValueError,match='publicación'):
        schedule(store,p,config)
    store.change(p['id'],{'title':'Cambio posterior'})
    with pytest.raises(Blocked,match='cambió'):
        publish(store,vault,job,lambda:False,lambda _:None)
    assert publications(store,p['id'])[0]['status']=='blocked'


def test_youtube_contract_and_lost_reply_no_retry(store,vault,project):
    p=ready(store,project)
    vault.set('youtube.default','fake-account-token')
    store.save_setting('youtube.default',{'permissions_confirmed':True})
    config=PublishInput(platform='youtube',title='Prueba',authorize=True).model_dump()
    job=schedule(store,p,config)
    calls=[]
    def transport(req):
        calls.append(req)
        if req.method=='POST':
            assert json.loads(req.content)['status']['containsSyntheticMedia'] is True
            return httpx.Response(200,headers={'Location':'https://www.googleapis.com/upload/session'})
        assert req.method=='PUT'
        raise httpx.ReadError('Reply lost')
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(httpx.ReadError):
            publish(store,vault,job,lambda:False,lambda _:None,client)
        assert publications(store,p['id'])[0]['status']=='unknown'
        with pytest.raises(Blocked,match='ya se intentó'):
            publish(store,vault,job,lambda:False,lambda _:None,client)
    assert len(calls)==2


def test_youtube_success_confirms_identifier(store,vault,project):
    p=ready(store,project)
    vault.set('youtube.default','fake-account-token')
    store.save_setting('youtube.default',{'permissions_confirmed':True})
    job=schedule(store,p,PublishInput(platform='youtube',title='Prueba',authorize=True).model_dump())
    def transport(req):
        if req.method=='POST':return httpx.Response(200,headers={'Location':'https://www.googleapis.com/upload/session'})
        return httpx.Response(201,json={'id':'confirmed-video-id'})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        publish(store,vault,job,lambda:False,lambda _:None,client)
    pub=publications(store,p['id'])[0]
    assert pub['status']=='uploaded'
    assert pub['data']['remote_id']=='confirmed-video-id'
    assert 'fake-account-token' not in json.dumps(pub)


def test_upload_redirect_hosts_are_restricted():
    for platform in ('youtube','facebook','tiktok'):
        with pytest.raises(Blocked):allowed_upload('https://evil.example/upload',platform)
    assert allowed_upload('https://www.googleapis.com/upload/session','youtube')
    assert allowed_upload('https://rupload.facebook.com/video-upload/123','facebook')
    assert allowed_upload('https://open-upload.tiktokapis.com/video/','tiktok')


def test_tiktok_queries_creator_before_init_and_preserves_publish_id(store,vault,project):
    p=ready(store,project)
    vault.set('tiktok.default','test-tiktok-token')
    store.save_setting('tiktok.default',{'permissions_confirmed':True})
    job=schedule(store,p,PublishInput(platform='tiktok',title='Prueba',privacy='SELF_ONLY',authorize=True).model_dump())
    paths=[]
    def transport(req):
        paths.append(req.url.path)
        if 'creator_info' in req.url.path:return httpx.Response(200,json={'error':{'code':'ok'},'data':{'privacy_level_options':['SELF_ONLY'],'max_video_post_duration_sec':180}})
        if req.url.path.endswith('/init/'):
            body=json.loads(req.content)
            assert body['post_info']['is_aigc'] is True
            assert body['post_info']['privacy_level']=='SELF_ONLY'
            return httpx.Response(200,json={'error':{'code':'ok'},'data':{'publish_id':'confirmed-publish-id','upload_url':'https://open-upload.tiktokapis.com/upload'}})
        assert req.headers['content-range']=='bytes 0-17/18'
        return httpx.Response(201)
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        publish(store,vault,job,lambda:False,lambda _:None,client)
    pub=publications(store,p['id'])[0]
    assert pub['status']=='processing'
    assert pub['data']['remote_id']=='confirmed-publish-id'
    assert 'creator_info' in paths[0]


def test_facebook_reel_three_phases(store,vault,project):
    p=ready(store,project)
    vault.set('facebook.default','test-facebook-token')
    store.save_setting('facebook.default',{'permissions_confirmed':True,'page_id':'123456','api_version':'v25.0'})
    job=schedule(store,p,PublishInput(platform='facebook',title='Prueba',privacy='public',authorize=True).model_dump())
    phases=[]
    def transport(req):
        if req.url.host=='rupload.facebook.com':
            assert req.headers['authorization']=='OAuth test-facebook-token'
            return httpx.Response(200,json={'success':True})
        from urllib.parse import parse_qs
        data=parse_qs(req.content.decode())
        phase=data['upload_phase'][0];phases.append(phase)
        if phase=='start':return httpx.Response(200,json={'video_id':'confirmed-fb-id','upload_url':'https://rupload.facebook.com/upload'})
        assert data['video_state']==['PUBLISHED']
        return httpx.Response(200,json={'success':True})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        publish(store,vault,job,lambda:False,lambda _:None,client)
    assert phases==['start','finish']
    assert publications(store,p['id'])[0]['status']=='processing'
