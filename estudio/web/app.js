"use strict";
const $ = (s) => document.querySelector(s);
const token = $('meta[name="studio-token"]').content;
let state = { projects: [], channels: [], jobs: [] },
  view = "projects",
  project = null,
  tab = "scenes",
  page = 0,
  filter = "all";
let uploading = null,
  pollBusy = false,
  toastTimer = null,
  editorDirty = false;
const E = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const labels = {
  draft: "Borrador",
  planned: "Planificado",
  review: "Revisar",
  ready: "Listo para reproducir",
  rendering: "Montando",
  queued: "En cola",
  waiting: "Esperando cuota",
  running: "Trabajando",
  done: "Completado",
  error: "Error",
  cancelled: "Cancelado",
  scheduled: "Programado",
  uploading: "Subiendo",
  uploaded: "Subida confirmada",
  processing: "Procesando en plataforma",
  published: "Publicado",
  unknown: "Resultado por comprobar",
  blocked: "Bloqueado",
};
const modes = {
  narration: "Narración visual",
  characters: "Personajes",
  mixed: "Mixto",
};
const kinds = {
  prepare: "Preparar guion y voz",
  generate: "Generar recursos",
  align: "Sincronizar audio",
  render: "Exportar video",
  produce: "Producción completa",
  publish: "Publicar",
};
const badge = (s) => `<span class="tag ${E(s)}">${E(labels[s] || s)}</span>`;
const time = (s) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const options = (rows, value) =>
  rows
    .map(
      ([v, t]) =>
        `<option value="${E(v)}" ${v === value ? "selected" : ""}>${E(t)}</option>`,
    )
    .join("");
