# Sistema de creación de videos para varios canales

Especificación funcional inicial · 29 de octubre de 2026

**Estado:** alcance acordado en la conversación; arquitectura e integraciones propuestas para validar. Este documento no implica que el nuevo sistema esté implementado ni que sus proveedores hayan superado pruebas de producción. Las aplicaciones de terror anteriores son prototipos y no cumplen por sí solas este alcance ampliado.

## 1. Objetivo

Crear reels y videos largos de distintas temáticas para YouTube, Facebook y TikTok, desde un tema, guion o narración, con producción automática y posibilidades de intervención manual. Cada proyecto debe conservar sus materiales, decisiones y estado para poder corregirse sin empezar de nuevo.

Principios acordados:

- Calidad mínima obligatoria antes de entregar o publicar.
- Presupuesto de servicios externos de cero por defecto. Un proveedor de pago exige habilitación expresa; nunca será una alternativa automática a una cuota agotada.
- Esperar cuando sea necesario para conservar calidad.
- Producción semanal flexible, ajustada a la capacidad real medida.
- Recuperación del trabajo, caché y correcciones por escena.
- Elegir publicación automática, programación o descarga manual por proyecto y plataforma.

## 2. Usuario, canales y entorno

Uso inicial personal del creador, con varios perfiles de canal y cuentas de destino. Una aplicación con usuarios, equipos y permisos compartidos no se incluye como requisito inicial.

Equipo conocido: Windows, Intel i3-8130U, 8 GB de RAM, gráficos Intel UHD 620. Propuesta: generación pesada mediante servicios externos y montaje local, con pocos trabajos simultáneos. El consumo y la velocidad deben medirse en ese equipo; no se promete un plazo de render.

Visual Studio Code servirá para desarrollar y mantener el proyecto. El usuario debe poder iniciar el sistema sin editar código ni mantener varias terminales manualmente.

Cada canal tendrá un perfil con temática, público, idioma, voces, estilo, referencias, reglas editoriales, formatos, publicación y proveedores habilitados. Se propone español como idioma inicial, configurable. Las reglas particulares —por ejemplo, referencias CEE y personajes Antonio/anciano— pertenecerán a su perfil y no a todos los canales.

## 3. Volumen y formatos

| Parámetro | Definición acordada |
|---|---|
| Reels | Referencia aproximada de 50 por semana; duración de 90 a 150 segundos |
| Largos | Referencia aproximada de 20 por semana; normalmente 5–10 minutos, máximo 15 |
| Reels independientes/adaptados | Mezcla configurable, sin porcentaje fijo acordado |
| Temas | Aportados por el usuario o propuestos por el sistema |
| Producción | Narración visual, personajes o combinación de ambos |
| Distribución entre canales | Configurable; las cifras sirven para dimensionar, no como cuota obligatoria por canal |
| Destinos | YouTube, Facebook y TikTok |

Se propone 9:16 para versiones verticales y 16:9 para versiones horizontales. Resolución, subtítulos, encuadre y duración serán presets actualizables por destino, comprobados contra las condiciones vigentes al conectar cada plataforma.

La carga publicada de referencia es de 175–325 minutos semanales, suponiendo 20 largos de 5–10 minutos y 50 reels de 1,5–2,5 minutos. Con todos los largos en el máximo sería de hasta 425 minutos. Publicación, generación nueva y reutilización se medirán por separado: una adaptación no debe contabilizarse como una regeneración completa obligatoria.

Una referencia de un recurso cada diez segundos equivale aproximadamente a 1.050–1.950 tramos visuales habituales. Es una estimación de planificación, no un número de llamadas API ni una obligación de hacer todos los planos con la misma duración.

## 4. Entradas y salidas

Entradas admitidas:

- Tema, enfoque y duración deseada.
- Guion propio o generado por el sistema.
- Audio existente o elección de síntesis.
- Referencias de personajes, lugares, estilo y recursos propios, cuando existan.
- Perfil de canal y destinos de publicación.

Cada proyecto debe entregar:

- MP4 final y variantes solicitadas, identificadas por plataforma.
- Guion, narración y diálogos separados cuando corresponda.
- Imágenes, clips, sonidos, mezclas y portadas.
- Línea de tiempo y lista de escenas con origen de los recursos.
- Fuentes y licencias, títulos y descripciones.
- Informe de calidad y limitaciones.
- Estado de cada publicación y su identificador confirmado, si se publicó.
- Material organizado para corregir en herramientas externas como CapCut. Un proyecto nativo de CapCut queda sujeto a validar un formato de intercambio; no se promete inicialmente.

