from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import unicodedata
import zipfile

from .db import dumps
from .media import Cancelled, clean_script, ffmpeg, fit_timing, make_cover, plan_basic, probe, render, run, write_srt
from .models import SceneInput
from .providers import Blocked, Providers, Quota, fingerprint
from .security import redact


def normalized(text):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn").split())


def validate_timeline(project):
    scenes = project.get("scenes", [])
    if not scenes:
        return ["No hay escenas."]
    errors, previous = [], 0.
    for i, value in enumerate(scenes, 1):
        try:
            scene = SceneInput.model_validate(value).model_dump()
        except Exception:
            errors.append(f"Escena {i}: datos no válidos.")
            continue
        if abs(scene["start"]-previous) > .06:
            errors.append(f"Escena {i}: hay un hueco o solapamiento en los tiempos.")
        previous = scene["end"]
    if project["format"] == "reel" and not 90 <= previous <= 150:
        errors.append("El audio final debe durar entre 90 y 150 segundos para este reel.")
    if project["format"] == "long" and not 300 <= previous <= 900:
        errors.append("El audio final de un largo debe durar entre 5 y 15 minutos.")
    if project["format"] == "pilot" and not 1 <= previous <= 30:
        errors.append("La prueba corta no puede superar los 30 segundos.")
    return errors


def quality(store, project, publishing=False):
    errors = validate_timeline(project)
    warnings = []
    review = project.get("review", {})
    if not project.get("audio_asset"):
        errors.append("Falta la narración definitiva.")
    else:
        try:
            audio = probe(store.asset_path(project["audio_asset"], project["id"]))
            if not audio["audio"]:
                errors.append("El recurso de narración no contiene audio.")
            if project["scenes"] and abs(audio["duration"]-project["scenes"][-1]["end"]) > .35:
                errors.append("Los tiempos no cubren exactamente la narración definitiva.")
        except ValueError as exc:
            errors.append(str(exc))
    for i, scene in enumerate(project.get("scenes", []), 1):
        if not scene.get("visual_asset"):
            errors.append(f"Falta el recurso visual de la escena {i}.")
            continue
        try:
            asset = store.asset(scene["visual_asset"], project["id"])
            path = store.asset_path(asset["id"], project["id"])
            if scene["kind"] in {"clip", "character"}:
                info = probe(path)
                if not info["video"] or info["duration"]+.08 < scene["end"]-scene["start"]+scene.get("source_offset", 0):
                    errors.append(f"El clip de la escena {i} no cubre su duración.")
            elif asset["kind"] != "image":
                errors.append(f"La escena {i} necesita una imagen.")
            if asset.get("rights") == "unknown":
                errors.append(f"Falta aclarar los derechos del recurso de la escena {i}.")
        except ValueError as exc:
            errors.append(f"Escena {i}: {exc}")
        if scene["kind"] == "character":
            if not scene.get("identity_reviewed"):
                errors.append(f"Revisa la identidad del personaje en la escena {i}.")
            if scene.get("text", "").strip() and not scene.get("lipsync_reviewed"):
                errors.append(f"Revisa la sincronización labial de la escena {i}.")
    if project["content_type"] == "factual":
        valid_sources = [s for s in project.get("sources", []) if s.get("url", "").startswith("https://") and s.get("title")]
        if not valid_sources or not review.get("factual"):
            errors.append("El contenido factual requiere fuentes y revisión de sus afirmaciones.")
    for check, label in {"editorial": "guion", "rights": "derechos", "timing": "tiempos y pronunciación", "continuity": "continuidad visual"}.items():
        if not review.get(check):
            errors.append("Pendiente de revisión: "+label+".")
    if project.get("timing") == "estimated":
        warnings.append("Los tiempos y subtítulos fueron estimados. Ajusta o sincroniza con el audio y revisa su precisión.")
    elif project.get("timing") != "transcribed":
        warnings.append("La duración de cada fragmento de voz está medida; la posición de cada palabra del subtítulo sigue siendo estimada.")
    if publishing:
        if not project.get("output_asset") or not project.get("technical_report", {}).get("decoded"):
            errors.append("Falta un video exportado y verificado para esta revisión.")
        if not review.get("playback"):
            errors.append("Reproduce y aprueba el video final antes de publicar.")
    return {"ok": not errors, "errors": list(dict.fromkeys(errors)), "warnings": warnings,
            "revision": project["revision"], "human_review_required": True}


