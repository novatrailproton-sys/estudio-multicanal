"""Explicit, opt-in live smoke test of anonymous image and speech endpoints.

Creates one fictional 5–30 second test, not a publishable production approval.
No accounts, keys, billing, or publication calls. May stop on quota/unavailability.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from estudio.db import Store
from estudio.media import plan_basic
from estudio.models import Channel, ProjectInput
from estudio.pipeline import Pipeline
from estudio.providers import Providers, Quota
from estudio.security import Vault


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',required=True,help='Directorio independiente para la prueba')
    args=parser.parse_args()
    store=Store(args.data)
    vault=Vault(store.root)
    channel=store.save_channel(Channel(name='Pruebas de conexiones',theme='Relatos de viaje',style='Warm natural travel photography, peaceful coastline, teal ocean, golden sunrise').model_dump())
    script='En aquella isla, el amanecer tenía un color distinto. Clara encontró un pequeño bote y decidió explorar la costa.'
    project=store.create_project(ProjectInput(channel_id=channel,title='Prueba: la isla al amanecer',format='pilot',duration=15,
                  script=script,audio_source='riva',image_source='sdxl',subtitles=True).model_dump())
    scenes=plan_basic(script,15,'narration')
    # Keep one resource for a bounded anonymous test, with a coherent single shot.
    scenes=[{**scenes[0],'text':script,'start':0,'end':15,
        'prompt':'A peaceful tropical island coastline at sunrise, a small empty wooden boat on turquoise water, golden sunlight, lush hills in distance, cinematic natural travel photography, vertical composition, no text, no people.'}]
    store.change(project['id'],{'scenes':scenes,'visual_bible':'Peaceful tropical coastline, small weathered wooden boat, turquoise sea, warm golden sunrise, natural travel photography.'})
    pipeline=Pipeline(store,vault)
    provider=Providers(store,vault,log=print)
    try:
        pipeline.prepare(project['id'],provider,lambda:False,print)
        pipeline.generate(project['id'],provider,lambda:False,print)
        p=store.project(project['id'])
        # This is a technical test of a fixed fictional sample. Playback is never
        # approved automatically and no publisher is invoked.
        store.change(p['id'],{'review':{'editorial':True,'rights':True,'timing':True,'continuity':True},'test_only':True},content=False)
        pipeline.render(p['id'],lambda:False,print)
        p=store.project(p['id'])
        print(json.dumps({'project_id':p['id'],'output':str(store.asset_path(p['output_asset'])),'technical_report':p['technical_report'],
                          'review_required':True},ensure_ascii=False,indent=2))
    except Quota as exc:
        print('Prueba detenida: '+str(exc))
        print('Los recursos terminados están conservados en '+str(store.root))
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
