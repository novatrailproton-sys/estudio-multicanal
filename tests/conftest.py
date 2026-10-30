import io
import math
from pathlib import Path
import wave
from array import array

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from estudio.db import Store
from estudio.models import Channel, ProjectInput
from estudio.security import Vault
from estudio.server import create_app


def wav_bytes(duration=8, rate=16000):
    buf = io.BytesIO()
    samples = array("h", (int(2200*math.sin(2*math.pi*180*n/rate)) for n in range(round(duration*rate))))
    with wave.open(buf, "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        out.writeframes(samples.tobytes())
    return buf.getvalue()


def image_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (480, 640), "#304e65").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path/"data")


@pytest.fixture
def vault(store):
    result = Vault(store.root)
    result.backend = "memory"
    return result


@pytest.fixture
def project(store):
    channel = store.save_channel(Channel(name="Pruebas", theme="Ciencia y relatos").model_dump())
    return store.create_project(ProjectInput(channel_id=channel, title="Un amanecer diferente", script="El cielo cambió al amanecer. Nadie había visto un color como aquel.",
                                             format="pilot", duration=8).model_dump())


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path/"web-data", start_worker=False)
    app.state.vault.backend = "memory"
    with TestClient(app) as client:
        client.get("/")
        client.headers["X-Studio-Token"] = app.state.token
        yield client


def api_project(client, **changes):
    channel = client.get("/api/state").json()["channels"][0]["id"]
    response = client.post("/api/projects", json={"channel_id": channel, "title": "Prueba", "format": "pilot", "duration": 8,
                           "script": "El cielo cambió al amanecer. Un pequeño planeta apareció entre las nubes.", **changes})
    assert response.status_code == 200, response.text
    return response.json()