## 5. Flujo y requisitos funcionales

| ID | Módulo | Comportamiento necesario | Prioridad |
|---|---|---|---|
| F01 | Perfiles de canal | Guardar identidad, reglas, recursos y cuentas de cada canal | Esencial |
| F02 | Ideas y calendario | Admitir temas manuales y propuestas automáticas; registrar historial para detectar repeticiones | Esencial |
| F03 | Investigación | Recopilar fuentes para afirmaciones factuales; distinguir información, opinión, ficción y adaptación | Esencial |
| F04 | Guion | Crear o importar contenido; ajustar estructura al público, formato y duración; conservar versiones | Esencial |
| F05 | Revisión editorial | Comprobar coherencia, cronología, repeticiones y correspondencia de afirmaciones con fuentes | Esencial |
| F06 | Voces | Usar audio propio o síntesis; separar narrador y personajes; revisar pronunciación y duración real | Esencial |
| F07 | Dirección y referencias | Crear guía visual, referencias persistentes y planificación de planos sin adelantar revelaciones | Esencial |
| F08 | Narración visual | Combinar imágenes y clips, movimientos y encuadres adecuados al relato | Esencial |
| F09 | Personajes | Generar actuación y diálogo sincronizado, con identidad y voz persistentes | Esencial, condicionado a prueba técnica |
| F10 | Modo mixto | Elegir el tipo de escena automáticamente y permitir cambiarlo manualmente | Esencial |
| F11 | Sincronización | Situar planos, acciones, diálogo y sonidos usando los tiempos del audio; señalar tiempos estimados | Esencial |
| F12 | Sonido | Seleccionar música y efectos adecuados al contenido y sus derechos; mantener inteligibilidad | Esencial |
| F13 | Montaje | Ensamblar recursos, transiciones, movimiento y subtítulos opcionales; corregir por escena | Esencial |
| F14 | Adaptaciones | Crear reels independientes o derivados de largos con apertura, contexto y cierre propios | Esencial |
| F15 | Presentación | Preparar portada, título y descripción fieles al contenido y adaptados al destino | Esencial |
| F16 | Calidad y exportación | Evaluar y decodificar el resultado; entregar versiones y materiales del proyecto | Esencial |
| F17 | Publicación | Descargar, subir o programar por destino autorizado, con seguimiento y prevención de duplicados | Esencial, condicionado a acceso de plataforma |
| F18 | Operación | Cola, cuotas, caché, reintentos limitados, recuperación y diagnóstico comprensible | Esencial |
| F19 | Conexiones | Configurar una vez, proteger credenciales, mostrar vencimientos y desconexiones | Esencial |
| F20 | Estadísticas | Incorporar métricas disponibles para comparar resultados y orientar futuras propuestas | Ampliación tras validar producción y publicación |

Orden de ejecución: seleccionar perfil y entrada → investigar si corresponde → preparar/revisar guion → generar o importar voces → medir y ajustar duración → obtener tiempos → planificar escenas y referencias → producir recursos → montar y mezclar → verificar → exportar → publicar según la configuración → registrar resultados.

La narración puede producirse por fragmentos para corregir frases y ajustar escenas, conservando una voz uniforme. El sistema debe validar los recursos definitivos contra el audio definitivo y no conservar tiempos de una versión anterior.

## 6. Modos visuales y reglas editoriales

**Narración visual:** voz en off, imágenes y clips, movimiento de cámara, música y efectos. Los planos deben acompañar lo narrado.

**Personajes:** fichas de identidad y vestuario, voces diferenciadas, acciones y expresiones temporizadas. La sincronización labial se exige cuando un personaje visible pronuncia diálogo. La modalidad puede ser ilustrada o realista según el perfil.

**Mixto:** alternar ambos tipos de escena de forma planificada. Una corrección manual debe persistir y no ser anulada por la próxima ejecución automática.

El módulo de personajes forma parte del alcance inicial. Su disponibilidad gratuita, calidad, consistencia y capacidad deben comprobarse pronto. Si no se encuentra una ruta que cumpla los criterios, ese modo quedará bloqueado con explicación y se revisará su viabilidad con el usuario; no se presentará una imagen estática como una animación lograda ni se convertirá el proyecto a otro modo sin la configuración correspondiente.

