"""Official API publishers. No browser posting, no automatic retries after ambiguity.

Access tokens are supplied by the owner through the local UI and stored in Vault.
OAuth app registration/review remains a deployment prerequisite, not something
this module can bypass. Publishers require final review and per-item consent.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import httpx

from .db import dumps, uid
from .pipeline import quality
from .providers import Blocked


def publications(store, project_id):
    with store.connect() as db:
        rows = db.execute("SELECT * FROM publications WHERE project_id=?", (project_id,)).fetchall()
    return [{**dict(r), "data": json.loads(r["data"])} for r in rows]


def update_publication(store, identifier, status, data):
    with store.connect() as db:
        db.execute("UPDATE publications SET status=?,data=? WHERE id=?", (status, dumps(data), identifier))


def schedule(store, project, config):
    if not config["authorize"]:
        raise ValueError("Debes autorizar esta publicación y sus opciones de privacidad.")
    report = quality(store, project, publishing=True)
    if not report["ok"]:
        raise ValueError("No se puede publicar: "+" ".join(report["errors"][:5]))
    when = 0.
    if config.get("when"):
        stamp = datetime.fromisoformat(config["when"].replace("Z", "+00:00"))
        if not stamp.tzinfo:
            raise ValueError("La programación necesita zona horaria.")
        when = stamp.timestamp()
    identifier = uid()
    with store.connect() as db:
        try:
            db.execute("INSERT INTO publications VALUES (?,?,?,?,?,?,?)", (identifier, project["id"], project["revision"],
                      config["platform"], config["account"], "scheduled", dumps(config)))
        except __import__("sqlite3").IntegrityError:
            raise ValueError("Ya hay una publicación de esta revisión, cuenta y plataforma. Revisa su estado para evitar duplicados.") from None
        job_id, now = uid(), time.time()
        db.execute("INSERT INTO jobs(id,project_id,kind,status,next_run,created,updated,data) VALUES (?,?,'publish','queued',?,?,?,?)",
                   (job_id, project["id"], when, now, now, dumps({"publication_id": identifier})))
    return store.job(job_id)


def checked_json(response):
    if response.status_code >= 300:
        raise Blocked(f"La plataforma rechazó la solicitud (HTTP {response.status_code}). Revisa permisos, token y límites.")
    try:
        value = response.json()
    except ValueError:
        raise Blocked("La plataforma devolvió una respuesta no reconocida.") from None
    if value.get("error") and (not isinstance(value["error"], dict) or value["error"].get("code") not in {None, "ok"}):
        raise Blocked("La plataforma rechazó la operación. Revisa permisos, configuración y elegibilidad de la cuenta.")
    return value


def allowed_upload(url, platform):
    host = (urlsplit(url).hostname or "").lower()
    valid = {"youtube": host == "www.googleapis.com", "facebook": host == "rupload.facebook.com",
             "tiktok": host.endswith(".tiktokapis.com") or host == "tiktokapis.com"}[platform]
    if not valid or urlsplit(url).scheme != "https" or urlsplit(url).username:
        raise Blocked("La plataforma devolvió una dirección de subida inesperada.")
    return url


def file_chunks(path, cancelled, chunk_size=1024*1024):
    with Path(path).open("rb") as stream:
        while data := stream.read(chunk_size):
            if cancelled():
                from .media import Cancelled
                raise Cancelled()
            yield data


def publish(store, vault, job, cancelled, log, client=None):
    identifier = job["data"]["publication_id"]
    with store.connect() as db:
        row = db.execute("SELECT * FROM publications WHERE id=?", (identifier,)).fetchone()
    if not row or row["status"] != "scheduled":
        raise Blocked("Esta publicación ya se intentó. Comprueba su resultado antes de repetirla.")
    project = store.project(row["project_id"])
    data = json.loads(row["data"])
    if project["revision"] != row["revision"]:
        update_publication(store, identifier, "blocked", {**data, "reason": "El proyecto cambió después de programarse"})
        raise Blocked("El proyecto cambió después de programarse; autoriza la nueva revisión.")
    report = quality(store, project, publishing=True)
    if not report["ok"]:
        raise Blocked("La revisión final ya no está aprobada.")
    platform, account = row["platform"], row["account"]
    token = vault.get(platform+"."+account)
    if not token:
        raise Blocked("Conecta la cuenta de "+platform+" antes de publicar.")
    account_config = store.setting(platform+"."+account, {})
    if not account_config.get("permissions_confirmed"):
        raise Blocked("Confirma permisos y elegibilidad de esta aplicación y cuenta en Conexiones.")
    path = store.asset_path(project["output_asset"], project["id"])
    size = path.stat().st_size
    client_owned = client is None
    client = client or httpx.Client(timeout=300, follow_redirects=False, trust_env=True)
    headers = {"Authorization": "Bearer "+token}
    # Persist intent before the first network request; lost responses never cause
    # a second POST automatically. Session URLs are protected as credentials.
    update_publication(store, identifier, "uploading", data)
    try:
        log("Subiendo a "+platform+" mediante su API oficial…")
        if platform == "youtube":
            if data["privacy"] not in {"private", "unlisted", "public"}:
                raise Blocked("Privacidad de YouTube no válida.")
            metadata = {"snippet": {"title": data["title"], "description": data["description"], "categoryId": "22"},
                        "status": {"privacyStatus": data["privacy"], "selfDeclaredMadeForKids": data["made_for_kids"],
                                   "containsSyntheticMedia": data["ai_generated"]}}
            response = client.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status"}, json=metadata,
                      headers={**headers, "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
            if response.status_code >= 300:
                raise Blocked(f"YouTube rechazó el inicio de la subida (HTTP {response.status_code}).")
            url = allowed_upload(response.headers.get("location", ""), platform)
            vault.set("upload."+identifier, url, remember=vault.backend != "memory")
            response = client.put(url, content=file_chunks(path, cancelled), headers={**headers, "Content-Type": "video/mp4", "Content-Length": str(size)})
            result = checked_json(response)
            if not result.get("id"):
                raise Blocked("YouTube no confirmó un identificador de video.")
            data.update(remote_id=result["id"], url="https://www.youtube.com/watch?v="+result["id"])
            update_publication(store, identifier, "uploaded", data)
        elif platform == "facebook":
            page_id = account_config.get("page_id", "")
            version = account_config.get("api_version", "")
            if not re.fullmatch(r"\d+", page_id) or not re.fullmatch(r"v\d+\.\d+", version):
                raise Blocked("Configura el ID de página y la versión vigente de Graph API.")
            if data["privacy"] != "public":
                raise Blocked("Este conector publica en una página de Facebook; selecciona público de forma expresa.")
            if project["format"] == "long":
                # Single upload to official Page Videos edge; no retry on loss.
                with path.open("rb") as stream:
                    result = checked_json(client.post(f"https://graph-video.facebook.com/{version}/{page_id}/videos",
                        headers=headers, data={"title": data["title"], "description": data["description"], "published": "true"},
                        files={"source": ("video.mp4", stream, "video/mp4")}))
                remote_id = result.get("id")
            else:
                base = f"https://graph.facebook.com/{version}/{page_id}/video_reels"
                result = checked_json(client.post(base, headers=headers, data={"upload_phase": "start"}))
                remote_id = result.get("video_id")
                if not remote_id:
                    raise Blocked("Facebook no devolvió el identificador de subida.")
                data["remote_id"] = remote_id
                update_publication(store, identifier, "uploading", data)
                url = allowed_upload(result.get("upload_url", ""), platform)
                checked_json(client.post(url, headers={"Authorization": "OAuth "+token, "offset": "0", "file_size": str(size),
                             "Content-Length": str(size), "Content-Type": "application/octet-stream"}, content=file_chunks(path, cancelled)))
                checked_json(client.post(base, headers=headers, data={"upload_phase": "finish", "video_id": remote_id,
                             "video_state": "PUBLISHED", "title": data["title"], "description": data["description"]}))
            if not remote_id:
                raise Blocked("Facebook no confirmó el video.")
            data.update(remote_id=remote_id, url="https://www.facebook.com/"+str(remote_id))
            update_publication(store, identifier, "processing", data)
        else:
            result = checked_json(client.post("https://open.tiktokapis.com/v2/post/publish/creator_info/query/", headers=headers, json={}))
            creator = result.get("data", {})
            options = creator.get("privacy_level_options", [])
            if data["privacy"] not in options:
                raise Blocked("La privacidad seleccionada no está permitida para este creador o la aplicación no está auditada.")
            if project["scenes"][-1]["end"] > creator.get("max_video_post_duration_sec", 0):
                raise Blocked("Este video supera la duración permitida por la cuenta de TikTok.")
            chunk_size = min(size, 10*1024*1024)
            count = max(1, size//chunk_size)
            result = checked_json(client.post("https://open.tiktokapis.com/v2/post/publish/video/init/", headers=headers,
                json={"post_info": {"title": data["title"]+" "+data["description"][:2000], "privacy_level": data["privacy"],
                                    "disable_duet": True, "disable_stitch": True, "disable_comment": bool(creator.get("comment_disabled", True)),
                                    "is_aigc": data["ai_generated"]},
                      "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk_size, "total_chunk_count": count}}))
            remote = result.get("data", {})
            if not remote.get("publish_id"):
                raise Blocked("TikTok no devolvió el identificador de publicación.")
            data["remote_id"] = remote["publish_id"]
            update_publication(store, identifier, "uploading", data)
            url = allowed_upload(remote.get("upload_url", ""), platform)
            with path.open("rb") as stream:
                offset = 0
                for i in range(count):
                    if cancelled():
                        from .media import Cancelled
                        raise Cancelled()
                    block = stream.read(size-offset if i == count-1 else chunk_size)
                    response = client.put(url, content=block, headers={"Content-Type": "video/mp4", "Content-Length": str(len(block)),
                                          "Content-Range": f"bytes {offset}-{offset+len(block)-1}/{size}"})
                    if response.status_code not in {200, 201, 206}:
                        raise Blocked("TikTok no confirmó la transferencia del video.")
                    offset += len(block)
            update_publication(store, identifier, "processing", data)
        vault.delete("upload."+identifier)
        log("Transferencia confirmada. El procesamiento y la visibilidad dependen de la plataforma.")
    except BaseException:
        # Even a clear 4xx is left for manual review rather than silently retried.
        update_publication(store, identifier, "unknown", data)
        raise
    finally:
        if client_owned:
            client.close()


def refresh(store, vault, identifier, client=None):
    with store.connect() as db:
        row = db.execute("SELECT * FROM publications WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise ValueError("Publicación no encontrada.")
    data = json.loads(row["data"])
    remote_id = data.get("remote_id")
    if not remote_id:
        raise Blocked("No hay identificador confirmado. Revisa la cuenta en la plataforma antes de cualquier nueva subida.")
    token = vault.get(row["platform"]+"."+row["account"])
    if not token:
        raise Blocked("Falta el token de esta cuenta.")
    client_owned = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False, trust_env=True)
    headers = {"Authorization": "Bearer "+token}
    status = row["status"]
    try:
        if row["platform"] == "tiktok":
            result = checked_json(client.post("https://open.tiktokapis.com/v2/post/publish/status/fetch/", headers=headers, json={"publish_id": remote_id}))
            external = result.get("data", {}).get("status")
            status = {"PUBLISH_COMPLETE": "published", "FAILED": "failed"}.get(external, "processing")
        elif row["platform"] == "youtube":
            result = checked_json(client.get("https://www.googleapis.com/youtube/v3/videos", headers=headers,
                                            params={"id": remote_id, "part": "status,processingDetails"}))
            items = result.get("items", [])
            if not items:
                raise Blocked("La plataforma todavía no confirmó este video.")
            item = items[0]
            external = item.get("processingDetails", {}).get("processingStatus")
            privacy = item.get("status", {}).get("privacyStatus")
            status = "published" if external == "succeeded" and privacy == "public" else "uploaded"
            if external in {"failed", "terminated"}:
                status = "failed"
        else:
            config = store.setting("facebook."+row["account"], {})
            version = config.get("api_version", "")
            if not re.fullmatch(r"v\d+\.\d+", version):
                raise Blocked("Versión de Graph API no válida.")
            result = checked_json(client.get(f"https://graph.facebook.com/{version}/{remote_id}", headers=headers, params={"fields": "status"}))
            external = result.get("status", {}).get("video_status")
            # Ready does not by itself prove public visibility.
            status = "uploaded" if external == "ready" else "failed" if external == "error" else "processing"
        data["last_checked"] = time.time()
        update_publication(store, identifier, status, data)
        return {"status": status, "data": data}
    finally:
        if client_owned:
            client.close()
