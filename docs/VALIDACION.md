# Validación de v0.1

Fecha del trabajo: 29 de octubre de 2026, zona America/Managua. Entorno de ejecución: Linux, Python 3.12, FFmpeg 6.1.1 y alternativa portable Linux 7.0.2. No se está ejecutando en el portátil Windows del usuario.

## Pruebas automáticas

`python -m pytest -q`: **44 casos**, que cubren:

- Límites de reels/largos/pruebas, máximo de 15 min en la planificación.
- Transacciones de cola, reclamo simultáneo, recuperación y exclusión de instancias.
- Espera persistente por cuota, Retry-After y ausencia de nuevas llamadas antes de tiempo.
- Bloqueo de precio positivo/desconocido y verificaciones vencidas en rutas configurables.
- Ausencia de almacenamiento de claves en texto plano, redacción y eliminación.
- Protección de sesión, origen/host, pertenencia de recursos e importaciones inválidas.
- Revisión obsoleta, cambios de escenas, edición sin pérdida de asignaciones y derechos pendientes.
- Contratos de SDXL, Riva y caché; uso del encabezado real de WAV.
- Puente de personajes con referencia y audio: validación de payload, video devuelto y reutilización.
- Bloqueo de personajes sin conector y rechazo de imágenes como sustituto de un clip.
- Exportación real 720 × 1280 con zoom, fundido, música, ducking, efecto, subtítulos, pistas y duración verificadas.
- Decodificación completa del MP4, portada y paquete de materiales.
- Reutilización de planos renderizados y subtítulos temporizados por palabras.
- Rutas con espacios, acentos y apóstrofos usando FFmpeg portable sin ffprobe.
- Adaptación con recorte del audio, reutilización de recursos, offsets de clips y efectos.
- Publicación simulada de YouTube, Facebook Reels y TikTok, IDs confirmados, revisión posterior a programación, duplicados y respuesta perdida.

La versión de FastAPI/Starlette del entorno emite una advertencia de deprecación sobre el transporte de TestClient/httpx; no produjo fallos. Debe revisarse al actualizar dependencias.

## Navegador real

`tests/browser_smoke.cjs`, Playwright y Chromium headless:

Crear proyecto → preparar → cargar narración → editar plano → importar imagen → revisar → exportar → acceder a descarga → abrir conexiones → tamaño móvil de 390 px.

Resultado: flujo completado, sin errores de JavaScript y sin desbordamiento horizontal móvil. Incluye una espera durante la edición para comprobar que el sondeo de la cola no borre selecciones sin guardar. El navegador se usa solo contra nuestra aplicación local. Los archivos de prueba eran imagen y tono sintéticos; esa prueba comprueba funcionamiento, no calidad narrativa ni voces humanas.

## Conexión real anónima

`scripts/smoke_live.py`, sin claves ni cuenta:

- Riva devolvió voz española para un breve relato ficticio de una isla.
- SDXL devolvió la imagen de una costa con bote al amanecer.
- La aplicación montó MP4 vertical **720 × 1280, 7,625 segundos**, con subtítulos y decodificación completa correcta.
- Se inspeccionó un fotograma y se corrigió la escala y margen de los subtítulos.
- El script marca el contenido como prueba y no aprueba reproducción ni publica en ninguna plataforma.

El entorno necesita su proxy/certificado administrado; se añadió soporte de proxy SOCKS de httpx, sin desactivar la verificación TLS. No se interpreta la configuración de red del entorno como requisito para la computadora del usuario.

## No validado todavía

| Área | Límite de la evidencia |
|---|---|
| Windows / hardware | BAT, DPAPI, consumo de RAM/CPU y exportación en el i3/8 GB pendientes |
| OpenRouter y OmniRoute | Contratos y bloqueos probados; no se usaron las claves del usuario para una generación real |
| Groq | Validación y alineación implementadas; conexión real con cuenta del usuario pendiente |
| Personajes | No se validó un proveedor gratuito de actuación, identidad y labios con un resultado real |
| Publicación | Simulación HTTP; no hubo subidas reales ni aprobación de apps |
| Duraciones completas | No se completó un piloto real de reel 90–150 s, largo 5–15 min o lote semanal |
| Editorial y derechos | Las comprobaciones automáticas no prueban veracidad, permisos ni calidad artística |
| Sonoridad | Objetivo de normalización, no medición final en dos pasadas ni certificación |

Las pruebas no deben describirse como certificación de los requisitos P01–P13 completos de la especificación. Los pilotos reales y las cuentas pendientes aparecen en ROADMAP.md.

## Fuentes técnicas consultadas

- [SDXL, OVHcloud](https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/stable-diffusion-xl/)
- [Riva español, OVHcloud](https://www.ovhcloud.com/en-gb/public-cloud/ai-endpoints/catalog/nvr-tts-es-es/)
- [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router)
- [Groq Speech to Text](https://console.groq.com/docs/speech-to-text)
- [YouTube resumable uploads](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol)
- [TikTok Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post)
- [Ejemplo oficial de Facebook Reels](https://github.com/fbsamples/Facebook-Reels-Publishing-API-Postman-Collection)

Las condiciones del proveedor pueden cambiar. Revisarlas al habilitar producción.