async function api(url, method = "GET", body) {
  const headers = { "X-Studio-Token": token };
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const response = await fetch(url, {
    method,
    headers,
    body:
      body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  });
  const data = await response
    .json()
    .catch(() => ({ detail: "No se pudo leer la respuesta." }));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
function toast(message, error = false) {
  const t = $("#toast");
  t.textContent = message;
  t.className = "toast" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => t.classList.add("hidden"),
    error ? 12000 : 6000,
  );
}
function modal(title, subtitle, body) {
  $("#modal-content").innerHTML =
    `<div class="modal-head"><div><h2>${E(title)}</h2><p>${E(subtitle)}</p></div><button class="icon-button" data-action="close" aria-label="Cerrar">×</button></div>${body}`;
  $("#modal").showModal();
}
const close = () => $("#modal").close();
function field(name, label, value = "", type = "text", extra = "") {
  return `<label>${E(label)}<input name="${E(name)}" type="${type}" value="${E(value)}" ${extra}></label>`;
}
function area(name, label, value = "", extra = "") {
  return `<label>${E(label)}<textarea name="${E(name)}" ${extra}>${E(value)}</textarea></label>`;
}
function select(name, label, rows, value) {
  return `<label>${E(label)}<select name="${E(name)}">${options(rows, value)}</select></label>`;
}
function check(name, label, checked = false) {
  return `<label class="check"><input type="checkbox" name="${E(name)}" ${checked ? "checked" : ""}>${E(label)}</label>`;
}
function actions(label) {
  return `<div class="modal-actions"><button type="button" data-action="close">Cancelar</button><button class="primary" type="submit">${E(label)}</button></div>`;
}
async function refreshState(redraw = true) {
  state = await api("/api/state");
  $("#queue-count").textContent = state.jobs.filter((j) =>
    ["queued", "waiting", "running"].includes(j.status),
  ).length;
  if (redraw) render();
}
async function openProject(id) {
  project = await api("/api/projects/" + id);
  editorDirty = false;
  view = "editor";
  tab = "scenes";
  page = 0;
  render();
}
function render() {
  document
    .querySelectorAll("[data-view]")
    .forEach((el) =>
      el.classList.toggle(
        "active",
        el.dataset.view === view ||
          (view === "editor" && el.dataset.view === "projects"),
      ),
    );
  $("#breadcrumb").textContent =
    "Mi espacio / " +
    {
      projects: "Proyectos",
      editor: project?.title,
      queue: "Cola de producción",
      channels: "Mis canales",
      connections: "Conexiones",
    }[view];
  if (view === "projects") renderProjects();
  if (view === "editor" && project) renderEditor();
  if (view === "queue") renderQueue();
  if (view === "channels") renderChannels();
  if (view === "connections")
    renderConnections().catch((e) => toast(e.message, true));
}
function renderProjects() {
  const list = state.projects.filter(
    (p) => filter === "all" || p.format === filter,
  );
  $("#main").innerHTML =
    `<div class="page-head"><div><span class="eyebrow">DE LA IDEA AL VIDEO</span><h1>Tu próxima historia empieza aquí.</h1><p>Un espacio para tus canales, escenas y videos terminados.</p></div><button class="primary" data-action="new-project">＋ Nuevo proyecto</button></div>
  <div class="stats"><div class="stat"><strong>${state.projects.length}</strong><span>Proyectos guardados</span></div><div class="stat"><strong>${state.jobs.filter((j) => ["queued", "waiting", "running"].includes(j.status)).length}</strong><span>Trabajos pendientes</span></div><div class="stat"><strong>${state.projects.filter((p) => p.state === "ready").length}</strong><span>Videos exportados</span></div></div>
  <div class="row spread"><div class="filters">${[
    ["all", "Todos"],
    ["reel", "Reels"],
    ["long", "Largos"],
    ["pilot", "Pruebas cortas"],
  ]
    .map(
      ([f, t]) =>
        `<button data-filter="${f}" class="${filter === f ? "selected" : ""}">${t}</button>`,
    )
    .join(
      "",
    )}</div><span class="hint">50 reels + 20 largos: referencia semanal ajustable</span></div>
  ${
    list.length
      ? `<div class="project-grid">${list.map((p) => `<button class="project-card" data-open="${p.id}"><div class="card-art" data-mode="${p.mode}"><span class="art-icon">${p.mode === "characters" ? "◉ ◉" : p.mode === "mixed" ? "◈" : "▤"}</span><span class="tag">${p.format === "long" ? "VIDEO LARGO" : p.format === "pilot" ? "PRUEBA CORTA" : "REEL"} · ${time(p.duration)}</span></div><div class="card-content"><h3>${E(p.title)}</h3><div class="card-meta"><span>${E(state.channels.find((c) => c.id === p.channel_id)?.name || "Canal")}</span><span>${E(modes[p.mode])}</span></div><div class="card-bottom">${badge(p.state)}<span>Editar →</span></div></div></button>`).join("")}</div>`
      : `<div class="empty"><div class="empty-icon">▤</div><h3>Todo listo para tu primer proyecto.</h3><p>Empieza con una prueba de 10–30 segundos para comprobar voces, imágenes y personajes.</p><button class="primary" data-action="new-project">Crear mi primer video</button> <button data-action="example">Probar ejemplo sin claves</button><p class="hint">El ejemplo solicita una voz y una imagen a los endpoints gratuitos anónimos. Puede esperar por cuota.</p></div>`
  }`;
}
function newProject() {
  modal(
    "Crea un proyecto",
    "Elige el canal y cómo quieres contar esta historia.",
    `<form id="project-form">
    <div class="grid2">${field("title", "Título del proyecto", "", "text", 'required maxlength="150"')}${select(
      "channel_id",
      "Canal",
      state.channels.map((c) => [c.id, c.name]),
      state.channels[0]?.id,
    )}</div>
    <div class="grid3">${select(
      "format",
      "Formato",
      [
        ["pilot", "Prueba corta · 5–30 s"],
        ["reel", "Reel · 90–150 s"],
        ["long", "Largo · 5–15 min"],
      ],
      "pilot",
    )}${field("duration", "Duración en segundos", 15, "number", 'min="5" max="900" required')}${select(
      "aspect",
      "Encuadre",
      [
        ["9:16", "Vertical 9:16"],
        ["16:9", "Horizontal 16:9"],
        ["1:1", "Cuadrado 1:1"],
      ],
      "9:16",
    )}</div>
    ${select("mode", "Forma de producción", Object.entries(modes), "narration")}
    <p class="preset-description">Narración: imágenes y clips con voz en off. Personajes: clips con actuación y diálogo. Mixto: el tipo se decide por escena. Personajes requiere clips propios o un conector de video compatible.</p>
    ${area("script", "Tu guion (con o sin etiquetas de voz)", "", 'rows="5" placeholder="Pega aquí tu historia. También puedes dejarla vacía y describir el tema abajo."')}
    ${field("topic", "Tema o idea (si necesitas generar el guion)")}
    <div class="grid2">${select(
      "content_type",
      "Tipo de contenido",
      [
        ["fiction", "Ficción"],
        ["factual", "Hechos / divulgación"],
        ["opinion", "Opinión"],
      ],
      "fiction",
    )}${select(
      "planner",
      "Planificación",
      [
        ["manual", "Manual · sin clave"],
        ["openrouter", "IA · OpenRouter gratuito"],
        ["omniroute", "IA · OmniRoute configurado"],
      ],
      "manual",
    )}</div>
    <details><summary>Voz, imágenes y calidad</summary><div class="grid2">${select(
      "audio_source",
      "Narración",
      [
        ["upload", "Voy a subir mi audio"],
        ["riva", "Generar con Riva gratuito"],
      ],
      "upload",
    )}${select(
      "image_source",
      "Recursos visuales",
      [
        ["upload", "Voy a subir imágenes o clips"],
        ["sdxl", "Generar imágenes con SDXL"],
        ["bridge", "Conector con referencias"],
      ],
      "upload",
    )}</div><div class="grid2">${select(
      "resolution",
      "Resolución",
      [
        ["720", "720p · menos carga"],
        ["1080", "1080p"],
      ],
      "720",
    )}${check("subtitles", "Incluir subtítulos", true)}</div></details>
    ${actions("Crear proyecto")}
  </form>`,
  );
}
function renderEditor() {
  const p = project,
    active = p.jobs.find(
      (j) =>
        ["running", "waiting", "queued"].includes(j.status) &&
        j.kind !== "publish",
    );
  $("#main").innerHTML =
    `<div class="page-head"><div><button class="small ghost" data-view="projects">← Proyectos</button><h1>${E(p.title)}</h1><div class="row"><span class="hint">${E(modes[p.mode])} · ${p.aspect} · ${p.resolution}p · Revisión ${p.revision}</span>${badge(p.state)}</div></div><button data-action="project-settings">Ajustes</button></div>
  ${active ? `<div class="notice row spread"><span><strong>${E(kinds[active.kind])}</strong> · ${E(active.message || "En cola")}${active.status === "waiting" ? `<br>Próximo intento: ${new Date(active.next_run * 1000).toLocaleString()}` : ""}</span><button class="small" data-cancel="${active.id}">Cancelar trabajo</button></div>` : ""}
  <div class="editor-grid"><div><div class="tabs">${[
    ["scenes", "Escenas"],
    ["script", "Guion y referencias"],
    ["review", "Revisión"],
    ["publish", "Publicación"],
  ]
    .map(
      ([v, t]) =>
        `<button data-tab="${v}" class="${tab === v ? "selected" : ""}">${t}</button>`,
    )
    .join("")}</div><div id="editor-body"></div></div>
  <aside class="player-panel"><div class="row spread"><h3>Tu video</h3><span class="tag">${E(p.aspect)}</span></div>
  <div class="player">${p.output_asset ? `<video src="/media/${E(p.output_asset)}" controls preload="metadata"></video>` : `<div class="player-placeholder"><span>▷</span>Aquí verás la exportación.<br>Prepara, revisa y crea tu video.</div>`}</div>
  ${p.audio_asset ? `<span class="hint">Narración cargada</span><audio src="/media/${E(p.audio_asset)}" controls preload="metadata"></audio>` : ""}
  <div class="step-label">01 / PREPARACIÓN</div><button class="full" data-job="prepare">Preparar guion y voz</button><button class="full ghost" data-upload="narration">↑ Cargar narración</button>
  <div class="step-label">02 / PRODUCCIÓN</div><button class="full" data-job="generate">Generar recursos faltantes</button><button class="full ghost" data-upload="music">♪ Cargar música</button>
  <div class="step-label">03 / ENTREGA</div><button class="primary full" data-job="render">Exportar video</button>
  ${p.output_asset ? `<a class="export-link" href="/media/${E(p.output_asset)}?download=true">↓ Descargar MP4</a>` : ""}
  ${p.cover_asset ? `<a class="hint export-link" href="/media/${E(p.cover_asset)}?download=true">↓ Descargar portada</a>` : ""}
  <a class="hint export-link" href="/api/projects/${p.id}/package">↓ Materiales y subtítulos</a><p class="hint">Se revisa el contenido antes de exportar. Tus escenas terminadas se reutilizan al reanudar.</p></aside></div>`;
  if (tab === "scenes") renderScenes();
  if (tab === "script") renderScript();
  if (tab === "review") renderReview();
  if (tab === "publish") renderPublish();
}
function renderScenes() {
  const p = project,
    from = page * 8,
    rows = p.scenes.slice(from, from + 8);
  $("#editor-body").innerHTML =
    `<div class="row spread"><div><h3>Escenas de tu historia</h3><p class="hint">${p.scenes.length} planos · Tiempos ${p.timing === "estimated" ? "estimados: revisa el audio" : p.timing === "transcribed" ? "obtenidos por transcripción" : "medidos por fragmento de voz"}</p></div><button class="small" data-job="align">Sincronizar con Groq</button></div>
  ${p.adaptation_note ? `<div class="notice amber">${E(p.adaptation_note)}</div>` : ""}
  ${
    rows.length
      ? rows
          .map((s, n) => {
            const a = p.assets.find((a) => a.id === s.visual_asset);
            return `<article class="scene"><div class="scene-thumb">${a?.kind === "image" ? `<img src="/media/${a.id}" alt="Plano ${from + n + 1}" loading="lazy">` : a?.kind === "video" ? "▷" : "＋"}</div><div class="scene-info"><span class="scene-number">PLANO ${String(from + n + 1).padStart(2, "0")} · ${s.kind === "character" ? "PERSONAJE" : s.kind === "clip" ? "CLIP" : "IMAGEN"}</span><p>${E(s.text.length > 150 ? s.text.slice(0, 150) + "…" : s.text)}</p><span class="time">${time(s.start)} → ${time(s.end)} · ${a ? "Recurso listo" : "Falta recurso"} ${s.reference_ids.length ? "· " + s.reference_ids.length + " referencias" : ""}</span></div><button class="small" data-scene="${s.id}">Editar</button></article>`;
          })
          .join("")
      : `<div class="empty"><div class="empty-icon">◫</div><h3>Primero prepara tu historia.</h3><p>El guion se dividirá por unidades de sentido. Después podrás corregir cada plano.</p><button data-job="prepare" class="primary">Preparar escenas</button></div>`
  }
  ${p.scenes.length > 8 ? `<div class="pagination"><button class="small" data-page="${page - 1}" ${page === 0 ? "disabled" : ""}>← Anteriores</button><span>Bloque ${page + 1} de ${Math.ceil(p.scenes.length / 8)}</span><button class="small" data-page="${page + 1}" ${from + 8 >= p.scenes.length ? "disabled" : ""}>Siguientes →</button></div>` : ""}`;
}
function sceneModal(id) {
  const s = project.scenes.find((s) => s.id === id),
    i = project.scenes.indexOf(s),
    asset = project.assets.find((a) => a.id === s.visual_asset),
    refs = project.assets.filter((a) => a.role === "reference");
  modal(
    "Plano " + String(i + 1).padStart(2, "0"),
    "Los cambios se guardan en esta escena y reinician su revisión.",
    `<form id="scene-form" data-id="${E(id)}">
    ${asset ? (asset.kind === "image" ? `<img class="inline-preview" src="/media/${asset.id}" alt="Plano">` : `<video class="inline-preview" src="/media/${asset.id}" controls preload="metadata"></video>`) : ""}
    <div class="grid3">${field("start", "Inicio (segundos)", s.start, "number", 'min="0" step="0.001" required')}${field("end", "Final (segundos)", s.end, "number", 'min="0.01" step="0.001" required')}${select(
      "kind",
      "Tipo",
      [
        ["image", "Imagen con movimiento"],
        ["clip", "Clip narrativo"],
        ["character", "Personaje en diálogo"],
      ],
      s.kind,
    )}</div>
    ${area("text", "Narración de este plano", s.text, 'rows="3" required')}${area("prompt", "Descripción visual / prompt", s.prompt, 'rows="4" placeholder="Un plano concreto: sujeto, lugar, acción, encuadre e iluminación."')}
    <div class="grid2">${field("speaker", "Voz / personaje (narrator para narrador)", s.speaker)}${select(
      "motion",
      "Movimiento de imagen",
      [
        ["push", "Acercamiento lento"],
        ["pull", "Alejamiento lento"],
        ["still", "Sin movimiento"],
      ],
      s.motion,
    )}</div>
    ${select(
      "transition",
      "Entrada al plano",
      [
        ["cut", "Corte directo"],
        ["fade", "Fundido corto"],
      ],
      s.transition,
    )}
    <div class="row"><button type="button" data-upload="scene" data-scene-upload="${s.id}">↑ Cargar imagen o clip</button><button type="button" data-upload="reference" data-scene-upload="${s.id}">＋ Referencia</button></div>
    ${refs.length ? `<details open><summary>Referencias persistentes</summary>${refs.map((r) => check("ref_" + r.id, "@" + (r.name || r.id.slice(0, 8)), s.reference_ids.includes(r.id))).join("")}<p class="hint">El conector debe admitir imágenes de referencia. Escribir @ por sí solo no vincula un archivo.</p></details>` : ""}
    <details><summary>Sonido y revisión de personajes</summary><div class="grid3">${select(
      "effect",
      "Efecto",
      [
        ["", "Ninguno"],
        ["knock", "Tres golpes"],
        ["phone", "Teléfono"],
        ["impact", "Impacto grave"],
        ["whoosh", "Barrido"],
        ["chime", "Campanilla"],
      ],
      s.effects[0]?.type || "",
    )}${field("offset", "A los segundos", s.effects[0]?.offset || 0, "number", 'min="0" step="0.1"')}${field("gain", "Volumen (0–0.4)", s.effects[0]?.gain || 0.18, "number", 'min="0" max="0.4" step="0.01"')}</div>${check("identity_reviewed", "Revisé rostro, vestuario y continuidad del personaje", s.identity_reviewed)}${check("lipsync_reviewed", "Revisé la voz y sincronización labial del clip", s.lipsync_reviewed)}</details>
    ${check("regenerate", "Descartar la asignación visual para generar otra versión (conserva el archivo anterior)", false)}${actions("Guardar plano")}</form>`,
  );
}
function renderScript() {
  const p = project,
    refs = p.assets.filter((a) => a.role === "reference");
  $("#editor-body").innerHTML =
    `<div class="panel"><div class="row spread"><h3>Guion</h3><button class="small" data-action="project-settings">Editar guion</button></div><div class="reading">${E(p.script || "Todavía no hay guion.")}</div></div><div class="panel"><div class="row spread"><h3>Guía visual de continuidad</h3><button class="small" data-action="bible">Editar</button></div><p class="reading">${E(p.visual_bible || "Define aquí personajes, vestuario, lugares, arquitectura y estilo persistentes.")}</p><button class="small" data-upload="reference">＋ Subir referencia</button><div class="ref-grid">${refs.map((a) => `<div class="reference"><img src="/media/${a.id}" alt="Referencia">@${E(a.name || a.id.slice(0, 8))}</div>`).join("")}</div></div><div class="panel"><div class="row spread"><h3>Fuentes del contenido</h3><button class="small" data-action="sources">Añadir / editar</button></div>${p.sources.length ? p.sources.map((s) => `<p><strong>${E(s.title)}</strong><br><span class="hint">${E(s.url)}</span><br>${E(s.claim || "")}</p>`).join("") : '<p class="hint">Para contenido factual, registra qué afirmación respalda cada fuente y revísala.</p>'}</div><div class="panel"><h3>Crear un reel derivado</h3><p class="hint">Reutiliza un fragmento de 90–150 s. Tendrás que revisar apertura, contexto, cierre y reencuadre.</p><button class="small" data-action="adapt">Elegir fragmento</button></div>`;
}
function renderReview() {
  const p = project,
    q = p.quality_now;
  $("#editor-body").innerHTML =
    `<div class="panel"><h3>Revisión del proyecto</h3><p class="hint">La revisión se invalida al cambiar contenido. Los controles automáticos no pueden confirmar por sí solos hechos, derechos o identidad visual.</p><form id="review-form">${[["editorial", "Guion: coherencia, contexto y cierre"], ["rights", "Recursos, música y voz con derechos de uso"], ["timing", "Narración, pronunciación, tiempos y subtítulos"], ["continuity", "Planos, lugares y personajes consistentes"], ...(p.content_type === "factual" ? [["factual", "Comprobé las afirmaciones con las fuentes registradas"]] : []), ...(p.output_asset ? [["playback", "Reproduje y aprobé el MP4 final completo"]] : [])].map(([k, l]) => check(k, l, !!p.review[k])).join("")}<button type="submit" class="primary">Guardar revisión</button></form></div><div class="notice ${q.ok ? "good" : "amber"}"><strong>${q.ok ? "Proyecto preparado para exportar" : "Pendientes antes de exportar"}</strong>${q.errors.length ? `<ul class="error-list">${q.errors.map((e) => `<li>${E(e)}</li>`).join("")}</ul>` : ""}${q.warnings.map((w) => `<p class="hint">${E(w)}</p>`).join("")}</div>${p.technical_report ? `<div class="panel"><h3>Archivo verificado</h3><p class="hint">Decodificación completa: ${p.technical_report.decoded ? "correcta" : "pendiente"}<br>${p.technical_report.width} × ${p.technical_report.height} · ${time(p.technical_report.duration)}<br>Audio normalizado con objetivo −16 LUFS. La sonoridad final requiere escucha; no se presenta como medición certificada.</p></div>` : ""}`;
}
function renderPublish() {
  const p = project;
  $("#editor-body").innerHTML =
    `<div class="notice">Puedes descargar el MP4 y subirlo tú mismo, o programar una publicación con las APIs oficiales. Cada cuenta necesita permisos y una aplicación elegible. El estudio debe permanecer abierto para ejecutar lo programado.</div><div class="panel"><h3>Publicar o programar</h3><form id="publish-form"><div class="grid2">${select(
      "platform",
      "Destino",
      [
        ["youtube", "YouTube"],
        ["facebook", "Facebook · Página"],
        ["tiktok", "TikTok"],
      ],
      "youtube",
    )}${field("account", "Nombre de conexión", "default")}</div>${field("title", "Título", p.title, "text", 'maxlength="100" required')}${area("description", "Descripción", p.description || "", 'maxlength="5000"')}<div class="grid2">${select(
      "privacy",
      "Visibilidad",
      [
        ["private", "YouTube: privado"],
        ["unlisted", "YouTube: no listado"],
        ["public", "YouTube / Facebook: público"],
        ["SELF_ONLY", "TikTok: solo yo"],
        ["PUBLIC_TO_EVERYONE", "TikTok: público"],
        ["MUTUAL_FOLLOW_FRIENDS", "TikTok: amigos"],
      ],
      "private",
    )}${field("when", "Fecha y hora local (vacío = ahora)", "", "datetime-local")}</div>${check("made_for_kids", "Contenido creado para niños", false)}${check("ai_generated", "El video contiene material generado con IA", true)}${check("authorize", "Autorizo esta publicación, su cuenta, contenido y visibilidad", false)}<button class="primary" type="submit">Guardar publicación</button></form></div>${p.publications.map((pub) => `<div class="job"><div class="job-title"><strong>${E(pub.platform)} · ${E(pub.account)}</strong>${badge(pub.status)}</div><p>${E(pub.data.title)}</p>${pub.data.remote_id ? `<p class="hint">ID confirmado: ${E(pub.data.remote_id)}</p><button class="small" data-refresh-publication="${pub.id}">Comprobar en plataforma</button>` : '<p class="hint">Aún no hay un identificador remoto confirmado.</p>'}</div>`).join("")}`;
}
function renderQueue() {
  $("#main").innerHTML =
    `<div class="page-head"><div><span class="eyebrow">PRODUCCIÓN CON MEMORIA</span><h1>La cola de tu estudio.</h1><p>Un trabajo a la vez para cuidar tu equipo. Las cuotas se esperan.</p></div></div>${state.jobs.length ? state.jobs.map((job) => `<article class="job"><div class="job-title"><strong>${E(state.projects.find((p) => p.id === job.project_id)?.title || "Proyecto")} · ${E(kinds[job.kind])}</strong>${badge(job.status)}</div><p>${E(job.message || "Esperando turno")}</p>${job.status === "waiting" ? `<p class="hint">Próximo intento: ${new Date(job.next_run * 1000).toLocaleString()}</p>` : ""}<div class="row"><button class="small" data-open="${job.project_id}">Abrir proyecto</button>${["queued", "waiting", "running"].includes(job.status) ? `<button class="small danger" data-cancel="${job.id}">Cancelar</button>` : ""}<button class="small ghost" data-events="${job.id}">Ver registro</button></div></article>`).join("") : '<div class="empty">No hay trabajos pendientes.</div>'}`;
}
function renderChannels() {
  $("#main").innerHTML =
    `<div class="page-head"><div><span class="eyebrow">UNA IDENTIDAD PARA CADA CANAL</span><h1>Historias distintas. Estilos propios.</h1><p>Define voces, público, reglas y apariencia una sola vez.</p></div><button class="primary" data-action="new-channel">＋ Crear canal</button></div><div class="project-grid">${state.channels.map((c) => `<div class="panel"><span class="eyebrow">${E(c.language.toUpperCase())}</span><h2>${E(c.name)}</h2><p>${E(c.theme)}</p><p class="hint">Público: ${E(c.audience)}<br>${E(c.style)}</p><div class="divider"></div><button data-channel="${c.id}">Editar perfil</button><button class="ghost small" data-ideas="${c.id}">Proponer temas</button></div>`).join("")}</div>`;
}
function channelModal(id) {
  const c = state.channels.find((c) => c.id === id) || {
    name: "",
    theme: "",
    audience: "Público general",
    style: "Fotografía cinematográfica natural",
    language: "es",
    rules: "",
    voice: "Spanish-ES-Male-1",
    character_voices: {},
  };
  modal(
    id ? "Editar canal" : "Tu nuevo canal",
    "Sus reglas se aplicarán a las próximas generaciones.",
    `<form id="channel-form" data-id="${E(id || "")}">${field("name", "Nombre", c.name, "text", "required")}${field("theme", "Temática", c.theme)}${field("audience", "Público", c.audience)}${area("style", "Estilo visual", c.style)}${area("rules", "Reglas editoriales", c.rules)}<div class="grid2">${field("language", "Idioma", c.language)}${select(
      "voice",
      "Voz de narrador Riva",
      [
        ["Spanish-ES-Male-1", "Masculina · español de España"],
        ["Spanish-ES-Female-1", "Femenina · español de España"],
      ],
      c.voice,
    )}</div><details><summary>Voces de personajes</summary>${area("character_voices", "JSON: nombre del personaje → voz Riva", JSON.stringify(c.character_voices, null, 2))}<p class="hint">Ejemplo: {"Teresa":"Spanish-ES-Female-1"}. Usa exactamente el nombre del campo Voz de cada escena. También puedes importar una narración con tus voces.</p></details>${actions("Guardar canal")}</form>`,
  );
}
async function renderConnections() {
  const c = await api("/api/connections");
  if (view !== "connections") return;
  $("#main").innerHTML =
    `<div class="page-head"><div><span class="eyebrow">TUS HERRAMIENTAS, CONECTADAS</span><h1>Conecta una vez. Crea a tu ritmo.</h1><p>Las claves se introducen aquí y nunca se incluyen en los videos o paquetes.</p></div></div><div class="notice ${c.backend === "memory" ? "amber" : "good"}">${c.backend === "memory" ? "Este entorno permite claves solo durante la sesión. En Windows se ofrece almacenamiento protegido por tu usuario. No se guardarán en un archivo de texto." : "Almacenamiento seguro disponible: " + E(c.backend) + ". Puedes recordar las claves en este equipo."}</div><div class="connection-grid">${[
      [
        "openrouter",
        "OpenRouter",
        "Ideas, guiones y planificación con openrouter/free.",
        "https://openrouter.ai/keys",
      ],
      [
        "groq",
        "Groq · opcional",
        "Transcripción para ajustar planos al audio. Requiere cuenta en plan gratuito.",
        "https://console.groq.com/keys",
      ],
    ]
      .map(
        ([name, title, description, url]) =>
          `<div class="panel"><div class="row spread"><h3>${title}</h3><span class="tag ${c.keys[name] ? "done" : ""}">${c.keys[name] ? "Conectado" : "Sin clave"}</span></div><p class="hint">${description}</p><form class="key-form" data-name="${name}">${field("key", "Clave de tu cuenta", "", "password", 'autocomplete="off" required')}${check("remember", "Recordar de forma segura", c.backend !== "memory")}<div class="row"><button type="submit">Guardar conexión</button><button type="button" class="small ghost" data-forget="${name}">Olvidar</button></div></form><p class="hint"><a href="${url}" target="_blank" rel="noopener noreferrer">Crear mi propia clave ↗</a></p>${name === "groq" ? check("groqfree", "Confirmo que uso la cuenta gratuita sin facturación", c.groq_free_confirmed) : ""}</div>`,
      )
      .join(
        "",
      )}</div><div class="panel"><h3>Imágenes y voz sin clave</h3><p class="hint">SDXL y Riva usan los endpoints anónimos de OVHcloud. El acceso puede tener cuotas o dejar de estar disponible. El sistema no añade una cuenta de pago como alternativa.</p><div class="row"><span class="tag">SDXL · texto → imagen</span><span class="tag">Riva · texto → voz</span><span class="tag">Importación de recursos propios</span></div></div><details><summary>Conector de personajes e imágenes con referencias</summary><div class="notice amber">No hay una ruta gratuita de animación verificada incluida. Puedes importar clips o conectar un servicio que cumpla el contrato de medios descrito en la documentación. Confirmar estas opciones no convierte una API de pago en gratuita.</div><form id="bridge-form">${field("url", "URL base del conector", c.bridge.url || "", "url")}${field("model", "Modelo", c.bridge.model || "")}<div class="grid2">${field("evidence_url", "Documentación de acceso gratuito", c.bridge.evidence_url || "", "url")}${field("valid_until", "Verificación vigente hasta (ISO con zona horaria)", c.bridge.valid_until || "", "", 'placeholder="2026-11-05T00:00:00Z"')}</div>${check("zero_cost_confirmed", "Verifiqué acceso gratuito y desactivé cualquier alternativa de pago", c.bridge.zero_cost_confirmed)}<div class="row">${["image", "video", "reference", "lipsync"].map((k) => check("cap_" + k, { image: "Imágenes", video: "Video", reference: "Referencias", lipsync: "Sincronización labial" }[k], c.bridge.capabilities?.includes(k))).join("")}</div><button type="submit">Guardar conector</button></form><form class="key-form" data-name="bridge">${field("key", "Clave del conector (si la requiere)", "", "password", 'autocomplete="off"')}${check("remember", "Recordar de forma segura", c.backend !== "memory")}<button>Guardar clave</button></form></details><details><summary>OmniRoute · opcional</summary><p class="hint">Requiere instalación aparte. Usa una ruta concreta con precio cero y sin fallback de pago; el sistema no puede auditar la facturación interna de tu pasarela.</p><form id="gateway-form">${field("url", "URL compatible con OpenAI", c.omniroute.url || "http://127.0.0.1:20128/v1")}${field("model", "Ruta / modelo concreto", c.omniroute.model || "")}<div class="grid2">${field("evidence_url", "Evidencia de precio cero", c.omniroute.evidence_url || "")}${field("valid_until", "Vigente hasta (ISO)", c.omniroute.valid_until || "")}</div>${check("zero_cost_confirmed", "Verifiqué entrada y salida gratuitas, sin alternativas de pago", c.omniroute.zero_cost_confirmed)}<button type="submit">Guardar ruta</button></form><form class="key-form" data-name="omniroute">${field("key", "Clave de la pasarela", "", "password", 'autocomplete="off"')}${check("remember", "Recordar de forma segura", c.backend !== "memory")}<button>Guardar clave</button></form></details><details><summary>Cuentas para publicación automática</summary><p class="hint">Registra tu aplicación en cada plataforma y obtén un token con los permisos de publicación correspondientes. Los tokens pueden vencer. TikTok puede restringir visibilidad hasta auditar tu aplicación; Meta requiere página y permisos. Este formulario no sustituye ese proceso.</p><form id="account-form"><div class="grid2">${select(
      "platform",
      "Plataforma",
      [
        ["youtube", "YouTube"],
        ["facebook", "Facebook"],
        ["tiktok", "TikTok"],
      ],
      "youtube",
    )}${field("name", "Nombre de conexión", "default", "text", 'pattern="[a-zA-Z0-9_-]{1,80}" required')}</div><div class="grid2">${field("page_id", "ID de página (Facebook)")}${field("api_version", "Versión Graph (Facebook)", "", "text", 'placeholder="Versión vigente de tu aplicación"')}</div>${field("key", "Token de acceso de tu cuenta", "", "password", 'autocomplete="off" required')}${check("remember", "Recordar de forma segura", c.backend !== "memory")}${check("permissions_confirmed", "Confirmo permisos, cuenta de destino y elegibilidad de mi aplicación", false)}<button type="submit">Guardar cuenta</button></form>${c.accounts.map((a) => `<p class="hint">${E(a.platform)} · ${E(a.name)} · ${c.keys[a.platform + "." + a.name] ? "Token cargado" : "Falta token"} <button class="small ghost" data-forget="${E(a.platform + "." + a.name)}">Olvidar token</button></p>`).join("")}</details>`;
}
function projectSettings() {
  const p = project;
  modal(
    "Ajustes del proyecto",
    "Cambiar guion invalida la planificación. Cambiar contenido reinicia la revisión.",
    `<form id="settings-form">${field("title", "Título", p.title, "text", "required")}${area("script", "Guion", p.script, 'rows="8"')}${field("topic", "Tema", p.topic)}<div class="grid2">${select(
      "planner",
      "Planificador",
      [
        ["manual", "Manual"],
        ["openrouter", "OpenRouter gratuito"],
        ["omniroute", "OmniRoute"],
      ],
      p.planner,
    )}${select("mode", "Modo", Object.entries(modes), p.mode)}</div><div class="grid2">${select(
      "audio_source",
      "Narración",
      [
        ["upload", "Audio propio"],
        ["riva", "Riva gratuito"],
      ],
      p.audio_source,
    )}${select(
      "image_source",
      "Visuales",
      [
        ["upload", "Recursos propios"],
        ["sdxl", "SDXL gratuito"],
        ["bridge", "Conector de medios"],
      ],
      p.image_source,
    )}</div><div class="grid3">${select(
      "aspect",
      "Encuadre",
      [
        ["9:16", "9:16"],
        ["16:9", "16:9"],
        ["1:1", "1:1"],
      ],
      p.aspect,
    )}${select(
      "resolution",
      "Resolución",
      [
        ["720", "720p"],
        ["1080", "1080p"],
      ],
      p.resolution,
    )}${field("music_gain", "Volumen de fondo", p.music_gain, "number", 'min="0" max="0.3" step="0.01"')}</div>${check("subtitles", "Incluir subtítulos", p.subtitles)}${check("burn_subtitles", "Incrustar subtítulos en el video", p.burn_subtitles)}${actions("Guardar ajustes")}</form>`,
  );
}
function beginUpload(role, sceneId) {
  modal(
    "Cargar " +
      {
        narration: "narración",
        music: "música",
        reference: "referencia",
        scene: "imagen o clip",
      }[role],
    "Los archivos permanecen en tu equipo.",
    `<form id="upload-form" data-role="${E(role)}" data-scene="${E(sceneId || "")}"><label>Archivo<input name="file" type="file" required accept="${role === "reference" ? "image/*" : role === "scene" ? "image/*,video/*" : "audio/*,video/mp4"}"></label>${select(
      "rights",
      "Derechos de uso",
      [
        ["unknown", "Pendientes de confirmar"],
        ["own", "Es un recurso propio"],
        ["licensed", "Tengo permiso o licencia"],
        ["cc0", "Dominio público / CC0"],
      ],
      "unknown",
    )}${field("source", "Origen / licencia / autor", "Recurso propio o autorizado")}<p class="hint">No elijas una licencia si no la has comprobado. Los derechos pendientes bloquearán la exportación.</p>${actions("Cargar archivo")}</form>`,
  );
}
async function reloadProject() {
  if (project) {
    project = await api("/api/projects/" + project.id);
    editorDirty = false;
    renderEditor();
  }
}
async function handleAction(el) {
  if (
    editorDirty &&
    (el.dataset.view || el.dataset.tab || el.dataset.job || el.dataset.open)
  ) {
    toast(
      "Guarda el formulario antes de continuar; tus selecciones siguen aquí.",
      true,
    );
    return;
  }
  if (el.dataset.view) {
    view = el.dataset.view;
    render();
    return;
  }
  if (el.dataset.open) {
    await openProject(el.dataset.open);
    return;
  }
  if (el.dataset.filter) {
    filter = el.dataset.filter;
    renderProjects();
    return;
  }
  if (el.dataset.tab) {
    tab = el.dataset.tab;
    renderEditor();
    return;
  }
  if (el.dataset.scene) {
    sceneModal(el.dataset.scene);
    return;
  }
  if (el.dataset.page) {
    page = Number(el.dataset.page);
    renderScenes();
    return;
  }
  if (el.dataset.job) {
    await api(`/api/projects/${project.id}/jobs/${el.dataset.job}`, "POST");
    toast("Trabajo guardado en la cola.");
    await reloadProject();
    return;
  }
  if (el.dataset.cancel) {
    await api("/api/jobs/" + el.dataset.cancel + "/cancel", "POST");
    await refreshState(false);
    if (view === "editor") await reloadProject();
    else render();
    return;
  }
  if (el.dataset.upload) {
    close();
    beginUpload(el.dataset.upload, el.dataset.sceneUpload);
    return;
  }
  if (el.dataset.channel) {
    channelModal(el.dataset.channel);
    return;
  }
  if (el.dataset.forget) {
    await api("/api/connections/key", "POST", {
      name: el.dataset.forget,
      delete: true,
    });
    toast("Clave eliminada del estudio.");
    await renderConnections();
    return;
  }
  if (el.dataset.ideas) {
    toast("Preparando ideas con OpenRouter gratuito…");
    const data = await api("/api/ideas", "POST", {
      channel_id: el.dataset.ideas,
    });
    modal(
      "Ideas para tu canal",
      "Propuestas para revisar; no son tendencias verificadas.",
      `<div>${(data.ideas || []).map((i) => `<div class="panel"><h3>${E(i.title)}</h3><p>${E(i.angle)}</p><span class="tag">${E(i.content_type)}</span></div>`).join("")}</div>`,
    );
    return;
  }
  if (el.dataset.events) {
    const events = await api("/api/jobs/" + el.dataset.events + "/events");
    modal(
      "Registro del trabajo",
      "Últimos 100 eventos.",
      events
        .map(
          (e) =>
            `<p class="hint">${new Date(e.at * 1000).toLocaleTimeString()} · ${E(e.message)}</p>`,
        )
        .join("") || "<p>Sin eventos.</p>",
    );
    return;
  }
  if (el.dataset.refreshPublication) {
    await api(
      "/api/publications/" + el.dataset.refreshPublication + "/refresh",
      "POST",
    );
    await reloadProject();
    return;
  }
  switch (el.dataset.action) {
    case "close":
      close();
      break;
    case "new-project":
      newProject();
      break;
    case "example": {
      const p = await api("/api/example", "POST");
      await refreshState(false);
      await openProject(p.id);
      toast("Ejemplo en cola. Al terminar, revisa sus recursos y exporta.");
      break;
    }
    case "new-channel":
      channelModal();
      break;
    case "project-settings":
      projectSettings();
      break;
    case "bible":
      modal(
        "Guía de continuidad",
        "Describe identidades, vestuario, escenarios y estilo persistentes.",
        `<form id="bible-form">${area("visual_bible", "Guía visual", project.visual_bible, 'rows="10"')}${actions("Guardar guía")}</form>`,
      );
      break;
    case "sources":
      modal(
        "Fuentes del contenido",
        "Una fuente por línea: título | URL | afirmación respaldada.",
        `<form id="sources-form">${area("sources", "Fuentes", project.sources.map((s) => [s.title, s.url, s.claim || ""].join(" | ")).join("\n"), 'rows="9"')}${actions("Guardar fuentes")}</form>`,
      );
      break;
    case "adapt":
      modal(
        "Reel a partir de este video",
        "Reutiliza recursos y revisa después su estructura.",
        `<form id="adapt-form"><div class="grid2">${field("start", "Desde el segundo", 0, "number", 'min="0" step="0.1" required')}${field("end", "Hasta el segundo", 120, "number", 'min="90" step="0.1" required')}</div>${actions("Crear adaptación")}</form>`,
      );
      break;
  }
}
document.addEventListener("click", async (e) => {
  const el = e.target.closest("button,[data-open]");
  if (!el || (el.type === "submit" && el.form) || el.disabled) return;
  try {
    await handleAction(el);
  } catch (error) {
    toast(error.message, true);
  }
});
document.addEventListener("change", async (e) => {
  if (e.target.name === "format" && $("#project-form")) {
    const f = $("#project-form"),
      v = e.target.value;
    f.elements.duration.value = { pilot: 15, reel: 120, long: 300 }[v];
    f.elements.aspect.value = v === "long" ? "16:9" : "9:16";
  }
  if (e.target.name === "groqfree")
    try {
      await api("/api/connections/groq", "PUT", {
        free_plan: e.target.checked,
      });
    } catch (err) {
      toast(err.message, true);
    }
});
document.addEventListener("input", (e) => {
  if (e.target.closest("#editor-body form")) editorDirty = true;
});
document.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target,
    fd = new FormData(f),
    v = Object.fromEntries(fd),
    button =
      f.querySelector("[type=submit]") ||
      f.querySelector("button:not([type=button])");
  if (button) button.disabled = true;
  try {
    if (f.id === "project-form") {
      v.duration = Number(v.duration);
      v.subtitles = fd.has("subtitles");
      const p = await api("/api/projects", "POST", v);
      close();
      await refreshState(false);
      await openProject(p.id);
      toast("Proyecto creado. Prepara el guion o carga tu audio.");
    } else if (f.id === "channel-form") {
      v.character_voices = JSON.parse(v.character_voices || "{}");
      await api(
        "/api/channels" + (f.dataset.id ? "/" + f.dataset.id : ""),
        f.dataset.id ? "PUT" : "POST",
        v,
      );
      close();
      await refreshState();
      toast("Perfil guardado.");
    } else if (f.id === "settings-form") {
      v.music_gain = Number(v.music_gain);
      v.subtitles = fd.has("subtitles");
      v.burn_subtitles = fd.has("burn_subtitles");
      await api("/api/projects/" + project.id, "PUT", {
        revision: project.revision,
        project: v,
      });
      close();
      await reloadProject();
    } else if (f.id === "scene-form") {
      const scenes = structuredClone(project.scenes),
        s = scenes.find((s) => s.id === f.dataset.id);
      Object.assign(s, {
        text: v.text,
        prompt: v.prompt,
        kind: v.kind,
        start: Number(v.start),
        end: Number(v.end),
        speaker: v.speaker,
        motion: v.motion,
        transition: v.transition,
        identity_reviewed: fd.has("identity_reviewed"),
        lipsync_reviewed: fd.has("lipsync_reviewed"),
        locked: true,
        reference_ids: [...fd.keys()]
          .filter((k) => k.startsWith("ref_"))
          .map((k) => k.slice(4)),
        effects: v.effect
          ? [{ type: v.effect, offset: Number(v.offset), gain: Number(v.gain) }]
          : [],
      });
      if (fd.has("regenerate")) {
        s.visual_asset = null;
        s.identity_reviewed = false;
        s.lipsync_reviewed = false;
      }
      await api("/api/projects/" + project.id + "/scenes", "PUT", {
        revision: project.revision,
        scenes,
      });
      close();
      await reloadProject();
      toast("Plano guardado. Revisa de nuevo el proyecto antes de exportar.");
    } else if (f.id === "review-form") {
      await api("/api/projects/" + project.id + "/review", "PUT", {
        revision: project.revision,
        review: Object.fromEntries(
          [
            "editorial",
            "rights",
            "timing",
            "continuity",
            "playback",
            "factual",
          ].map((k) => [k, fd.has(k)]),
        ),
      });
      await reloadProject();
      toast("Revisión guardada.");
    } else if (f.id === "bible-form" || f.id === "sources-form") {
      const changes =
        f.id === "bible-form"
          ? v
          : {
              sources: v.sources
                .split("\n")
                .filter((s) => s.trim())
                .map((row) => {
                  const [title, url, ...claim] = row
                    .split("|")
                    .map((s) => s.trim());
                  return { title, url, claim: claim.join("|") };
                }),
            };
      await api("/api/projects/" + project.id, "PUT", {
        revision: project.revision,
        project: changes,
      });
      close();
      await reloadProject();
    } else if (f.id === "upload-form") {
      const form = new FormData();
      form.set("file", fd.get("file"));
      const params = new URLSearchParams({
        role: f.dataset.role,
        rights: v.rights,
        source: v.source,
      });
      if (f.dataset.scene) params.set("scene_id", f.dataset.scene);
      toast("Cargando y comprobando archivo…");
      await api(
        "/api/projects/" + project.id + "/assets?" + params,
        "POST",
        form,
      );
      close();
      await reloadProject();
      toast("Recurso guardado.");
    } else if (f.classList.contains("key-form")) {
      await api("/api/connections/key", "POST", {
        name: f.dataset.name,
        key: v.key,
        remember: fd.has("remember"),
      });
      f.reset();
      toast("Conexión guardada.");
      await renderConnections();
    } else if (f.id === "bridge-form") {
      v.zero_cost_confirmed = fd.has("zero_cost_confirmed");
      v.capabilities = ["image", "video", "reference", "lipsync"].filter((k) =>
        fd.has("cap_" + k),
      );
      await api("/api/connections/bridge", "PUT", v);
      toast("Conector guardado. Aún requiere una prueba real.");
    } else if (f.id === "gateway-form") {
      v.zero_cost_confirmed = fd.has("zero_cost_confirmed");
      v.price_per_input_token = v.zero_cost_confirmed ? 0 : null;
      v.price_per_output_token = v.zero_cost_confirmed ? 0 : null;
      await api("/api/connections/omniroute", "PUT", v);
      toast(
        "Ruta guardada. Su facturación depende de la configuración de OmniRoute.",
      );
    } else if (f.id === "account-form") {
      await api("/api/accounts", "PUT", {
        platform: v.platform,
        name: v.name,
        page_id: v.page_id,
        api_version: v.api_version,
        permissions_confirmed: fd.has("permissions_confirmed"),
      });
      await api("/api/connections/key", "POST", {
        name: v.platform + "." + v.name,
        key: v.key,
        remember: fd.has("remember"),
      });
      f.reset();
      toast("Cuenta guardada.");
      await renderConnections();
    } else if (f.id === "publish-form") {
      v.when = v.when ? new Date(v.when).toISOString() : null;
      for (const k of ["made_for_kids", "ai_generated", "authorize"])
        v[k] = fd.has(k);
      await api("/api/projects/" + project.id + "/publish", "POST", v);
      await reloadProject();
      toast("Publicación autorizada y guardada en cola.");
    } else if (f.id === "adapt-form") {
      const p = await api("/api/projects/" + project.id + "/adapt", "POST", {
        start: Number(v.start),
        end: Number(v.end),
      });
      close();
      await refreshState(false);
      await openProject(p.id);
      toast(
        "Adaptación creada. Revisa el contexto y cierre antes de exportar.",
      );
    }
  } catch (error) {
    toast(error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
});
$("#modal").addEventListener("click", (e) => {
  if (e.target === $("#modal")) close();
});
setInterval(async () => {
  if (pollBusy || document.hidden) return;
  pollBusy = true;
  try {
    await refreshState(false);
    if (!$("#modal").open) {
      if (view === "queue" || view === "projects") render();
      else if (view === "editor" && project && !editorDirty) {
        const fresh = await api("/api/projects/" + project.id);
        const changed =
          JSON.stringify([
            fresh.revision,
            fresh.state,
            fresh.jobs,
            fresh.output_asset,
          ]) !==
          JSON.stringify([
            project.revision,
            project.state,
            project.jobs,
            project.output_asset,
          ]);
        if (changed && !editorDirty && !$("#modal").open) {
          project = fresh;
          renderEditor();
        }
      }
    }
  } catch {
  } finally {
    pollBusy = false;
  }
}, 3500);
refreshState().catch((e) => toast(e.message, true));
