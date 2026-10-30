import os
from pathlib import Path

from estudio.db import Store
from estudio.media import ffmpeg, probe
from estudio.models import Channel, ProjectInput
from estudio.pipeline import Pipeline
from estudio.security import Vault
from test_render import production_fixture


def test_portable_ffmpeg_unicode_space_and_apostrophe(tmp_path,monkeypatch):
    import imageio_ffmpeg
    import estudio.media as media
    root=tmp_path/"José's proyectos"
    store=Store(root)
    channel=store.save_channel(Channel(name='Canal').model_dump())
    project=store.create_project(ProjectInput(channel_id=channel,title='Prueba portable',format='pilot',duration=5,script='La costa tiene un color especial.').model_dump())
    project=production_fixture(store,project,duration=5)
    monkeypatch.setattr(media,'ffmpeg',imageio_ffmpeg.get_ffmpeg_exe)
    original_which=media.shutil.which
    monkeypatch.setattr(media.shutil,'which',lambda name: None if name=='ffprobe' else original_which(name))
    Pipeline(store,Vault(root)).render(project['id'],lambda:False,lambda _:None)
    project=store.project(project['id'])
    assert project['technical_report']['decoded']
    assert abs(probe(store.asset_path(project['output_asset']))['duration']-5)<.3
