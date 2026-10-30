from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import wave
from array import array

from PIL import Image, ImageDraw, ImageFont, ImageOps


class Cancelled(Exception):
    pass


def ffmpeg():
    path = shutil.which("ffmpeg")
    if path:
        return path
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, cancelled=lambda: False, timeout=3600, cwd=None):
    args = [args[0], "-filter_threads", "1", "-filter_complex_threads", "1", *args[1:]]
    with tempfile.TemporaryFile() as error:
        flags = subprocess.CREATE_NO_WINDOW if __import__("os").name == "nt" else 0
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=error, creationflags=flags, cwd=cwd)
        start = time.monotonic()
        while process.poll() is None:
            if cancelled() or time.monotonic()-start > timeout:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                if cancelled():
                    raise Cancelled("Trabajo cancelado; se conservan los recursos.")
                raise ValueError("La operación tardó demasiado. Prueba con 720p.")
            time.sleep(.08)
        if process.returncode:
            error.seek(0, 2)
            size = error.tell()
            error.seek(max(0, size-3000))
            detail = error.read().decode("utf-8", "replace")
            raise ValueError("FFmpeg no pudo procesar el material: " + detail[-1200:])


def probe(path):
    path = Path(path)
    exe = shutil.which("ffprobe")
    if exe:
        result = subprocess.run([exe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                                capture_output=True, timeout=30)
        if result.returncode:
            raise ValueError("El archivo no es un audio o video válido.")
        info = json.loads(result.stdout)
        streams = info.get("streams", [])
        duration = float(info.get("format", {}).get("duration", 0))
        video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        return {"duration": duration, "video": bool(video), "audio": bool(audio),
                "width": int(video.get("width", 0)) if video else 0, "height": int(video.get("height", 0)) if video else 0}
    # Portable imageio FFmpeg includes no ffprobe. Read only bounded diagnostics.
    result = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, timeout=30)
    text = result.stderr.decode("utf-8", "replace")
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError("No se pudo medir el archivo. Instala FFmpeg completo o importa otro archivo.")
    video = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", text)
    return {"duration": int(match[1])*3600+int(match[2])*60+float(match[3]), "video": bool(video),
            "audio": "Audio:" in text, "width": int(video[1]) if video else 0, "height": int(video[2]) if video else 0}


