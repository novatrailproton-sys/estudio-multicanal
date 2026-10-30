# Estudio Multicanal

Aplicación local en español para producir reels y videos largos de distintas temáticas. Organiza canales, guiones, voces, escenas, referencias y publicaciones. Genera recursos mediante APIs y monta el video en tu computadora.

**Versión 0.1: primera versión funcional para pruebas.** El modo narrado ya exportó un video con voz e imagen generadas en servicios reales gratuitos. El módulo de personajes acepta clips e integra un contrato de generación con referencias y audio; no incluye una API gratuita de animación que haya superado una prueba visual de identidad y labios. Las publicaciones tienen conectores oficiales y pruebas simuladas; necesitan cuentas autorizadas y validación real. No se promete producción ilimitada, viralidad ni la media semanal antes de medirla.

## Empezar en Windows

1. Instala **Python 3.11 o posterior** desde [python.org](https://www.python.org/downloads/). Marca **Add Python to PATH**.
2. Descomprime el proyecto en una carpeta normal y abre **INICIAR.bat**. La primera vez instala dependencias y necesita Internet. Mantén abierta la ventana de inicio.
3. Se abrirá `http://127.0.0.1:57321` en el navegador. Es una aplicación en tu computadora.
4. Pulsa **Probar ejemplo sin claves**. Generará una voz y una imagen mediante los endpoints anónimos de Riva y SDXL. Si hay cuota agotada, el trabajo esperará.
5. Cuando los recursos estén listos, abre **Revisión**, escucha el audio, mira la imagen y confirma lo revisado. Después pulsa **Exportar video**.
6. Reproduce el resultado y descarga el MP4, la portada o el paquete de materiales.

Para tus propios videos: **Nuevo proyecto → canal, guion y modo → preparar → cargar o generar recursos → revisar → exportar**. La sección Conexiones solo hace falta para las funciones que quieras usar. Un proyecto manual con archivos propios no necesita claves.

El FFmpeg incluido por `imageio-ffmpeg` sirve como alternativa cuando no hay FFmpeg en PATH; los subtítulos requieren libass. Se probaron el FFmpeg de sistema y el binario portable de Linux. El instalador BAT, DPAPI y el binario de Windows todavía necesitan probarse en el equipo del usuario.

## Lo que incluye

| Función | Comportamiento |
|---|---|
| Canales | Tema, público, reglas, estilo, idioma, narrador y asignación de voces a personajes |
| Proyectos | Tema, guion, fuentes, audio, narrativa visual, personajes o mezcla |
| Formatos | Reel 90–150 s; largo 5–15 min; prueba corta 5–30 s; vertical, horizontal y cuadrado |
| Guion e ideas | Entrada manual o generación JSON con OpenRouter gratuito; historial de títulos para propuestas |
| Dirección | Escenas por unidades de sentido, planificación en bloques de 8 y guía visual persistente |
| Editor | Tiempos, texto, prompt, tipo, voz, referencias, movimiento, transición y efectos por escena |
| Audio | Importación o Riva, voces estables por nombre de personaje, música propia y ducking |
| Sincronización | Duración real; tiempos estimados señalados; alineación por palabras opcional con Groq |
| Imágenes | Importación o SDXL; SDXL de texto no acepta imágenes de referencia |
| Personajes | Clips reales importados o conector de medios con audio y referencias; revisión de identidad y labios |
| Sonido | Efectos originales sintetizados: golpes, teléfono, impacto, barrido y campanilla; música importada |
| Montaje | Zoom suave en imágenes, clips, cortes/fundidos, mezcla, subtítulos ASS/SRT y portada |
| Adaptaciones | Fragmentos de 90–150 s con audio recortado y reutilización de recursos; revisión editorial obligatoria |
| Entrega | MP4, portada, SRT, JSON, CSV de línea de tiempo, fuentes, procedencia y recursos; sin proyecto nativo CapCut |
| Operación | SQLite, cola persistente, cuotas, caché, reanudación, cancelación y una producción a la vez |
| Publicación | APIs de YouTube, páginas de Facebook y TikTok; programación local, consentimiento y estados separados |
| Privacidad | Claves en memoria o almacén seguro del sistema; no se devuelven al navegador ni entran en paquetes |

Las duraciones elegidas son objetivos. La voz generada puede durar más o menos. Si la narración definitiva queda fuera del rango del formato, la exportación se bloquea para que ajustes el contenido; no se acelera ni se recorta sin avisarte.

## Conexiones

- **SDXL/Riva:** acceso anónimo a endpoints concretos de OVHcloud. Separación de 31 s entre solicitudes al mismo modelo. Sin cuentas de pago ni fallback automático. Disponibilidad sujeta al proveedor.
- **OpenRouter:** clave propia; modelo fijo `openrouter/free`. Crea una clave en [OpenRouter](https://openrouter.ai/keys), introdúcela en Conexiones y elige IA en el proyecto. No se incluyen claves compartidas.
- **Groq:** opcional para transcribir. Necesita clave propia y confirmación de cuenta Free sin facturación. Se envía FLAC mono 16 kHz, máximo configurado 24 MB.
- **OmniRoute:** instalación opcional aparte; ruta concreta, precios declarados de entrada y salida cero, evidencia y fecha vigente. Debes desactivar allí los fallbacks de pago. El estudio no puede auditar la facturación interna de una pasarela ajena.
- **Conector de medios:** contrato documentado en [docs/MEDIA_BRIDGE.md](docs/MEDIA_BRIDGE.md). Conecta un servicio bajo tu control o autorizado que realmente ofrezca referencias, animación y sincronización. No es una API gratuita incluida.
- **Publicación:** consulta [docs/PUBLICACION.md](docs/PUBLICACION.md). Requiere configurar aplicaciones, permisos y tokens de tus cuentas. Los conectores no eluden las auditorías ni autorizaciones de las plataformas.

Las claves recordadas usan DPAPI en Windows, Secret Service en Linux o Keychain en macOS si están disponibles. Sin almacén seguro, el programa exige usar memoria de sesión. No guarda claves en JSON ni en el repositorio. Los tokens de publicación no se renuevan automáticamente en esta versión.

## Referencias y personajes

Sube imágenes en **Guion y referencias** o desde una escena. Selecciónalas dentro del plano: aparecen con `@nombre`. La vinculación real usa el ID del archivo; escribir `@` dentro del prompt no adjunta una imagen por sí solo.

Define nombres, rostro, edad, vestuario, voces y lugares en la guía visual. Revisa las escenas de personajes una por una. El modo de personajes nunca se convierte silenciosamente en una imagen con zoom. Si no hay conector válido o clip suficiente, el proyecto queda pendiente con el motivo.

## Datos, cierre y recuperación

Los proyectos se guardan por defecto en `EstudioMulticanal`, dentro de tu carpeta de usuario. Contiene base de datos, archivos, caché, exportaciones y credenciales protegidas. El código fuente está separado.

- Cierra el programa antes de copiar esa carpeta como respaldo.
- No subas esa carpeta a GitHub. Contiene tus materiales y configuración personal.
- DPAPI vincula las credenciales a tu usuario de Windows; al migrar de equipo vuelve a conectarlas.
- Al cerrar, los trabajos locales se conservan y reanudan al abrir. Una publicación con resultado incierto requiere comprobarse antes de repetirla.
- La programación funciona con el estudio y el equipo encendidos. Un horario vencido se ejecuta al volver a abrir si sigue autorizado y la revisión no cambió.
- Los efectos y la música no sustituyen una revisión de mezcla. La normalización usa un objetivo de −16 LUFS, sin afirmar una medición final certificada.

## Desarrollo

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m estudio --no-browser
python -m pytest -q
```

En Windows activa `.venv\Scripts\activate`. Para reproducir versiones del entorno probado, instala antes `requirements-tested.txt`. Para cambiar carpeta o puerto:

```bash
python -m estudio --data ./data --port 57321
```

Prueba real anónima y opcional, independiente de tus proyectos:

```bash
python scripts/smoke_live.py --data ./test-output/live
```

Prueba de navegador opcional en Linux:

```bash
npm install --no-save playwright @sparticuz/chromium
node tests/browser_smoke.cjs
```

En entornos de contenedores pueden requerirse librerías de Chromium y ajustes de extracción propios del entorno; no forman parte de la aplicación del usuario. El navegador de pruebas no inicia sesiones en servicios externos.

Consulta [docs/VALIDACION.md](docs/VALIDACION.md) para evidencias y límites, [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para el diseño y [docs/ROADMAP.md](docs/ROADMAP.md) para pendientes.

## Repositorio GitHub

El proyecto viene listo para Git. Si estás instalando desde un ZIP, `CREAR_REPOSITORIO.bat` crea **un repositorio privado** con GitHub CLI, después de instalar Git, instalar [GitHub CLI](https://cli.github.com/) e iniciar sesión con `gh auth login`. No pongas tokens en scripts o en la conversación. Si el remoto ya existe, no lo reemplaza.

El origen está bajo MIT. Las dependencias, modelos y materiales tienen condiciones propias; MIT no cambia sus licencias ni concede acceso a servicios ajenos.
