# Contrato de medios v1

Este contrato permite integrar un proveedor de imágenes con referencias o de personajes con animación y sincronización labial, sin acoplar la cola a una API concreta. **No se incluye un servicio remoto que implemente el contrato**, ni un proveedor gratuito de animación validado visualmente. Puedes importar clips hasta contar con uno.

La URL base se configura expresamente. Solo HTTPS o HTTP de loopback. No se siguen redirecciones. Las credenciales, si existen, se envían como Bearer desde Vault. Requiere evidencia de acceso gratuito, una fecha futura con zona horaria y las capacidades declaradas.

## Petición

`POST {base}/generate`, JSON:

```json
{
  "version": 1,
  "model": "modelo-concreto",
  "task": "character",
  "prompt": "Un plano, acción, expresión e iluminación",
  "visual_bible": "Identidades y lugares persistentes",
  "speaker": "Clara",
  "duration": 7.5,
  "aspect": "9:16",
  "references": [{"mime": "image/png", "b64_json": "BASE64_DEL_ARCHIVO"}],
  "audio_b64": "WAV_MONO_24000_HZ_BASE64",
  "budget": {"maximum_cost": 0, "paid_fallback": false}
}
```

`task=image` devuelve una imagen. `task=character` exige video, referencias y lipsync. El audio contiene exactamente la parte de la narración correspondiente a la escena. Los clips se montan sin su audio original; la mezcla final usa la narración del proyecto para evitar voces duplicadas.

## Respuesta

```json
{"cost": 0, "kind": "video", "b64_json": "MP4_BASE64"}
```

La imagen usa `kind=image`. No se aceptan URLs generadas por el modelo. La respuesta de video debe contener una pista visual con duración suficiente; no se transforma en una imagen estática. La revisión humana de identidad y sincronización sigue siendo necesaria: el servidor puede devolver un video incorrecto aunque cumpla el contrato.

429 y Retry-After sirven para esperar. 503/502/504 se tratan como indisponibilidad temporal. Precio declarado distinto de cero, respuestas de pago o capacidades insuficientes bloquean el trabajo. Verificar el coste devuelto ocurre después de la solicitud; por eso debe comprobarse previamente el contrato y la configuración del proveedor. No se promete impedir un cargo de un servidor que incumpla su propio contrato.

Para APIs asíncronas, implementa en tu puente el inicio y sondeo, devolviendo 429 mientras no haya resultado reutilizable. Debe deduplicar internamente por el contenido para que una reanudación no cree generaciones duplicadas. El cliente conserva caché de respuestas completas; no garantiza idempotencia dentro de un servicio externo antes de recibir su resultado.
