from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import time

import httpx
import pytest

from estudio.db import Store
from estudio.media import clean_script, plan_basic
from estudio.models import ProjectInput, SceneInput
from estudio.pipeline import Worker
from estudio.providers import Blocked, Providers, Quota, require_free, validate_endpoint
from estudio.security import InstanceLock, redact


@pytest.mark.parametrize("format,duration,valid", [("reel",90,True),("reel",150,True),("reel",89,False),("reel",151,False),
    ("long",300,True),("long",900,True),("long",901,False),("long",299,False),("pilot",30,True),("pilot",31,False)])
def test_duration_limits(format,duration,valid):
    value = dict(channel_id="channel", title="Prueba", format=format, duration=duration)
    if valid:
        assert ProjectInput(**value).duration == duration
    else:
        with pytest.raises(ValueError):
            ProjectInput(**value)


def test_queue_single_claim_and_restart(store,project):
    job = store.enqueue(project["id"], "prepare")
    with pytest.raises(ValueError):
        store.enqueue(project["id"], "generate")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.claim(), range(4)))
    assert sum(r is not None for r in results) == 1
    reopened = Store(store.root)
    reopened.recover()
    assert reopened.job(job["id"])["status"] == "queued"
    reopened.set_job(job["id"],status="cancelled")
    assert reopened.enqueue(project["id"], "render")


def test_revision_and_scene_preservation(store,project):
    scenes = plan_basic(project["script"],8,"narration")
    p = store.change(project["id"],{"scenes":scenes})
    store.change(p["id"],{"review":{"editorial":True}},content=False)
    with pytest.raises(ValueError):
        store.change(p["id"],{"title":"old"}, expected=1)
    p = store.change(p["id"],{"visual_bible":"Cambio de luz"},expected=p["revision"])
    assert p["scenes"] == scenes
    assert p["review"] == {}
    assert not p["output_asset"]


def test_quota_persists_and_prevents_calls(store,vault):
    calls=[]
    def respond(req):
        calls.append(req)
        return httpx.Response(429,headers={"Retry-After":"3600"})
    provider=Providers(store,vault,transport=httpx.MockTransport(respond))
    with pytest.raises(Quota) as result:
        provider.request("test","https://example.com/api",{})
    assert result.value.until > time.time()+3500
    provider=Providers(Store(store.root),vault,transport=httpx.MockTransport(respond))
    with pytest.raises(Quota):
        provider.request("test","https://example.com/api",{})
    assert len(calls)==1


def test_waiting_job_preserves_work(store,vault,project):
    class Waiting:
        provider_factory=Providers
        def prepare(self,*args):
            raise Quota("Esperar",time.time()+7200)
    job=store.enqueue(project["id"],"prepare")
    Worker(store,vault,Waiting()).execute(store.claim())
    assert store.job(job["id"])["status"]=="waiting"
    assert store.claim() is None
    assert store.project(project["id"])["script"]==project["script"]


def test_free_policy_and_endpoint_restrictions():
    config={"zero_cost_confirmed":True,"evidence_url":"https://provider.example/terms", "valid_until":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
            "price_per_input_token":0,"price_per_output_token":0}
    require_free(config,pricing=True)
    for changes in ({"price_per_input_token":.1},{"price_per_output_token":None},{"valid_until":"2020-01-01T00:00:00Z"},{"zero_cost_confirmed":False}):
        with pytest.raises(Blocked):
            require_free({**config,**changes},pricing=True)
    for url in ("http://provider.example/api","file:///etc/passwd","https://user:pass@example.com","https://example.com?token=secret"):
        with pytest.raises(Blocked):
            validate_endpoint(url)
    assert validate_endpoint("http://127.0.0.1:20128/v1/").endswith("/v1")


def test_no_plaintext_keys(vault,store):
    vault.set("openrouter","example-private-value",remember=False)
    assert vault.get("openrouter")=="example-private-value"
    with pytest.raises(ValueError):
        vault.set("groq","another-private-value",remember=True)
    assert not (store.root/"credentials").exists()
    assert "example-private-value" not in redact("error example-private-value",vault.secrets())
    vault.delete("openrouter")
    assert not vault.get("openrouter")
    with pytest.raises(ValueError):
        vault.set("../bad","secret")


def test_instance_lock(store):
    first,second=InstanceLock(store.root),InstanceLock(store.root)
    first.acquire()
    try:
        with pytest.raises(RuntimeError):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_script_tags_and_semantic_plan():
    assert clean_script('[whispering] Hola. <#1.0#> [long pause] Adiós.')=='Hola. Adiós.'
    scenes=plan_basic("Una frase completa. Otra frase también completa.\nLa última frase.",25,"mixed")
    assert scenes[0]["start"]==0
    assert scenes[-1]["end"]==25
    assert " ".join(s["text"] for s in scenes)=="Una frase completa. Otra frase también completa. La última frase."
    assert all(s["end"]>s["start"] for s in scenes)
