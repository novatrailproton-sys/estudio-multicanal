# Publicación por API

El módulo utiliza APIs oficiales. No crea aplicaciones de desarrollador, no obtiene permisos por sí solo y no inicia sesión con contraseñas del usuario. Configura tu propia aplicación y un token de acceso autorizado en **Conexiones → Cuentas para publicación**. Cada plataforma tiene condiciones y cuotas propias.

Los conectores se probaron con HTTP simulado; **no se realizó ninguna subida real a las cuentas del usuario**. Son una integración inicial que debe validarse con contenido privado/de prueba y los permisos actuales. No se prometen elegibilidad, monetización ni publicación pública inmediata.

## Flujo

1. Exportar el video actual y completar la revisión de reproducción.
2. Conectar la cuenta, confirmar sus permisos y escoger su nombre.
3. Seleccionar plataforma, título, descripción y privacidad de forma expresa.
4. Autorizar ese contenido y, si quieres, fecha/hora local.
5. El backend guarda la revisión exacta, UTC y una clave única por proyecto/revisión/plataforma/cuenta.
6. El worker comprueba otra vez la revisión antes de contactar la plataforma.
7. Transferencia confirmada y publicación pública son estados diferentes. Usa **Comprobar en plataforma** para conocer el procesamiento.

El equipo debe estar encendido. Cerrar y reabrir no pierde la programación. Si una respuesta se pierde durante una subida, el estado queda **Resultado por comprobar**; no se reintenta automáticamente. Si existe un ID remoto, se puede consultar. Si no existe, comprueba tu cuenta directamente antes de cualquier nueva subida.

## YouTube

- Token OAuth de una aplicación del usuario con permisos de subida, no una API key de datos públicos.
- Inicio de sesión resumable, conservación protegida de su URL y transferencia binaria.
- Registro de ID confirmado y consulta de processingDetails/status.
- Privado, no listado o público según selección. Declaraciones de contenido para niños y material sintético en metadatos.
- No incluye renovación automática de tokens ni reanudación byte a byte del archivo tras una caída; se bloquea ante ambigüedad para revisar y evitar duplicados.

Referencias: [protocolo de subida](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol), [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert), [videos](https://developers.google.com/youtube/v3/docs/videos).

## Facebook

- Página administrada, token de página, ID de página y versión vigente de Graph API elegida por el usuario.
- Reels: inicio, transferencia a rupload.facebook.com y finalización PUBLISHED.
- Largos: transferencia al edge Videos de la página.
- Los límites de duración y formato del endpoint de Reels pueden diferir de la interfaz de Facebook. Un reel de 90–150 s no está garantizado por esta integración: hay que comprobar la versión, permisos y condiciones de la cuenta. No se recorta ni convierte silenciosamente.
- Este conector de página exige selección pública; no ofrece una privacidad individual ficticia.
- La consulta de estado ready confirma procesamiento, no garantiza por sí sola visibilidad pública.
- Revisa las declaraciones de contenido sintético y comercial en la plataforma: no se inventa un campo de Graph no confirmado para etiquetar IA.

Referencia primaria de ejemplo: [fbsamples/Facebook-Reels-Publishing-API-Postman-Collection](https://github.com/fbsamples/Facebook-Reels-Publishing-API-Postman-Collection). Debe contrastarse con la documentación de la versión vigente de Graph antes de habilitar producción.

## TikTok

- Aplicación registrada y permisos de Content Posting API. La auditoría puede ser necesaria para publicación pública.
- Consulta creator_info antes de iniciar: exige privacidad y duración permitidas para el creador.
- Inicio FILE_UPLOAD, transferencia por fragmentos y consulta por publish_id.
- is_aigc se envía según la elección de IA; duet/stitch quedan desactivados en esta primera integración.
- Las opciones de privacidad no se eligen automáticamente a partir de lo más público permitido.
- Las directrices y auditoría pueden limitar el uso como herramienta personal y sus automatizaciones; confirma elegibilidad antes de usar este conector. Tener código de subida no concede esa aprobación.

Referencias: [Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [guía de integración](https://developers.tiktok.com/doc/content-posting-api-get-started), [directrices](https://developers.tiktok.com/doc/content-sharing-guidelines).