class Pipeline:
    def __init__(self, store, vault, provider_factory=Providers):
        self.store, self.vault = store, vault
        self.provider_factory = provider_factory

    def prepare(self, project_id, provider, cancelled, log):
        project = self.store.project(project_id)
        channel = self.store.channel(project["channel_id"])
        if not project["script"].strip():
            if project["planner"] == "manual":
                raise Blocked("Pega el guion o selecciona IA para desarrollarlo desde el tema.")
            if project["content_type"] == "factual" and not project["sources"]:
                raise Blocked("Añade fuentes verificables para desarrollar este tema factual.")
            result = provider.text("Eres guionista de videos en español. Devuelve JSON con script, title, description. "
                                   "Respeta el perfil y duración; aproximadamente 130 palabras por minuto, sin prometer duración exacta. "
                                   "No inventes fuentes ni citas. Distingue ficción, opinión y hechos. No incluyas instrucciones técnicas en el texto hablado.",
                                   {"topic": project["topic"], "duration": project["duration"], "type": project["content_type"],
                                    "channel": channel, "sources": project["sources"]}, project["planner"])
            script = result.get("script", "")
            if not isinstance(script, str) or not 20 <= len(script) <= 40000:
                raise Blocked("El guion generado no es válido.")
            project = self.store.change(project_id, {"script": script,
                      "description": str(result.get("description", ""))[:5000]})
        if not project["scenes"]:
            scenes = plan_basic(project["script"], project["duration"], project["mode"])
            if project["planner"] != "manual":
                bible = project["visual_bible"]
                for start in range(0, len(scenes), 8):
                    batch = scenes[start:start+8]
                    result = provider.text(
                        "Act as a cinematic storyboard director. Return JSON only: {visual_bible:string, scenes:[{id,prompt,kind,speaker,effects:[]}]}. "
                        "Plan exactly the supplied IDs in order. Do not return timings or rewrite narration. "
                        "Prompt: one shot, no collage, English, physically clear, 40-90 words. Never depict a revelation before its narration. "
                        "Keep exact repeated character descriptions, wardrobe and location architecture. visual_bible contains stable identities and locations, not plot. "
                        "If a previous bible exists copy it exactly. Respect selected mode: narration uses image/clip (prefer image); characters uses character; mixed chooses per shot. "
                        "speaker must identify a single speaker or narrator. Sound effects optional (knock, phone, impact, whoosh, chime), offset in seconds, gain <=0.3. "
                        "Apply channel style and rules, not a fixed genre. Do not invent sources or URLs.",
                        {"channel": channel, "mode": project["mode"], "previous_bible": bible, "script": project["script"],
                         "scenes": [{"id": s["id"], "narration": s["text"], "duration": s["end"]-s["start"]} for s in batch]}, project["planner"])
                    rows = result.get("scenes", [])
                    if not isinstance(rows, list) or [r.get("id") for r in rows] != [s["id"] for s in batch]:
                        raise Blocked("El plan de IA omitió o cambió escenas.")
                    new_bible = result.get("visual_bible", "")
                    if not isinstance(new_bible, str) or not new_bible.strip() or len(new_bible) > 10000:
                        raise Blocked("La IA no devolvió referencias de continuidad válidas.")
                    if bible and new_bible != bible:
                        raise Blocked("El planificador cambió las referencias entre bloques. Revisa el plan.")
                    bible = bible or new_bible
                    for scene, row in zip(batch, rows):
                        kind = row.get("kind", "image")
                        if kind not in {"image", "clip", "character"}:
                            raise Blocked("Tipo de escena no válido en el plan de IA.")
                        if project["mode"] == "characters" and kind != "character":
                            raise Blocked("El plan no respetó el modo de personajes.")
                        if project["mode"] == "narration" and kind == "character":
                            raise Blocked("El plan no respetó el modo de narración.")
                        scene.update(prompt=str(row.get("prompt", ""))[:5000], kind=kind,
                                     speaker=str(row.get("speaker", "narrator"))[:100], effects=row.get("effects", [])[:15])
                        SceneInput.model_validate(scene)
                    log(f"Planificadas escenas {start+1}–{start+len(batch)}.")
                project = self.store.change(project_id, {"scenes": scenes, "visual_bible": bible})
            else:
                project = self.store.change(project_id, {"scenes": scenes})
        if not project.get("audio_asset"):
            if project["audio_source"] == "upload":
                raise Blocked("El plan está guardado. Ahora carga tu narración para medir los tiempos reales.")
            folder = self.store.root/"work"/project_id/"voice"
            folder.mkdir(parents=True, exist_ok=True)
            pieces, measured = [], []
            for i, scene in enumerate(project["scenes"]):
                voice = channel["voice"]
                if scene["speaker"] != "narrator":
                    voice = channel.get("character_voices", {}).get(scene["speaker"], "")
                    if not voice:
                        raise Blocked(f"Asigna una voz estable a {scene['speaker']} en el perfil del canal.")
                signature = fingerprint({"text": scene["text"], "voice": voice})
                target = folder/(signature+".wav")
                if not target.exists():
                    provider.tts_scene(scene["text"], voice, target.with_suffix(".part.wav"))
                    target.with_suffix(".part.wav").replace(target)
                length = probe(target)["duration"]
                measured.append(length)
                pieces.append(target)
                log(f"Narración lista: escena {i+1}/{len(project['scenes'])}.")
            manifest = folder/"voices.txt"
            manifest.write_text("\n".join("file '"+p.name+"'" for p in pieces), "utf-8")
            joined = folder/"narration.wav"
            run([ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "1", "-i", str(manifest), "-ac", "1", "-ar", "24000", str(joined)], cancelled)
            asset = self.store.add_asset(project_id, joined, {"kind": "audio", "role": "narration", "source": "Riva OVHcloud", "rights": "generated", "duration": sum(measured)})
            scenes, at = [], 0.
            for scene, length in zip(project["scenes"], measured):
                scenes.append({**scene, "start": round(at, 3), "end": round(at+length, 3)})
                at += length
            project = self.store.change(project_id, {"audio_asset": asset["id"], "scenes": scenes, "timing": "tts_segments"})
        else:
            duration = probe(self.store.asset_path(project["audio_asset"], project_id))["duration"]
            if project["scenes"] and abs(project["scenes"][-1]["end"]-duration) > .1:
                if any(s.get("locked") for s in project["scenes"]):
                    raise Blocked("El audio no coincide con los tiempos editados. Ajusta o sincroniza las escenas.")
                project = self.store.change(project_id, {"scenes": fit_timing(project["scenes"], duration), "timing": "estimated"})
        self.store.change(project_id, {"state": "planned"}, content=False)

    def generate(self, project_id, provider, cancelled, log):
        project = self.store.project(project_id)
        if not project["scenes"] or not project.get("audio_asset"):
            self.prepare(project_id, provider, cancelled, log)
            project = self.store.project(project_id)
        for i in range(len(project["scenes"])):
            if cancelled():
                raise Cancelled()
            # Reload after each completed resource; a crash cannot erase prior scenes.
            project = self.store.project(project_id)
            scene = project["scenes"][i]
            if scene.get("visual_asset"):
                self.store.asset_path(scene["visual_asset"], project_id)
                continue
            if not scene["prompt"].strip():
                raise Blocked(f"Añade un prompt al plano {i+1} o usa planificación por IA.")
            refs = [self.store.asset_path(r, project_id) for r in scene["reference_ids"]]
            if scene["kind"] == "clip":
                raise Blocked(f"Importa el clip del plano {i+1}. No se sustituirá por una imagen.")
            if scene["kind"] == "character" or project["image_source"] == "bridge":
                folder = self.store.root/"work"/project_id
                folder.mkdir(parents=True, exist_ok=True)
                audio = folder/(scene["id"]+".wav")
                run([ffmpeg(), "-y", "-v", "error", "-ss", str(scene["start"]), "-i", str(self.store.asset_path(project["audio_asset"], project_id)),
                     "-t", str(scene["end"]-scene["start"]), "-ac", "1", "-ar", "24000", str(audio)], cancelled)
                path = provider.bridge(scene, project, audio, refs)
                source, rights = "Conector de medios configurado", "generated"
            elif project["image_source"] == "sdxl":
                if refs:
                    raise Blocked("SDXL de texto no acepta estas imágenes de referencia. Usa un conector con referencias o importa el recurso.")
                path = provider.image(project["visual_bible"]+"\n"+scene["prompt"])
                source, rights = "SDXL · OVHcloud · CreativeML Open RAIL++-M", "generated"
            else:
                raise Blocked(f"Carga la imagen del plano {i+1} o selecciona generación por API.")
            asset = self.store.add_asset(project_id, path, {"kind": "video" if scene["kind"] == "character" else "image",
                      "role": "scene", "source": source, "rights": rights, "prompt": scene["prompt"],
                      "reference_ids": scene["reference_ids"], "created_by_ai": True})
            scenes = project["scenes"]
            scenes[i] = {**scene, "visual_asset": asset["id"], "identity_reviewed": False, "lipsync_reviewed": False}
            self.store.change(project_id, {"scenes": scenes})
            log(f"Recurso guardado: plano {i+1}/{len(scenes)}.")
        self.store.change(project_id, {"state": "review"}, content=False)

    def align(self, project_id, provider, cancelled, log):
        project = self.store.project(project_id)
        if not project.get("audio_asset") or not project["scenes"]:
            raise Blocked("Primero prepara las escenas e importa o genera la narración.")
        audio = self.store.asset_path(project["audio_asset"], project_id)
        folder = self.store.root/"work"/project_id
        folder.mkdir(exist_ok=True)
        words = provider.align(audio, probe(audio)["duration"], folder)
        # Match complete transcript against script before assigning semantic boundaries.
        script_tokens = normalized(clean_script(" ".join(s["text"] for s in project["scenes"]))).split()
        word_tokens = normalized(" ".join(w["word"] for w in words)).split()
        import difflib
        matcher = difflib.SequenceMatcher(None, script_tokens, word_tokens, autojunk=False)
        if matcher.ratio() < .8 or len(word_tokens) != len(words):
            raise Blocked("La transcripción no coincide suficientemente con el guion. Revisa el audio y los textos antes de asignar tiempos.")
        positions = {}
        for block in matcher.get_matching_blocks():
            for n in range(block.size):
                positions[block.a+n] = block.b+n
        scenes, token_at, previous = [], 0, 0.
        for i, scene in enumerate(project["scenes"]):
            token_at += len(normalized(clean_script(scene["text"])).split())
            if i == len(project["scenes"])-1:
                end = probe(audio)["duration"]
            else:
                if token_at not in positions:
                    raise Blocked("Una separación de escenas no coincide con la transcripción. Ajusta ese tiempo manualmente.")
                end = words[positions[token_at]]["start"]
            if end <= previous:
                raise Blocked("La sincronización produciría una escena sin duración.")
            scenes.append({**scene, "start": round(previous, 3), "end": round(end, 3)})
            previous = end
        self.store.change(project_id, {"scenes": scenes, "timing": "transcribed", "words": words})

    def render(self, project_id, cancelled, log):
        project = self.store.project(project_id)
        report = quality(self.store, project)
        if not report["ok"]:
            self.store.change(project_id, {"state": "review", "quality": report}, content=False)
            raise Blocked("Antes de exportar: "+" ".join(report["errors"][:4]))
        work = self.store.root/"work"/project_id/"render"
        self.store.change(project_id, {"state": "rendering"}, content=False)
        path, srt, info = render(self.store, project, work, cancelled, log)
        asset = self.store.add_asset(project_id, path, {"kind": "video", "role": "output", "rights": "project", **info})
        cover_path = self.store.root/"exports"/f"{project_id}-r{project['revision']}-cover.jpg"
        make_cover(path, cover_path, project["title"], info["duration"], cancelled)
        cover = self.store.add_asset(project_id, cover_path, {"kind": "image", "role": "cover", "rights": "project", "source": "Fotograma del video y título del proyecto"})
        self.store.change(project_id, {"output_asset": asset["id"], "cover_asset": cover["id"], "state": "ready",
            "technical_report": {"decoded": True, "duration": info["duration"], "width": info["width"], "height": info["height"],
                                 "revision": project["revision"], "audio_normalization_target": "-16 LUFS / -1.5 dBTP (one-pass)",
                                 "measured_loudness": False}, "quality": report}, content=False)
        self.package(project_id)

    def package(self, project_id):
        project = self.store.project(project_id)
        target = self.store.root/"exports"/f"{project_id}-r{project['revision']}-materials.zip"
        temp = target.with_suffix(".part.zip")
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as output:
            safe_project = {k: v for k, v in project.items() if k not in {"words"}}
            output.writestr("project.json", dumps(safe_project))
            output.writestr("script.txt", project["script"])
            output.writestr("sources.json", dumps(project.get("sources", [])))
            output.writestr("quality.json", dumps(quality(self.store, project, publishing=True)))
            output.writestr("README.txt", "Materiales de Estudio Multicanal. No es un proyecto nativo de CapCut.\nImporta MP4, SRT y recursos en tu editor.\nLos tiempos estimados requieren revisión.\n")
            output.writestr("timeline.csv", "scene,start,end,kind,asset\n"+"\n".join(f"{i+1},{s['start']},{s['end']},{s['kind']},{s.get('visual_asset','')}" for i, s in enumerate(project["scenes"])))
            subtitle_path = self.store.root/"work"/project_id/"package.srt"
            subtitle_path.parent.mkdir(exist_ok=True)
            write_srt(project["scenes"], subtitle_path, project.get("words") if project.get("timing") == "transcribed" else None)
            output.write(subtitle_path, "subtitles.srt")
            used = {s["visual_asset"] for s in project["scenes"] if s.get("visual_asset")}
            used.update(r for s in project["scenes"] for r in s["reference_ids"])
            used.update(a for a in [project.get("audio_asset"), project.get("music_asset"), project.get("cover_asset")] if a)
            provenance = []
            for identifier in sorted(used):
                asset = self.store.asset(identifier, project_id)
                path = self.store.asset_path(identifier, project_id)
                output.write(path, "assets/"+identifier+path.suffix)
                provenance.append({k: v for k, v in asset.items() if k != "path"})
            output.writestr("provenance.json", dumps(provenance))
        temp.replace(target)
        return target


