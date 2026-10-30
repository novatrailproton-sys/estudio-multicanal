from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import time
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from PIL import Image, ImageOps

from .db import Store, uid
from .media import clean_script, ffmpeg, fit_timing, plan_basic, probe, run
from .models import BridgeConfig, Channel, GatewayConfig, ProjectInput, PublishInput, Review, SceneInput
from .pipeline import Pipeline, Worker, quality, validate_timeline
from .providers import Blocked, validate_endpoint
from .publishing import publications, refresh, schedule
from .security import InstanceLock, Vault, redact

WEB = Path(__file__).parent/"web"


def public_asset(asset):
    return {k: v for k, v in asset.items() if k != "path"}


def create_app(root=None, start_worker=True):
    root = root or os.getenv("ESTUDIO_DATA") or Path.home()/"EstudioMulticanal"
    store, vault = Store(root), Vault(root)
    worker, lock = Worker(store, vault), InstanceLock(root)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        lock.acquire()
        if not store.list_channels():
            store.save_channel(Channel(name="Mi canal").model_dump())
        if start_worker:
            worker.start()
        try:
            yield
        finally:
            if start_worker:
                worker.close()
            lock.release()

    app = FastAPI(title="Estudio Multicanal", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.vault, app.state.worker, app.state.token = store, vault, worker, token

    @app.middleware("http")
    async def local_security(request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "El estudio solo admite conexiones locales."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("content-length", "0").isdigit() and int(request.headers.get("content-length", "0")) > 550*1024*1024:
                return JSONResponse({"detail": "La petición supera el límite de importación."}, status_code=413)
            if not secrets.compare_digest(request.headers.get("x-studio-token", ""), token):
                return JSONResponse({"detail": "Sesión no válida. Recarga el estudio."}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != "http://"+request.headers.get("host"):
                return JSONResponse({"detail": "Origen no autorizado."}, status_code=403)
        if request.url.path.startswith(("/api/", "/media/")):
            # All reads containing project material are session protected too.
            session = request.cookies.get("studio_session", "")
            if not secrets.compare_digest(session, token) and request.headers.get("x-studio-token") != token:
                return JSONResponse({"detail": "Abre primero la página principal del estudio."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse({"detail": redact(str(exc), vault.secrets())[:1800]}, status_code=400)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return JSONResponse({"detail": "No se pudo completar la operación. Se conservan los proyectos; revisa el formato y vuelve a intentarlo."}, status_code=500)

    def idle(project_id):
        if any(j["status"] == "running" and j["kind"] != "publish" for j in store.jobs(project_id)):
            raise ValueError("Este proyecto está trabajando. Cancela o espera antes de editarlo.")

    @app.get("/", response_class=HTMLResponse)
    def home():
        html = (WEB/"index.html").read_text("utf-8").replace("__STUDIO_TOKEN__", token)
        response = HTMLResponse(html)
        response.set_cookie("studio_session", token, httponly=True, samesite="strict", path="/")
        return response

    @app.get("/app.js")
    def js():
        return FileResponse(WEB/"app.js", media_type="application/javascript")

    @app.get("/style.css")
    def css():
        return FileResponse(WEB/"style.css", media_type="text/css")

    @app.get("/api/state")
    def state():
        projects = [{k: p[k] for k in ("id", "channel_id", "title", "format", "duration", "mode", "state", "revision", "updated", "parent_id")} for p in store.list_projects()]
        return {"channels": store.list_channels(), "projects": projects, "jobs": store.jobs(), "version": "0.1.0",
                "budget": 0, "worker": bool(worker.thread and worker.thread.is_alive())}

    @app.post("/api/channels")
    def create_channel(value: Channel):
        identifier = store.save_channel(value.model_dump())
        return store.channel(identifier)

    @app.put("/api/channels/{identifier}")
    def update_channel(identifier: str, value: Channel):
        store.channel(identifier)
        store.save_channel(value.model_dump(), identifier)
        return store.channel(identifier)

    @app.post("/api/projects")
    def create_project(value: ProjectInput):
        return store.create_project(value.model_dump())

    @app.post("/api/example")
    def example():
        channel = store.save_channel(Channel(name="Relatos de viaje", theme="Ficción y viajes",
                              style="Warm natural travel photography, peaceful coastline, golden sunlight").model_dump())
        script = "En aquella isla, el amanecer tenía un color distinto. Clara encontró un pequeño bote y decidió explorar la costa."
        project = store.create_project(ProjectInput(channel_id=channel, title="La isla al amanecer · prueba", format="pilot", duration=15,
                             script=script, audio_source="riva", image_source="sdxl", visual_bible="Peaceful tropical coastline, small wooden boat, turquoise sea, golden sunrise.").model_dump())
        scene = plan_basic(script, 15, "narration")[0]
        scene.update(text=script, start=0, end=15,
                     prompt="A peaceful tropical island coastline at sunrise, a small empty wooden boat on turquoise water, golden sunlight, lush hills in distance, cinematic natural travel photography, vertical composition, no text, no people.")
        store.change(project["id"], {"scenes": [scene]})
        store.enqueue(project["id"], "generate")
        return store.project(project["id"])

    @app.get("/api/projects/{identifier}")
    def get_project(identifier: str):
        project = store.project(identifier)
        return {**project, "assets": [public_asset(a) for a in store.assets(identifier)], "jobs": store.jobs(identifier),
                "publications": publications(store, identifier), "quality_now": quality(store, project)}

    @app.put("/api/projects/{identifier}")
    def update_project(identifier: str, payload: dict = Body(...)):
        idle(identifier)
        project = store.project(identifier)
        value = ProjectInput.model_validate({**project, **payload.get("project", {})}).model_dump()
        changes = value
        if value["script"] != project["script"]:
            changes.update(scenes=[], timing="estimated")
            if value["audio_source"] == "riva":
                changes["audio_asset"] = None
        return store.change(identifier, changes, expected=payload.get("revision"))

    @app.put("/api/projects/{identifier}/scenes")
    def update_scenes(identifier: str, payload: dict = Body(...)):
        idle(identifier)
        project = store.project(identifier)
        rows = payload.get("scenes", [])
        if not isinstance(rows, list) or len(rows) > 500:
            raise ValueError("Lista de escenas no válida.")
        scenes = [SceneInput.model_validate(r).model_dump() for r in rows]
        if len({s["id"] for s in scenes}) != len(scenes):
            raise ValueError("Los identificadores de escena no pueden repetirse.")
        for scene in scenes:
            for ref in scene["reference_ids"]:
                if store.asset(ref, identifier)["kind"] != "image":
                    raise ValueError("Las referencias deben ser imágenes.")
            if scene["visual_asset"]:
                store.asset(scene["visual_asset"], identifier)
            for effect in scene["effects"]:
                if effect.get("type") not in {"knock", "phone", "impact", "whoosh", "chime"}:
                    raise ValueError("Efecto de sonido no disponible.")
                if not (0 <= float(effect.get("offset", 0)) <= scene["end"]-scene["start"] and 0 <= float(effect.get("gain", .18)) <= .4):
                    raise ValueError("Tiempo o volumen del efecto no válido.")
        errors = validate_timeline({**project, "scenes": scenes})
        # During manual drafting permit a real audio duration outside chosen format;
        # rendering remains blocked. Gaps and overlaps are always rejected.
        if any("hueco" in error or "solapamiento" in error for error in errors):
            raise ValueError(" ".join(errors))
        text_changed = [s["text"] for s in scenes] != [s["text"] for s in project["scenes"]]
        changes = {"scenes": scenes, "script": "\n\n".join(s["text"] for s in scenes)}
        if text_changed and project["audio_source"] == "riva":
            changes.update(audio_asset=None, timing="estimated")
        return store.change(identifier, changes, expected=payload.get("revision"))

    @app.put("/api/projects/{identifier}/review")
    def review(identifier: str, payload: dict = Body(...)):
        idle(identifier)
        project = store.project(identifier)
        if payload.get("revision") != project["revision"]:
            raise ValueError("El proyecto cambió. Revisa la versión actual.")
        value = Review.model_validate(payload.get("review", {})).model_dump()
        if value["playback"] and not project.get("output_asset"):
            raise ValueError("Primero exporta y reproduce el video final.")
        return store.change(identifier, {"review": value}, expected=project["revision"], content=False)

    @app.post("/api/projects/{identifier}/jobs/{kind}")
    def enqueue(identifier: str, kind: str):
        if kind not in {"prepare", "generate", "align", "render", "produce"}:
            raise ValueError("Operación no disponible.")
        return store.enqueue(identifier, kind)

    @app.post("/api/jobs/{identifier}/cancel")
    def cancel(identifier: str):
        job = store.job(identifier)
        if job["status"] in {"queued", "waiting", "running"}:
            store.set_job(identifier, status="cancelled", message="Cancelado. Se conservan los recursos terminados.")
        return store.job(identifier)

    @app.get("/api/jobs/{identifier}/events")
    def events(identifier: str):
        store.job(identifier)
        return store.events(identifier)

    @app.post("/api/projects/{identifier}/assets")
    def upload(identifier: str, role: str = Query(...), scene_id: str | None = None,
               rights: str = "unknown", source: str = "Recurso importado", file: UploadFile = File(...)):
        idle(identifier)
        project = store.project(identifier)
        if role not in {"narration", "music", "scene", "reference"} or rights not in {"own", "licensed", "cc0", "unknown"}:
            raise ValueError("Tipo de recurso o derechos no válidos.")
        if scene_id and scene_id not in {s["id"] for s in project["scenes"]}:
            raise ValueError("Escena no encontrada.")
        maximum = 500*1024*1024 if role == "scene" else 150*1024*1024
        ext = Path(file.filename or "file").suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".webm"}:
            raise ValueError("Usa PNG/JPG/WebP, MP3/WAV/FLAC o MP4/MOV/WebM.")
        path = store.root/"assets"/(uid()+ext)
        size = 0
        asset = None
        try:
            with path.open("wb") as out:
                while block := file.file.read(1024*1024):
                    size += len(block)
                    if size > maximum:
                        raise ValueError("El archivo supera el límite de tamaño de esta importación.")
                    out.write(block)
            if ext in {".png", ".jpg", ".jpeg", ".webp"}:
                if role in {"narration", "music"}:
                    raise ValueError("Selecciona un archivo de audio.")
                with Image.open(path) as image:
                    if image.width*image.height > 30_000_000 or min(image.size) < 64:
                        raise ValueError("La imagen debe tener entre 64 píxeles y 30 megapíxeles.")
                    converted = path.with_suffix(".normalized.png")
                    ImageOps.exif_transpose(image).convert("RGB").save(converted)
                path.unlink()
                path = converted
                metadata = {"kind": "image"}
            else:
                info = probe(path)
                if role in {"narration", "music"} and not info["audio"]:
                    raise ValueError("El archivo no contiene una pista de audio.")
                if role == "reference":
                    raise ValueError("Usa una imagen como referencia del personaje o lugar.")
                if role == "scene" and not info["video"]:
                    raise ValueError("Usa una imagen o un clip de video para el plano.")
                metadata = {"kind": "video" if info["video"] else "audio", **info}
            asset = store.add_asset(identifier, path, {**metadata, "role": role, "rights": rights, "source": source[:1000],
                         "name": Path(file.filename or "Recurso").name[:150], "created_by_ai": False})
            changes = {}
            if role in {"narration", "music"}:
                changes["audio_asset" if role == "narration" else "music_asset"] = asset["id"]
                if role == "narration":
                    changes.update(audio_source="upload", timing="estimated")
                    if project["scenes"] and not any(s["locked"] for s in project["scenes"]):
                        changes["scenes"] = fit_timing(project["scenes"], metadata["duration"])
            elif scene_id:
                scenes = project["scenes"]
                for scene in scenes:
                    if scene["id"] == scene_id:
                        if role == "reference":
                            scene["reference_ids"] = list(dict.fromkeys(scene["reference_ids"]+[asset["id"]]))[:8]
                        else:
                            scene.update(visual_asset=asset["id"], source_offset=0, identity_reviewed=False, lipsync_reviewed=False)
                            if metadata["kind"] == "video" and scene["kind"] == "image":
                                scene["kind"] = "clip"
                            if metadata["kind"] == "image" and scene["kind"] != "image":
                                raise ValueError("Esta escena necesita un clip. Cambia su tipo si quieres usar una imagen.")
                changes["scenes"] = scenes
            store.change(identifier, changes)
            return public_asset(asset)
        except BaseException:
            path.unlink(missing_ok=True)
            if asset:
                with store.connect() as db:
                    db.execute("DELETE FROM assets WHERE id=?", (asset["id"],))
            raise
        finally:
            file.file.close()

    @app.get("/media/{identifier}")
    def media(identifier: str, download: bool = False):
        asset = store.asset(identifier)
        path = store.asset_path(identifier)
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                            filename=(asset.get("name") or path.name) if download else None)

    @app.get("/api/projects/{identifier}/package")
    def package(identifier: str):
        idle(identifier)
        path = Pipeline(store, vault).package(identifier)
        return FileResponse(path, filename="Materiales-"+identifier[:8]+".zip")

    @app.post("/api/projects/{identifier}/adapt")
    def adapt(identifier: str, payload: dict = Body(...)):
        idle(identifier)
        parent = store.project(identifier)
        start, end = float(payload.get("start", 0)), float(payload.get("end", 120))
        if not 90 <= end-start <= 150 or start < 0:
            raise ValueError("Selecciona un fragmento de entre 90 y 150 segundos.")
        if not parent.get("audio_asset") or end > probe(store.asset_path(parent["audio_asset"], identifier))["duration"]+.01:
            raise ValueError("El fragmento supera la narración del proyecto original.")
        selected = [s for s in parent["scenes"] if s["end"] > start and s["start"] < end]
        if not selected:
            raise ValueError("El fragmento no contiene escenas.")
        value = ProjectInput.model_validate({**parent, "title": parent["title"][:140]+" · reel", "format": "reel", "duration": round(end-start),
                   "aspect": "9:16", "parent_id": identifier, "script": "\n\n".join(s["text"] for s in selected)}).model_dump()
        child = store.create_project(value)
        folder = store.root/"work"/child["id"]
        folder.mkdir(exist_ok=True)
        audio = folder/"adapted.wav"
        run([ffmpeg(), "-y", "-v", "error", "-ss", str(start), "-i", str(store.asset_path(parent["audio_asset"], identifier)), "-t", str(end-start), str(audio)])
        audio_asset = store.add_asset(child["id"], audio, {"kind": "audio", "role": "narration", "source": "Adaptación de "+identifier, "rights": "project"})
        scenes, imported = [], {}
        def copy_asset(aid):
            if not aid:
                return None
            if aid not in imported:
                asset = store.asset(aid, identifier)
                imported[aid] = store.add_asset(child["id"], store.asset_path(aid, identifier), {k: v for k, v in asset.items() if k not in {"id", "project_id", "path"}})["id"]
            return imported[aid]
        for scene in selected:
            clipped = max(0, start-scene["start"])
            effects = [{**e, "offset": float(e.get("offset", 0))-clipped} for e in scene.get("effects", [])
                       if clipped <= float(e.get("offset", 0)) < min(end, scene["end"])-scene["start"]]
            scenes.append({**scene, "id": uid(), "start": max(0, scene["start"]-start), "end": min(end-start, scene["end"]-start),
                           "source_offset": scene.get("source_offset", 0)+clipped if scene["kind"] != "image" else 0, "effects": effects,
                           "visual_asset": copy_asset(scene["visual_asset"]), "reference_ids": [copy_asset(r) for r in scene["reference_ids"]],
                           "locked": True, "identity_reviewed": False, "lipsync_reviewed": False})
        store.change(child["id"], {"audio_asset": audio_asset["id"], "scenes": scenes, "timing": "estimated",
                                  "adaptation_note": "Fragmento reutilizado. Revisar inicio, contexto, cierre, textos parciales y reencuadre antes de exportar."})
        return store.project(child["id"])

    @app.get("/api/connections")
    def connections():
        names = ["openrouter", "groq", "omniroute", "bridge"]
        accounts = store.setting("accounts", [])
        names += [a["platform"]+"."+a["name"] for a in accounts]
        return {"backend": vault.backend, "keys": {n: bool(vault.get(n)) for n in names},
                "bridge": store.setting("bridge", {}), "omniroute": store.setting("omniroute", {}),
                "groq_free_confirmed": store.setting("groq_free_confirmed", False), "accounts": accounts}

    @app.post("/api/connections/key")
    def save_key(payload: dict = Body(...)):
        name = payload.get("name", "")
        allowed = {"openrouter", "groq", "omniroute", "bridge"}
        allowed.update(a["platform"]+"."+a["name"] for a in store.setting("accounts", []))
        if name not in allowed:
            raise ValueError("Conexión no disponible.")
        if payload.get("delete"):
            vault.delete(name)
        else:
            vault.set(name, payload.get("key", ""), bool(payload.get("remember")))
        return {"saved": bool(vault.get(name)), "backend": vault.backend}

    @app.put("/api/connections/bridge")
    def bridge(value: BridgeConfig):
        data = value.model_dump()
        if data["url"]:
            data["url"] = validate_endpoint(data["url"])
        store.save_setting("bridge", data)
        return {"saved": True}

    @app.put("/api/connections/omniroute")
    def gateway(value: GatewayConfig):
        data = value.model_dump()
        data["url"] = validate_endpoint(data["url"])
        store.save_setting("omniroute", data)
        return {"saved": True}

    @app.put("/api/connections/groq")
    def groq(value: dict = Body(...)):
        store.save_setting("groq_free_confirmed", value.get("free_plan") is True)
        return {"saved": True}

    @app.post("/api/ideas")
    def ideas(payload: dict = Body(...)):
        from .providers import Providers
        channel = store.channel(payload.get("channel_id", ""))
        history = [p["title"] for p in store.list_projects() if p["channel_id"] == channel["id"]][:100]
        return Providers(store, vault).text("Sugiere cinco temas originales para este canal, evitando repetir el historial. "
                    "Devuelve JSON {ideas:[{title,angle,content_type}]}. No afirmes tendencias ni datos recientes sin fuentes. "
                    "No inventes citas, cifras ni promesas de viralidad.", {"channel": channel, "history": history}, payload.get("route", "openrouter"))

    @app.put("/api/accounts")
    def account(payload: dict = Body(...)):
        import re
        platform, name = payload.get("platform"), payload.get("name", "default")
        if platform not in {"youtube", "facebook", "tiktok"} or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name):
            raise ValueError("Cuenta no válida.")
        config = {k: payload.get(k) for k in ("page_id", "api_version", "permissions_confirmed")}
        store.save_setting(platform+"."+name, config)
        accounts = [a for a in store.setting("accounts", []) if (a["platform"], a["name"]) != (platform, name)]
        accounts.append({"platform": platform, "name": name})
        store.save_setting("accounts", accounts)
        return {"saved": True}

    @app.post("/api/projects/{identifier}/publish")
    def publish(identifier: str, value: PublishInput):
        idle(identifier)
        return schedule(store, store.project(identifier), value.model_dump())

    @app.post("/api/publications/{identifier}/refresh")
    def publication_status(identifier: str):
        return refresh(store, vault, identifier)

    return app