Los diez segundos por recurso serán una referencia. El director debe respetar unidades de sentido y permitir planos más cortos o largos. Los reels derivados deben poder entenderse sin haber visto el video largo; reutilizar audio o imágenes no sustituye la adaptación editorial.

Los hechos, citas e imágenes documentales conservarán procedencia. Los recursos ilustrativos y las reconstrucciones no se presentarán como prueba de hechos reales. La revisión automática debe señalar incertidumbre; no garantiza por sí sola verdad factual, derechos ni originalidad absoluta.

## 7. Arquitectura propuesta

| Componente | Responsabilidad | Propuesta inicial |
|---|---|---|
| Aplicación | Perfiles, proyectos, previsualización y correcciones | Interfaz local sencilla; ajustes técnicos en sección avanzada |
| Coordinador | Dependencias, estados y reglas de cada etapa | Servicio propio con trabajos persistentes |
| Base de datos | Proyectos, versiones, tareas, recursos y publicaciones | SQLite inicialmente; confirmar funcionamiento con reinicios |
| Conectores de IA | Capacidades, planes, cuotas, precios, autenticación y fallos | Adaptadores independientes; OmniRoute como candidato para agrupar rutas |
| Recursos | Archivo, caché, referencias, licencias y procedencia | Almacenamiento por proyecto y caché identificada por contenido |
| Producción | Audio, imágenes, animación y sincronización | Proveedores validados por capacidad, con alternativas compatibles |
| Montaje | Composición, mezcla y exportación | Python y FFmpeg como candidatos ya usados en los prototipos |
| Publicadores | Autorización, subida, programación y estado | APIs oficiales de cada plataforma, donde estén disponibles |
| Navegador | Pruebas de interfaz y tareas web compatibles | agent-browser como candidato auxiliar del producto, no dependencia universal |

Estos componentes son una propuesta, no una selección cerrada de todas las tecnologías. Se elegirá la menor cantidad de servicios que supere las pruebas, midiendo el consumo en el equipo del usuario. Inicialmente se propone una sola exportación y un solo navegador controlado simultáneos; la concurrencia de APIs se ajustará a sus cuotas.

El director puede coordinar funciones de investigación, escritura, visuales y calidad mediante tareas controladas. No se necesita asignar una cuenta o un agente autónomo distinto a cada función.

Estados previstos: borrador → en cola → preparando → generando → montando → verificando → listo. Estados adicionales: esperando cuota, necesita revisión, error recuperable, cancelado. Cada destino de publicación tendrá sus propios estados, incluido resultado desconocido para impedir reintentos que puedan duplicar una publicación ya realizada.

## 8. Revisión de los repositorios aportados

Revisión de documentación y metadatos mediante la integración de GitHub. No se instalaron ni se ejecutaron estos repositorios; no se ha auditado su implementación completa ni se han medido sus prestaciones.

### OmniRoute — candidato de prioridad alta

Repositorio: https://github.com/cheaper-inference/OmniRoute

Documenta una pasarela con interfaz compatible con OpenAI, múltiples proveedores, estrategias de selección, cuotas, recuperación y funciones de medios. Puede reducir el trabajo de conectar proveedores, especialmente para investigación, guiones, planificación y revisión. La documentación describe generación de imagen/video/audio, pero cada capacidad y proveedor requiere prueba separada.

La cabecera y la documentación de cuotas aclaran que se deben aportar cuentas y credenciales propias. Las cifras de tokens agregados son estimaciones de planes de terceros y elegibilidades separadas; no son un saldo concedido por OmniRoute. No se usarán para prometer nuestra capacidad semanal ni como equivalencia de minutos de voz, imágenes o animación.

La selección automática general puede incluir rutas con costos. Para este proyecto hace falta una lista explícita de proveedores/modelos permitidos y evidencia de precio cero o acceso gratuito vigente. Si no existe evidencia suficiente, no se ejecutará la ruta. Un costo marginal de cero sobre una suscripción ya pagada se registrará por separado de un servicio gratuito.

El modo headless documentado permite omitir el panel y algunos subsistemas; se evaluará para reducir carga. No se afirma cuánto RAM ahorra sin medirlo. La compresión de prompts se validará antes de usarla en guiones o continuidad, porque el ahorro no debe alterar nombres, hechos o instrucciones de actuación.