def clean_script(text):
    text = re.sub(r"\[[^\]]*\]|<#[^>]*#>|<[^>]+>", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def split_text(text, max_chars=450):
    parts, current = [], ""
    for line in re.split(r"(?<=[.!?…])\s+|\n+", clean_script(text)):
        for word in line.split():
            if len(current)+len(word)+1 > max_chars:
                parts.append(current)
                current = ""
            current = (current+" "+word).strip()
        if current and len(current) > max_chars*.65:
            parts.append(current)
            current = ""
    if current:
        parts.append(current)
    return parts


def plan_basic(script, duration, mode):
    sentences = [x.strip() for x in re.split(r"(?<=[.!?…])\s+|\n+", clean_script(script)) if x.strip()]
    if not sentences:
        raise ValueError("Añade un guion o elige un planificador de IA.")
    total = sum(max(1, len(s.split())) for s in sentences)
    groups, buf, weight = [], [], 0
    for sentence in sentences:
        buf.append(sentence)
        weight += max(1, len(sentence.split()))
        if duration*weight/total >= 8:
            groups.append((" ".join(buf), weight))
            buf, weight = [], 0
    if buf:
        if groups and duration*weight/total < 3:
            text, count = groups.pop()
            groups.append((text+" "+" ".join(buf), count+weight))
        else:
            groups.append((" ".join(buf), weight))
    scenes, at = [], 0.
    for i, (text, weight) in enumerate(groups):
        end = duration if i == len(groups)-1 else at+duration*weight/total
        scenes.append({"id": __import__("uuid").uuid4().hex, "text": text, "prompt": "",
                       "kind": "character" if mode == "characters" else "image", "speaker": "narrator",
                       "start": round(at, 3), "end": round(end, 3), "visual_asset": None,
                       "reference_ids": [], "identity_reviewed": False, "lipsync_reviewed": False,
                       "motion": "push", "transition": "cut", "effects": [], "locked": False})
        at = end
    return scenes


def fit_timing(scenes, duration):
    total = sum(len(s["text"].split()) or 1 for s in scenes)
    at, rows = 0., []
    for i, scene in enumerate(scenes):
        end = duration if i == len(scenes)-1 else at+duration*(len(scene["text"].split()) or 1)/total
        rows.append({**scene, "start": round(at, 3), "end": round(end, 3)})
        at = end
    return rows


def dimensions(aspect, resolution):
    short = int(resolution)
    long = int(round(short*16/9/2)*2)
    return {"9:16": (short, long), "16:9": (long, short), "1:1": (short, short)}[aspect]


def timestamp(seconds, sep=","):
    value = round(seconds*1000)
    hours, value = divmod(value, 3600000)
    mins, value = divmod(value, 60000)
    secs, ms = divmod(value, 1000)
    return f"{hours:02}:{mins:02}:{secs:02}{sep}{ms:03}"


def write_srt(scenes, path, words=None):
    # Subdivide whole-scene text into readable 7-word captions. These remain
    # estimates unless imported/aligned timings have been reviewed.
    rows, n = [], 1
    if words:
        for start in range(0, len(words), 7):
            group = words[start:start+7]
            rows.append(f"{n}\n{timestamp(group[0]['start'])} --> {timestamp(group[-1]['end'])}\n{' '.join(w['word'] for w in group)}\n")
            n += 1
        Path(path).write_text("\n".join(rows), "utf-8")
        return
    for scene in scenes:
        words = clean_script(scene["text"]).split()
        groups = [words[i:i+7] for i in range(0, len(words), 7)]
        at = scene["start"]
        for group in groups:
            end = at+(scene["end"]-scene["start"])*len(group)/max(1, len(words))
            rows.append(f"{n}\n{timestamp(at)} --> {timestamp(end)}\n{' '.join(group)}\n")
            at, n = end, n+1
    Path(path).write_text("\n".join(rows), "utf-8")


def synthetic_effect(kind, path):
    # Original procedural effects, no external library or ambiguous licenses.
    sr, duration = 24000, {"knock": .8, "phone": 1.4, "impact": 1.2, "whoosh": .8, "chime": 1.2}.get(kind, .8)
    samples = array("h")
    for n in range(int(sr*duration)):
        t = n/sr
        if kind == "phone":
            value = .25*(math.sin(2*math.pi*440*t)+math.sin(2*math.pi*480*t))*(1 if t%.6 < .4 else 0)
        elif kind == "knock":
            phase = t%.24
            value = math.sin(2*math.pi*150*phase)*math.exp(-phase*50)*.7 if t < .72 else 0
        elif kind == "chime":
            value = .5*math.sin(2*math.pi*660*t)*math.exp(-3*t)
        elif kind == "whoosh":
            value = .45*math.sin(2*math.pi*(300*t+900*t*t))*math.sin(math.pi*t/duration)**2
        else:
            value = .7*math.sin(2*math.pi*(55*t-12*t*t))*math.exp(-5*t)
        samples.append(int(max(-1, min(1, value))*28000))
    if __import__("sys").byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, sr, 0, "NONE", "not compressed"))
        out.writeframes(samples.tobytes())


def write_ass(srt, target, width, height):
    """Explicit canvas coordinates avoid SRT's tiny default ASS play resolution."""
    font_size = round(min(width, height)*.052)
    margin_v = round(height*(.16 if height > width else .10))
    header = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
              "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
              "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
              f"Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H0012151C,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,{round(width*.065)},{round(width*.11)},{margin_v},1\n\n"
              "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    rows = []
    for block in Path(srt).read_text("utf-8").strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        start, end = lines[1].split(" --> ")
        def ass_time(value):
            return str(int(value[:2]))+value[2:].replace(",", ".")[:-1]
        text = " ".join(lines[2:]).replace("\\", " ").replace("{", "(").replace("}", ")")
        rows.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}")
    Path(target).write_text(header+"\n".join(rows)+"\n", "utf-8")


