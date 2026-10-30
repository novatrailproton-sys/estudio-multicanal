from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
import wave

import httpx
from PIL import Image

from .db import dumps
from .media import Cancelled, clean_script, run, ffmpeg, split_text

SDXL = "https://stable-diffusion-xl.endpoints.kepler.ai.cloud.ovh.net/api/text2image"
RIVA = "https://nvr-tts-es-es.endpoints.kepler.ai.cloud.ovh.net/api/v1/tts/text_to_audio"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
GROQ = "https://api.groq.com/openai/v1/audio/transcriptions"


class Blocked(ValueError):
    pass


class Quota(Exception):
    def __init__(self, message, until):
        super().__init__(message)
        self.until = until


def fingerprint(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def validate_endpoint(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise Blocked("La dirección del conector no es válida.")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise Blocked("Usa HTTPS, o HTTP solo para un conector local.")
    return url.rstrip("/")


def require_free(config, pricing=False):
    if not config or not config.get("zero_cost_confirmed") or not config.get("evidence_url"):
        raise Blocked("Falta verificar el acceso gratuito de este conector. No se hará una llamada de precio desconocido.")
    try:
        expiry = datetime.fromisoformat(config["valid_until"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry.timestamp() <= time.time():
            raise ValueError()
    except (KeyError, ValueError):
        raise Blocked("La verificación de gratuidad ha vencido o no tiene fecha válida.") from None
    if pricing and (config.get("price_per_input_token") != 0 or config.get("price_per_output_token") != 0):
        raise Blocked("La ruta no tiene precio cero confirmado para entrada y salida.")


class Providers:
    def __init__(self, store, vault, cancelled=lambda: False, log=lambda _: None, transport=None):
        self.store, self.vault, self.cancelled, self.log = store, vault, cancelled, log
        self.transport = transport

    def request(self, provider, url, payload=None, *, key="", content=None, headers=None, interval=0, maximum=35_000_000):
        if self.cancelled():
            raise Cancelled()
        now = time.time()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT next_allowed FROM quotas WHERE provider=?", (provider,)).fetchone()
            if row and row[0] > now:
                raise Quota(f"Esperando la cuota de {provider}; el trabajo se conservará.", row[0])
            if interval:
                db.execute("INSERT OR REPLACE INTO quotas VALUES (?,?)", (provider, now+interval))
        hdr = {"User-Agent": "EstudioMulticanal/0.1", **(headers or {})}
        if key:
            hdr["Authorization"] = "Bearer "+key
        # No redirects: don't forward keys or accept provider-generated endpoints.
        try:
            with httpx.Client(timeout=httpx.Timeout(120, connect=20), follow_redirects=False, trust_env=True, transport=self.transport) as client:
                with client.stream("POST" if payload is not None or content is not None else "GET", url,
                                   json=payload, content=content, headers=hdr) as response:
                    if response.status_code == 429 or response.status_code in {502, 503, 504}:
                        retry = response.headers.get("retry-after", "60")
                        try:
                            seconds = float(retry)
                        except ValueError:
                            try:
                                seconds = parsedate_to_datetime(retry).timestamp()-now
                            except Exception:
                                seconds = 60
                        until = now+max(31, min(seconds, 7*86400))
                        with self.store.connect() as db:
                            db.execute("INSERT OR REPLACE INTO quotas VALUES (?,?)", (provider, until))
                        raise Quota(f"{provider}: cuota agotada o servicio ocupado. Esperando sin usar alternativas de pago.", until)
                    if response.status_code >= 300:
                        hints = {401: "Revisa tu clave.", 402: "El proveedor solicita pago; la ruta está bloqueada.",
                                 403: "Acceso no autorizado o plan no elegible.", 404: "El modelo o endpoint no está disponible."}
                        raise Blocked(f"{provider}: HTTP {response.status_code}. "+hints.get(response.status_code, "El proveedor rechazó la petición."))
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        if self.cancelled():
                            raise Cancelled()
                        data.extend(chunk)
                        if len(data) > maximum:
                            raise Blocked("El proveedor devolvió más datos de los permitidos.")
                    return bytes(data)
        except (httpx.TimeoutException, httpx.NetworkError):
            raise Quota(f"No se pudo contactar con {provider}. Se volverá a intentar.", time.time()+60) from None

    def text(self, system, user, route="openrouter"):
        if route == "openrouter":
            key = self.vault.get("openrouter")
            if not key:
                raise Blocked("Añade tu clave de OpenRouter en Conexiones o usa guion y escenas manuales.")
            url, model = OPENROUTER, "openrouter/free"
        elif route == "omniroute":
            config = self.store.setting("omniroute", {})
            require_free(config, pricing=True)
            base = validate_endpoint(config.get("url", ""))
            model = config.get("model", "")
            if not model or model in {"auto", "omniroute/auto", "free"}:
                raise Blocked("Selecciona una ruta concreta y gratuita en OmniRoute; se bloquea la selección general automática.")
            url, key = base+"/chat/completions", self.vault.get("omniroute")
        else:
            raise Blocked("Planificador no disponible.")
        payload = {"model": model, "messages": [{"role": "system", "content": system},
                    {"role": "user", "content": dumps(user)}], "temperature": .45, "max_tokens": 9000}
        cache = self.store.root/"cache"/(fingerprint({"route": route, "url": url, "payload": payload})+".json")
        if cache.exists():
            return json.loads(cache.read_text("utf-8"))
        raw = json.loads(self.request(route, url, payload, key=key, maximum=3_000_000))
        try:
            text = raw["choices"][0]["message"]["content"]
            text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError()
        except (KeyError, TypeError, IndexError, ValueError):
            raise Blocked("La IA devolvió un formato incompleto. Se conserva el proyecto para revisar o reintentar.") from None
        temp = cache.with_suffix(".tmp")
        temp.write_text(dumps(value), "utf-8")
        temp.replace(cache)
        return value

    def image(self, prompt):
        cache = self.store.root/"cache"/(fingerprint({"v": 1, "provider": "sdxl", "prompt": prompt})+".png")
        if cache.exists():
            return cache
        self.log("Generando imagen con SDXL…")
        data = self.request("sdxl", SDXL, {"prompt": prompt, "negative_prompt": "watermark, logo, text, distorted hands, extra limbs, blurry"}, interval=31)
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.width < 256 or image.height < 256:
                    raise ValueError()
                image.convert("RGB").save(cache.with_suffix(".tmp"), format="PNG")
        except Exception:
            raise Blocked("SDXL no devolvió una imagen válida.") from None
        cache.with_suffix(".tmp").replace(cache)
        return cache

    def tts_chunk(self, text, voice):
        if voice not in {"Spanish-ES-Male-1", "Spanish-ES-Female-1"}:
            raise Blocked("Voz Riva no compatible. Usa una de las voces disponibles o importa el audio.")
        text = clean_script(text)
        cache = self.store.root/"cache"/(fingerprint({"voice": voice, "text": text})+".wav")
        if cache.exists():
            return cache
        data = self.request("riva", RIVA, {"encoding": 1, "language_code": "es-ES", "sample_rate_hz": 16000,
                                           "text": text, "voice_name": voice}, interval=31)
        try:
            with wave.open(io.BytesIO(data)) as wav:
                if wav.getnframes() < 10 or wav.getsampwidth() != 2:
                    raise ValueError()
        except Exception:
            raise Blocked("La API de voz no devolvió un WAV válido.") from None
        cache.with_suffix(".tmp").write_bytes(data)
        cache.with_suffix(".tmp").replace(cache)
        return cache

    def tts_scene(self, text, voice, target):
        parts = [self.tts_chunk(t, voice) for t in split_text(text)]
        if not parts:
            raise Blocked("La escena no tiene texto para narrar.")
        with wave.open(str(target), "wb") as out:
            params = None
            for part in parts:
                with wave.open(str(part), "rb") as source:
                    current = (source.getnchannels(), source.getsampwidth(), source.getframerate())
                    if params is None:
                        params = current
                        out.setparams((*params, 0, "NONE", "not compressed"))
                    if current != params:
                        raise Blocked("El proveedor cambió el formato entre fragmentos de voz.")
                    out.writeframes(source.readframes(source.getnframes()))
        return target

    def bridge(self, scene, project, audio, references):
        config = self.store.setting("bridge", {})
        require_free(config)
        base = validate_endpoint(config.get("url", ""))
        required = {"video", "reference", "lipsync"} if scene["kind"] == "character" else {"image"}
        if not required <= set(config.get("capabilities", [])):
            raise Blocked("El conector no declara las capacidades necesarias para esta escena.")
        if scene["kind"] == "character" and not references:
            raise Blocked("Añade al menos una referencia del personaje a esta escena.")
        refdata = [{"mime": "image/png", "b64_json": base64.b64encode(p.read_bytes()).decode()} for p in references]
        payload = {"version": 1, "model": config.get("model"), "task": "character" if scene["kind"] == "character" else "image",
                   "prompt": scene["prompt"], "visual_bible": project["visual_bible"], "speaker": scene["speaker"],
                   "duration": scene["end"]-scene["start"], "aspect": project["aspect"], "references": refdata,
                   "audio_b64": base64.b64encode(Path(audio).read_bytes()).decode() if audio else None,
                   "budget": {"maximum_cost": 0, "paid_fallback": False}}
        digest = fingerprint({"base": base, "payload": payload})
        ext = ".mp4" if scene["kind"] == "character" else ".png"
        cache = self.store.root/"cache"/(digest+ext)
        if cache.exists():
            return cache
        response = json.loads(self.request("bridge", base+"/generate", payload, key=self.vault.get("bridge"), maximum=180_000_000))
        if response.get("cost") != 0 or response.get("kind") != ("video" if ext == ".mp4" else "image"):
            raise Blocked("El conector no confirmó coste cero o devolvió un tipo de recurso incorrecto.")
        try:
            content = base64.b64decode(response["b64_json"], validate=True)
            if not content:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise Blocked("El conector de medios no devolvió un archivo válido.") from None
        temp = cache.with_suffix(".tmp"+ext)
        temp.write_bytes(content)
        if ext == ".mp4":
            from .media import probe
            info = probe(temp)
            if not info["video"] or info["duration"]+.08 < scene["end"]-scene["start"]:
                temp.unlink(missing_ok=True)
                raise Blocked("El clip de personajes no cubre la escena completa.")
        else:
            with Image.open(temp) as image:
                image.verify()
        temp.replace(cache)
        return cache

    def align(self, audio, duration, work):
        key = self.vault.get("groq")
        if not key or not self.store.setting("groq_free_confirmed", False):
            raise Blocked("Conecta Groq y confirma que la cuenta usa su plan gratuito para sincronizar.")
        path = Path(work)/"alignment.flac"
        run([ffmpeg(), "-y", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", str(path)], self.cancelled)
        if path.stat().st_size > 24_000_000:
            raise Blocked("El audio comprimido supera el límite configurado para Groq gratuito.")
        cache = self.store.root/"cache"/(hashlib.sha256(path.read_bytes()).hexdigest()+"-words.json")
        if cache.exists():
            data = json.loads(cache.read_text("utf-8"))
        else:
            boundary = "Estudio"+__import__("uuid").uuid4().hex
            fields = {"model": "whisper-large-v3-turbo", "language": "es", "response_format": "verbose_json", "timestamp_granularities[]": "word"}
            body = bytearray()
            for name, value in fields.items():
                body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.flac"\r\nContent-Type: audio/flac\r\n\r\n'.encode())
            body.extend(path.read_bytes())
            body.extend(f"\r\n--{boundary}--\r\n".encode())
            data = json.loads(self.request("groq", GROQ, content=bytes(body), key=key,
                                         headers={"Content-Type": "multipart/form-data; boundary="+boundary}))
        words, last = [], -1.
        for row in data.get("words", []):
            start, end = float(row["start"]), float(row["end"])
            if not (0 <= start <= end <= duration+.5) or start < last or not str(row["word"]).strip():
                raise Blocked("La transcripción contiene tiempos no válidos.")
            last = start
            words.append({"word": str(row["word"]), "start": start, "end": min(end, duration)})
        if not words:
            raise Blocked("No se detectaron palabras en el audio.")
        cache.write_text(dumps({"words": words}), "utf-8")
        return words