Licencia declarada: MIT. Rama predeterminada observada: release/v3.8.53. Referencias consultadas:

- README.md, blob 904b3c117fbf24c3a56f96eb17bb80e4cfca5c28.
- docs/reference/FREE_TIERS.md, blob ccfeed04dc97b002891989485fdb52b802e4f1a2.
- docs/guides/HEADLESS.md, blob 411c6cc23edf65defb5102898377d6b3dc39dd41.
- LICENSE, blob b5c9f58d06b1cef61ebf96f580d90c3dba5e1dac.

### public-apis — recurso de investigación, prioridad media

Repositorio: https://github.com/public-apis/public-apis

Es un catálogo comunitario de APIs de distintas categorías. Puede ayudar a descubrir fuentes para ciencia, historia, cultura y otras temáticas, así como servicios complementarios. No es por sí mismo un generador de videos ni una conexión que habilite automáticamente todos los servicios listados.

Cada incorporación deberá verificar documentación oficial, acceso, cuotas, licencias de los datos y recursos, uso comercial y vigencia. La licencia MIT del catálogo no se traslada a todos los contenidos o servicios enlazados. La promoción de una suite comercial en el README tampoco demuestra que todas sus funciones sean gratuitas.

Licencia declarada por metadatos: MIT. Rama observada: master. Se leyó README.md mediante GitHub. Antes de incorporar APIs concretas se guardará la evidencia del proveedor, no solo su presencia en este catálogo.

### agent-browser — candidato auxiliar, prioridad media

Repositorio: https://github.com/vercel-labs/agent-browser

Documenta una herramienta de automatización de navegador para agentes, con snapshots, interacción, pruebas, persistencia de sesiones y funciones de protección optativas. Declara soporte para Windows x64 y licencia Apache-2.0. Puede ayudar en pruebas de nuestra interfaz y tareas web específicas cuando el sitio y la autorización lo permitan.

El navegador, sus controles y el razonamiento que decide las acciones son componentes diferentes. Instalar esta herramienta no proporciona por sí solo modelos gratuitos ni acceso a las cuentas del usuario. Sus opciones de seguridad deben configurarse; no se asumirán activas por defecto.

Se priorizarán APIs oficiales para publicación. La automatización de navegador no reemplaza una auditoría de TikTok, permisos de Meta, consentimiento, autenticación ni condiciones del servicio. Los bloqueos de acceso requerirán una continuación permitida; no se diseñará evasión de cuotas o controles.

README.md consultado: blob dc103702f638491e276a8595ddcae5cc97ec52a5. Las prestaciones descritas deben probarse en una versión fijada antes de integrar actualizaciones.

**Decisión propuesta:** probar OmniRoute como conector opcional; usar public-apis como catálogo de descubrimiento; evaluar agent-browser para pruebas y apoyos web concretos. El coordinador de producción, la continuidad visual, el montaje y el control editorial siguen necesitando diseño propio.

## 9. Operación, costos y excepciones

- Una cuenta o varias claves de la misma cuenta pueden compartir cuota; se contabilizará por el límite real del proveedor, evitando sumas ficticias.
- Respetar ventanas, concurrencia y Retry-After; emplear reintentos limitados y espera persistente.
- Un cambio de proveedor debe respetar voz, formato, referencias y calidad. No se intercambiarán narradores a mitad de un video sin la configuración correspondiente.
- Una cuota agotada no autoriza suscripciones, recargas, uso de credenciales ajenas ni llamadas de pago.
- Guardar proyectos y puntos de recuperación. Cancelar o reiniciar debe preservar trabajos completos y no publicar a medias.
- Guardar credenciales mediante un mecanismo seguro del sistema operativo o equivalente validado; excluirlas de logs, exportaciones y repositorios.
- Registrar la procedencia, licencia y tratamiento de cada recurso. Una música autorizada solo dentro de una plataforma no se reutilizará automáticamente en las demás.
- Las condiciones de publicación se comprobarán por plataforma y tipo de cuenta. Si la cuenta o aplicación no tiene acceso suficiente, conservar el resultado descargable y mostrar el bloqueo.
- La disponibilidad de una cuota no indica que el equipo esté encendido. Programación local exige el proceso activo; un servidor continuo implicaría una decisión adicional de alojamiento y costo.
- Los modos rápidos y alternativas de menor complejidad se habilitarán explícitamente. La configuración predeterminada conserva calidad y espera.