def make_cover(video, target, title, duration, cancelled=lambda: False):
    frame = Path(target).with_suffix(".frame.png")
    run([ffmpeg(), "-y", "-v", "error", "-ss", str(min(2, duration*.2)), "-i", str(video), "-frames:v", "1", str(frame)], cancelled)
    with Image.open(frame) as source:
        image = source.convert("RGBA")
    width, height = image.size
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)
    for y in range(height//2, height):
        draw.line((0, y, width, y), fill=(8, 10, 18, round(220*(y-height/2)/(height/2))))
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)
    size = round(min(width, height)*.07)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        font = ImageFont.load_default(size=size)
    lines, line = [], ""
    for word in title.split():
        trial = (line+" "+word).strip()
        if draw.textlength(trial, font=font) > width*.82 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    lines = lines[:4]
    text = "\n".join(lines)
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=8)
    draw.multiline_text((width*.075, height*.85-(box[3]-box[1])), text, font=font, spacing=8, fill="white", stroke_width=1, stroke_fill="#10131e")
    image.convert("RGB").save(target, quality=94)
    frame.unlink(missing_ok=True)
    return Path(target)


def render(store, project, work, cancelled, log):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    width, height = dimensions(project["aspect"], project["resolution"])
    fps, segments = 24, []
    for index, scene in enumerate(project["scenes"]):
        if cancelled():
            raise Cancelled()
        path = store.asset_path(scene["visual_asset"], project["id"])
        length = scene["end"]-scene["start"]
        # Quantize shared boundaries rather than rounding every duration
        # independently, preventing cumulative drift on long timelines.
        frames = max(1, round(scene["end"]*fps)-round(scene["start"]*fps))
        signature = hashlib.sha256(json.dumps({"scene": scene, "file": str(path), "size": path.stat().st_size,
                                               "wh": [width, height], "v": 4}, sort_keys=True).encode()).hexdigest()
        target = work / (signature+".mp4")
        segments.append(target)
        if target.exists():
            log(f"Plano {index+1}: reutilizando montaje.")
            continue
        temp = work / (signature+".part.mp4")
        log(f"Montando plano {index+1}/{len(project['scenes'])}…")
        common = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-threads", "2"]
        if scene["kind"] == "image":
            frame = work / (signature+".jpg")
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                ImageOps.fit(image, (width*2, height*2)).save(frame, quality=94)
            zoom = {"push": f"1+0.06*on/{frames}", "pull": f"1.06-0.06*on/{frames}", "still": "1"}[scene["motion"]]
            vf = f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s={width}x{height}:fps={fps}"
            if scene["transition"] == "fade":
                vf += ",fade=t=in:st=0:d=0.2"
            run([ffmpeg(), "-y", "-v", "error", "-i", str(frame), "-vf", vf, "-frames:v", str(frames), *common, str(temp)], cancelled)
        else:
            info = probe(path)
            offset = scene.get("source_offset", 0)
            if info["duration"]+.08 < length+offset:
                raise ValueError(f"El clip del plano {index+1} es más corto que la escena. Ajusta sus tiempos.")
            vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}"
            if scene["transition"] == "fade":
                vf += ",fade=t=in:st=0:d=0.2"
            run([ffmpeg(), "-y", "-v", "error", "-ss", str(offset), "-i", str(path), "-vf", vf, "-frames:v", str(frames), *common, str(temp)], cancelled)
        temp.replace(target)
    concat = work / "concat.txt"
    # Names in this manifest are locally generated hex strings, never user paths.
    concat.write_text("\n".join("file '"+s.name+"'" for s in segments), "utf-8")
    joined = work / "joined.mp4"
    run([ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "1", "-i", str(concat), "-c", "copy", str(joined)], cancelled)
    duration = project["scenes"][-1]["end"]
    audio = store.asset_path(project["audio_asset"], project["id"])
    mixed = work / "mixed.wav"
    inputs = ["-i", str(audio)]
    filters = ["[0:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS,alimiter=limit=0.95[v]"]
    labels, input_index = ["[v]"], 1
    if project.get("music_asset"):
        inputs += ["-stream_loop", "-1", "-i", str(store.asset_path(project["music_asset"], project["id"]))]
        filters[0] = filters[0].replace("[v]", "[v0]")
        filters += ["[v0]asplit=2[v][side]", f"[{input_index}:a]aresample=48000,aformat=channel_layouts=stereo,volume={project['music_gain']}[bg]",
                    "[bg][side]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[m]"]
        labels.append("[m]")
        input_index += 1
    # Mix effects in small intermediate files to keep input concurrency bounded.
    effects = []
    for scene in project["scenes"]:
        for effect in scene.get("effects", []):
            kind = effect.get("type", "")
            if kind not in {"knock", "phone", "impact", "whoosh", "chime"}:
                continue
            at = scene["start"] + max(0, min(float(effect.get("offset", 0)), scene["end"]-scene["start"]))
            gain = max(0, min(.4, float(effect.get("gain", .18))))
            path = work / (kind+".wav")
            if not path.exists():
                synthetic_effect(kind, path)
            effects.append((path, at, gain))
    filters.append("".join(labels)+f"amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.95[a]")
    run([ffmpeg(), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[a]", "-t", str(duration), str(mixed)], cancelled)
    for batch_start in range(0, len(effects), 6):
        args, fx, tracks = ["-i", str(mixed)], [], ["[0:a]"]
        for n, (path, at, gain) in enumerate(effects[batch_start:batch_start+6], 1):
            args += ["-i", str(path)]
            fx.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain},adelay={round(at*1000)}|{round(at*1000)}[s{n}]")
            tracks.append(f"[s{n}]")
        fx.append("".join(tracks)+f"amix=inputs={len(tracks)}:normalize=0,alimiter=limit=0.95[a]")
        next_mix = work / f"mix_{batch_start}.wav"
        run([ffmpeg(), "-y", "-v", "error", *args, "-filter_complex", ";".join(fx), "-map", "[a]", "-t", str(duration), str(next_mix)], cancelled)
        mixed = next_mix
    subtitles = work / "subtitles.srt"
    write_srt(project["scenes"], subtitles, project.get("words") if project.get("timing") == "transcribed" else None)
    ass = work / "subtitles.ass"
    write_ass(subtitles, ass, width, height)
    final = work / "video.part.mp4"
    args = [ffmpeg(), "-y", "-v", "error", "-i", str(joined), "-i", str(mixed)]
    if project["subtitles"] and project["burn_subtitles"]:
        # Use a fixed local filename in a per-process cwd: no filter escaping of
        # user profile paths (Windows drive letters, apostrophes, or accents).
        args += ["-vf", "ass=filename=subtitles.ass",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-threads", "2"]
    else:
        args += ["-c:v", "copy"]
    args += ["-map", "0:v:0", "-map", "1:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k",
             "-t", str(duration), "-movflags", "+faststart", str(final)]
    log("Mezclando audio y subtítulos…")
    run(args, cancelled, cwd=work)
    log("Verificando decodificación completa…")
    run([ffmpeg(), "-v", "error", "-xerror", "-i", str(final), "-f", "null", "-"], cancelled)
    info = probe(final)
    if not info["video"] or not info["audio"] or abs(info["duration"]-duration) > .3:
        raise ValueError("La verificación final detectó duración o pistas incorrectas.")
    target = store.root / "exports" / f"{project['id']}-r{project['revision']}.mp4"
    final.replace(target)
    return target, subtitles, info