class Worker:
    def __init__(self, store, vault, pipeline=None):
        self.store, self.vault = store, vault
        self.pipeline = pipeline or Pipeline(store, vault)
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        self.store.recover()
        self.thread = threading.Thread(target=self.loop, name="studio-worker", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=125)

    def loop(self):
        while not self.stop.is_set():
            job = self.store.claim()
            if job:
                self.execute(job)
            else:
                self.stop.wait(.5)

    def execute(self, job):
        identifier, pid = job["id"], job["project_id"]
        cancelled = lambda: self.stop.is_set() or self.store.job(identifier)["status"] == "cancelled"
        log = lambda msg: self.store.log(identifier, redact(msg, self.vault.secrets()))
        provider = self.pipeline.provider_factory(self.store, self.vault, cancelled, log)
        try:
            log("Iniciando "+job["kind"]+"…")
            if job["kind"] in {"prepare", "generate", "produce"}:
                self.pipeline.prepare(pid, provider, cancelled, log)
            if job["kind"] in {"generate", "produce"}:
                self.pipeline.generate(pid, provider, cancelled, log)
            if job["kind"] == "align":
                self.pipeline.align(pid, provider, cancelled, log)
            if job["kind"] in {"render", "produce"}:
                self.pipeline.render(pid, cancelled, log)
            if job["kind"] == "publish":
                from .publishing import publish
                publish(self.store, self.vault, job, cancelled, log)
            if cancelled():
                raise Cancelled()
            self.store.set_job(identifier, status="done", progress=1, message="Completado")
        except Quota as exc:
            if not cancelled():
                self.store.set_job(identifier, status="waiting", next_run=exc.until, message=str(exc))
        except Cancelled:
            # On shutdown requeue local work; publication is reconciled on startup.
            if self.store.job(identifier)["status"] != "cancelled":
                self.store.set_job(identifier, status="queued", message="Pausado al cerrar; continuará al abrir")
        except Exception as exc:
            message = redact(str(exc), self.vault.secrets())[:1500]
            log(message)
            self.store.set_job(identifier, status="review" if isinstance(exc, (Blocked, ValueError)) else "error", message=message)
            if job["kind"] != "publish":
                self.store.change(pid, {"state": "review"}, content=False)