## 10. Criterios de calidad y pruebas

Estos son criterios propuestos de aceptación; se ajustarán a partir de los primeros videos, sin considerar aprobada una capacidad por estar anunciada en un README.

| Prueba | Resultado necesario |
|---|---|
| P01: entrada y duración | Importar tema, guion y audio; reels dentro de 90–150 s; largos respetan la duración elegida y nunca superan 15 min |
| P02: factual y ficción | Conservar fuentes de afirmaciones factuales; distinguir ficción y reconstrucción; señalar incertidumbre para revisión |
| P03: narración visual | Planos relacionados con lo narrado, voz inteligible y video reproducible de principio a fin |
| P04: personajes | Referencias reconocibles, voz estable, diálogos correctos y actuación coherente; revisión de sincronización labial |
| P05: modo mixto | Cambiar de modalidad por escena, mantener continuidad y conservar correcciones manuales |
| P06: adaptación | Obtener un reel con contexto y cierre a partir de un largo, preservando el vínculo y evitando regeneraciones innecesarias |
| P07: presupuesto | Agotar una cuota y comprobar que el trabajo espera; provocar una ruta de precio positivo/desconocido y comprobar su bloqueo |
| P08: recuperación | Reiniciar durante la generación, recuperar el estado y regenerar únicamente lo incompleto |
| P09: credenciales | Reabrir con almacenamiento seguro y comprobar ausencia de secretos en archivos públicos y registros |
| P10: publicación | Probar subida autorizada por plataforma, confirmar identificador/estado y simular respuesta perdida sin duplicar publicaciones |
| P11: hardware | Medir RAM, CPU, espacio y tiempo en el i3/8 GB, con render y navegador; elegir concurrencia a partir de resultados |
| P12: versiones | Reencuadrar para horizontal/vertical, revisar áreas cubiertas por la interfaz de cada plataforma y respetar subtítulos del perfil |
| P13: lotes | Ejecutar una pequeña cola mixta, observar esperas y estimar capacidad sostenida sin extrapolar solo el mejor caso |

Los problemas críticos bloquean la entrega automática/publicación: archivo corrupto, narración incompleta, duración fuera de límites, recurso sin derechos aclarados, credencial expuesta, escena ausente o afirmación relevante sin revisión suficiente. Las comprobaciones editoriales y de identidad requieren calibración humana durante el piloto; no se promete detección perfecta de todos los errores.

## 11. Secuencia de validación antes de escalar

1. Comprobar cuentas disponibles, condiciones, capacidades reales y presupuesto cero. Fijar versiones de herramientas candidatas.
2. Ejecutar una prueba corta de personajes con referencias, actuación y diálogo; detectar pronto la viabilidad del módulo más exigente.
3. Producir un reel narrado de 90–150 s y otro de personajes/mixto dentro de ese rango.
4. Producir un largo de cinco minutos y obtener al menos una adaptación coherente. Comprobar reanudación y corrección por escena.
5. Validar el máximo de quince minutos, exportaciones y carga en el equipo del usuario.
6. Conectar y probar publicaciones autorizadas por plataforma, manteniendo descarga manual.
7. Ejecutar un lote pequeño, medir cuotas reales, tiempo, fallos, intervención y recursos reutilizados; después ajustar la media semanal.

El piloto cubrirá al menos un contenido factual y uno narrativo; los ejemplos conocidos del usuario —relato del hospital y contenido bíblico dialogado— servirán como referencias de entrada, con perfiles separados. Se incorporará un ejemplo de otra temática para comprobar que el motor no conserva reglas exclusivas de terror o Biblia.

## 12. Pendientes y siguiente acción

El alcance funcional queda definido para empezar validaciones. Siguen pendientes: elección de proveedores por capacidad, condiciones y rendimiento real; disponibilidad gratuita de animación con continuidad y labios; permisos de publicación; almacenamiento disponible; perfiles concretos de los primeros canales y criterios visuales de aceptación sobre sus ejemplos.

Estas incógnitas se resolverán mediante configuración y pruebas, no con promesas de capacidad basadas en el número de proveedores o estrellas de un repositorio. La siguiente acción es una prueba técnica acotada de conexiones y del módulo de personajes, seguida de los pilotos de extremo a extremo. El desarrollo debe mantener el sistema modular para corregir lo aprendido sin rehacerlo completo.
