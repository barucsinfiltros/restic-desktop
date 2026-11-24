# Hoja de ruta de implementación — Restic Desktop Fork

> **Alcance vigente.** La especificación rectora es [RESTIC_DESKTOP_DESIGN.md](RESTIC_DESKTOP_DESIGN.md). El contenido anterior de esta hoja se conserva como historial cuando contradice esa especificación. El catálogo parte limpio y no requiere importar JSON heredado ni implementar el esquema v2 de linaje.

## Estado del MVP

- Catálogo SQLite en preparación con validación de invariantes al abrir, carpeta única, asociaciones transaccionales, archivado y copia SQLite coherente a una ruta nueva. Una vista aislada permite crear y editar perfiles con el formulario existente, gestionar asociaciones y registrar carpetas de repositorios sin ejecutar Restic. Los respaldos por catálogo siguen pendientes.
- La vista de preparación puede guardar referencias de credenciales en Credential Manager. El adaptador se probó con dobles y con una credencial sintética creada y eliminada en la cuenta actual. Falta verificar la cuenta de ejecución automática y completar la recuperación ante fallos entre almacén y catálogo.
- La vista de preparación no ejecuta Restic y el servicio ofrece una comprobación de admisión que actualmente rechaza cualquier operación. Todavía no existe un coordinador que aplique esa comprobación a ejecuciones reales. Las rutas heredadas existentes siguen independientes y no se han neutralizado. Antes de operaciones reales del catálogo deben verificarse la barrera contra ejecutores heredados, la identidad de destinos, las credenciales y la recuperación.
- La restauración sobre el origen permanece deshabilitada. La restauración alternativa requiere verificación.

## Criterios verificables del catálogo en preparación

- Cuando se crea o edita un perfil, el servicio exige una única carpeta y valida sus opciones.
- Cuando un repositorio compartido tiene asociaciones incompatibles, el servicio rechaza convertirlo en exclusivo hasta retirarlas de forma explícita.
- Cuando se archiva un perfil sin propiedad exclusiva, el servicio conserva su UUID y nombre, retira opciones y asociaciones, y preserva repositorios físicos. Si conserva un exclusivo, rechaza la operación.
- Cuando se solicita una copia del catálogo, se crea en una ruta nueva y se verifica su integridad y referencias. Se publica mediante un enlace exclusivo desde un temporal del mismo directorio y falla si el destino existe o el sistema de archivos no admite ese enlace.

## Orden de entrega

1. Catálogo de carpeta única, exclusividad y archivado, con pruebas y recuperación.
2. Interfaz y credenciales seguras, con barrera frente a ejecutores incompatibles.
3. Respaldo manual por UUID con resultados por destino.
4. Exploración y restauración alternativa verificada.
5. Automatización, restauración al origen y retención segura en etapas posteriores.


**Documento rector:** plan de desarrollo funcional y técnico del fork.  
**Estado:** hoja de ruta consolidada; las fases 0–3 tienen implementación inicial, pero su aceptación técnica no está cerrada.  
**Rama de referencia:** `codex/initial-restic-foundation`  
**Base upstream:** `Dallustallus/restic-desktop`, commit `d2f258f99a56f8b40a4cd10f75e0bc2727cfc065`  
**Stack de referencia aprobado:** Python + PySide6 + Restic + SQLite, con integración específica para Windows 11.

> Este documento conserva los requisitos y decisiones acordados para el fork. No convierte propuestas futuras en decisiones aprobadas. Las decisiones arquitectónicas fundamentales, los cambios de alcance y las operaciones destructivas requieren aprobación expresa.

---

## 1. Propósito y alcance del producto

Construir una aplicación de escritorio generalista para administrar respaldos con Restic. No debe estar limitada a Minecraft ni a un único tipo de carpeta o repositorio.

La aplicación debe facilitar la configuración, ejecución, supervisión, exploración, retención y restauración de respaldos, manteniendo la seguridad de los datos y aprovechando selectivamente el proyecto upstream.

### Objetivos principales

1. Administrar perfiles de respaldo y repositorios como conceptos independientes.
2. Permitir que varios perfiles compartan un repositorio o utilicen repositorios exclusivos.
3. Ejecutar respaldos manuales y automáticos de forma fiable.
4. Supervisar procesos Restic sin depender de la interfaz gráfica.
5. Restaurar snapshots o elementos individuales con protecciones contra destinos incorrectos y sobrescrituras accidentales.
6. Gestionar retención, integridad, historial y estado de los repositorios.
7. Integrarse con Windows para tareas automáticas, minimización a bandeja e inicio/apagado.
8. Mantener una arquitectura modular, verificable y económicamente sencilla.

### Fuera del objetivo

- Convertirse en una suite empresarial equivalente a Veeam o Acronis.
- Crear un motor propio de deduplicación, cifrado o almacenamiento que sustituya Restic.
- Subir automáticamente repositorios, datos personales o credenciales a servicios externos.
- Ejecutar borrados, migraciones o restauraciones destructivas sin confirmación explícita.

---

## 2. Decisiones aprobadas y reglas permanentes

### 2.1 Decisiones aprobadas

- Estrategia de fork de Restic Desktop, preservando el historial y respetando la licencia MIT y las atribuciones aplicables.
- Reutilización selectiva de componentes upstream; no adoptar automáticamente su arquitectura completa.
- Stack de referencia: Python, PySide6, Restic y SQLite.
- Separación progresiva de interfaz, servicios de aplicación, ejecución Restic, persistencia y funciones específicas de Windows.
- Repositorios y perfiles independientes, con asociación flexible de uno o varios perfiles a un repositorio.
- Restauración predeterminada sobre la ubicación original solo cuando exista un flujo de seguridad suficiente; siempre debe haber vista previa y confirmación explícita.
- Automatización diferenciada de respaldos al inicio y durante el apagado de Windows.
- Respaldos manuales únicamente por orden del usuario.
- En los respaldos automáticos, detectar cambios y omitir ejecuciones sin cambios cuando corresponda.
- Retención configurable por perfil o repositorio.
- Historial detallado y panel de estado.
- Desarrollo incremental por fases, con pruebas y aceptación antes de avanzar.

### 2.2 Reglas de seguridad

- No asumir que un código de salida 0 demuestra por sí solo que un respaldo está completo. Interpretar también el resumen documentado de Restic cuando el flujo lo requiera.
- No presentar una operación fallida, incompleta, interrumpida o no confirmada como exitosa.
- Diferenciar desregistrar un repositorio de borrar físicamente sus datos.
- El borrado físico debe ser una acción separada, irreversible, con validación reforzada de identidad y alcance.
- No sobrescribir destinos de restauración silenciosamente.
- Preferir staging, vista previa, verificación y recuperación controlada antes de publicar una restauración.
- No almacenar secretos en argumentos, logs o mensajes. Usar mecanismos de entorno o almacenamiento protegido adecuados.
- No ejecutar pruebas sobre repositorios personales. Las pruebas Restic modificadoras deben usar repositorios temporales desechables.
- No realizar commits, push, PR, publicación, despliegues ni operaciones destructivas sin autorización expresa.
- Preservar cambios existentes y revisar el estado de Git antes de cada intervención.

---

## 3. Arquitectura objetivo

La separación siguiente es el objetivo de diseño. No exige crear todos los módulos de una vez ni impone nombres o rutas que todavía no existan.

### 3.1 Interfaz PySide6

Responsabilidades:

- Ventana principal, navegación, panel y páginas.
- Formularios y asistentes de perfiles, repositorios, respaldos y restauración.
- Exploración de snapshots y archivos.
- Presentación de progreso, errores e historial.
- Notificaciones y minimización a bandeja.

La interfaz no debe ejecutar directamente lógica compleja de Restic ni mantener procesos de larga duración.

### 3.2 Servicios de aplicación y coordinador

Responsabilidades:

- Recibir acciones de la interfaz, CLI y automatización.
- Validar solicitudes.
- Coordinar perfiles, repositorios, destinos y políticas.
- Evitar ejecuciones incompatibles o duplicadas.
- Mantener estados de operaciones y comunicar resultados.

### 3.3 Motor Restic y supervisor de procesos

Responsabilidades:

- Construir argumentos estructurados y seguros.
- Ejecutar Restic sin shell cuando sea posible.
- Gestionar entorno, directorio de trabajo y salida.
- Supervisar PID, progreso, cancelación, timeout y terminación real.
- Clasificar resultados con evidencia suficiente.
- No depender de PySide6 ni de widgets.

### 3.4 Persistencia SQLite y configuración

Responsabilidades:

- Persistir perfiles, repositorios, asociaciones, políticas e historial.
- Gestionar migraciones versionadas.
- Mantener compatibilidad con información histórica cuando sea posible.
- Evitar que GUI y procesos programados corrompan o compitan por actualizaciones.

La separación exacta entre configuración JSON existente y SQLite debe decidirse tras inspeccionar el modelo heredado. No migrar datos de usuario automáticamente sin estrategia, copia de seguridad y aprobación.

### 3.5 Restauración segura

Responsabilidades:

- Previsualizar archivos y destinos.
- Validar identidad, permisos y estado del destino.
- Preparar staging privado cuando el diseño lo permita.
- Ejecutar restauración sin sobrescritura accidental.
- Verificar resultados y ofrecer recuperación controlada.

### 3.6 Integración Windows

Responsabilidades:

- Programación y ejecución en segundo plano.
- Inicio de sesión/inicio de Windows.
- Apagado ordenado con plazo limitado.
- Bandeja del sistema y notificaciones.
- Protección de credenciales y gestión de procesos.
- Recuperación y registro de ejecuciones interrumpidas.

La viabilidad de un servicio Windows, tareas de inicio/apagado y mecanismos de preshutdown debe demostrarse con prototipos y pruebas reales antes de adoptarse como arquitectura definitiva.

---

## 4. Hoja de ruta por fases

Las fases describen entregables y dependencias. La división puede ajustarse si una auditoría descubre incompatibilidades, pero no se deben saltar los criterios de seguridad de cada etapa.

### Fase 0 — Preparación y línea base

**Estado:** realizada inicialmente; debe conservarse como referencia.

Objetivos:

- Inspeccionar repositorio, rama, commit, remotos y estado de trabajo.
- Identificar origen upstream y conservar el historial Git.
- Registrar stack, dependencias, configuración, pruebas y limitaciones.
- Establecer una línea base reproducible.

Entregables:

- Identificación de la base upstream.
- Estado inicial del repositorio y rama de trabajo.
- Inventario de dependencias y estructura.
- Informe de pruebas y riesgos iniciales.

Criterios de aceptación:

- Se conoce qué código es upstream y qué cambios pertenecen al fork.
- No se han perdido cambios ni historial.
- Las pruebas de referencia se pueden reproducir o sus limitaciones están documentadas.

### Fase 1 — Extracción de componentes visuales reutilizables

**Estado:** implementada inicialmente; pendiente de aceptación integral.

Objetivos:

- Identificar componentes visuales independientes.
- Desacoplar temas, iconos, tarjetas, estadísticas, gráficos, menús, navegación, diálogos y asistentes genéricos.
- Mantener compatibilidad visual sin rediseñar toda la aplicación.
- Permitir importarlos sin cargar la ventana principal ni iniciar Restic.

Restricciones:

- No migrar toda la interfaz a Qt Designer.
- No reconstruir páginas que ya sean reutilizables y estables.
- No introducir dependencias visuales innecesarias.

Criterios de aceptación:

- Los componentes reutilizados se pueden importar de forma aislada.
- Las páginas principales siguen funcionando.
- Los recursos se resuelven tanto en desarrollo como en el paquete PyInstaller.
- No se introducen regresiones de navegación o carga.

### Fase 2 — Contención de riesgos heredados

**Estado:** implementada inicialmente. H1.1 fue aceptado por auditoría independiente. H1.2 conserva sus límites documentados y H1.3 tiene pendiente la validación de symlinks reales.

Objetivos:

- Diferenciar desregistrar repositorio de eliminar sus datos.
- Retirar o bloquear rutas heredadas que puedan borrar datos de repositorios.
- Corregir la interpretación de resultados de procesos.
- Aislar mecanismos de cancelación antiguos que confundan terminar un hilo con terminar el proceso.
- Deshabilitar rutas de restauración que puedan sobrescribir ubicaciones originales sin protección suficiente.

Criterios de aceptación:

- Desregistrar no borra datos del repositorio.
- No existe una ruta accidental de borrado físico.
- La UI no presenta errores como éxitos.
- Las rutas de restauración inseguras están bloqueadas.
- Los riesgos que no se hayan podido resolver están documentados.

### Fase 3 — Supervisor Restic independiente de Qt

**Estado:** implementada inicialmente. La clasificación original de H2 fue aceptada y H2.3 está resuelto. H2.2-R3 y H2.2-T1 están corregidos y auditados. H2.2 fue aceptado para el alcance verificado en Windows. La prueba nativa en POSIX sigue pendiente. H3 sigue pendiente de diseño.

Objetivos:

- Crear un contrato estructurado de ejecución Restic.
- Ejecutar procesos con argumentos separados, entorno controlado, stdout y stderr independientes.
- Supervisar inicio, progreso, código de salida y finalización real.
- Diferenciar resultado observado y motivo de parada solicitado.
- Integrar progresivamente el supervisor en el respaldo manual y `--run-job`.

Estados y resultados:

- Iniciado.
- En ejecución/progreso.
- Completado.
- Sin cambios.
- Fallido.
- Incompleto.
- Cancelado o con timeout solicitado, conservando también el resultado real.
- Interrumpido.
- Fallo de inicio.

Criterios de aceptación:

- El supervisor puede importarse sin PySide6.
- La finalización terminal se publica después de observar la salida del proceso.
- Se conserva el código real y la evidencia de snapshot.
- Los consumidores no presentan falsos éxitos.
- Los tests cubren éxito, error, salida, cancelación, timeout, proceso activo, argumentos con espacios y fallo de inicio.
- No se ejecutan operaciones modificadoras contra repositorios personales.

Limitación conocida:

- `StopPolicy.WAIT` puede esperar indefinidamente si Restic no termina.
- El vencimiento de un plazo no garantiza la terminación del proceso.
- No habilitar terminación forzada en operaciones reales sin un diseño y pruebas específicos.

### Fase 4 — Modelo de dominio y persistencia de perfiles/repositorios

**Estado:** núcleo de dominio y persistencia implementado en modo `staged`, pendiente de auditoría. El catálogo SQLite se crea en una ruta explícita y opera mediante un servicio Python con revisiones, transacciones y validación de exclusividad. La aplicación sigue usando la configuración heredada. El importador, el corte a SQLite, la integración con GUI/CLI y el respaldo portable siguen pendientes.

Objetivo: introducir un modelo coherente para perfiles y repositorios, sin depender de las asociaciones y heurísticas heredadas.

Requisitos funcionales:

- Crear repositorios independientemente de los perfiles.
- Registrar repositorios existentes sin recrearlos ni migrarlos automáticamente.
- Crear perfiles y asignarles repositorios manualmente.
- Permitir varios perfiles sobre un mismo repositorio.
- Permitir repositorios exclusivos por perfil.
- Ofrecer desde la creación de perfil la opción de crear un repositorio exclusivo.
- Diferenciar identidad del repositorio, ubicación, configuración y estado.
- Permitir desregistrar sin borrar datos.
- Mantener referencias estables, no depender únicamente de nombres visibles.

Implementación pendiente:

- Importación compatible desde la configuración upstream y reconciliación de duplicados y conflictos.
- Activación del catálogo, integración con los consumidores y respaldo portable, según el [diseño de Fase 4](PHASE_4_DESIGN.md).

Criterios de aceptación:

- Las asociaciones perfil/repositorio son explícitas y persistentes.
- Dos perfiles pueden compartir repositorio sin duplicar ni confundir su identidad.
- Un repositorio existente puede registrarse sin inicializarlo.
- Las migraciones tienen pruebas con configuraciones antiguas y datos temporales.
- Ninguna migración destructiva se ejecuta sin respaldo y autorización.

### Fase 5 — Gestión de perfiles y motor de respaldos

**Estado:** pendiente.

Objetivo: permitir definir qué se respalda y coordinar ejecuciones de forma consistente.

Requisitos:

- Un perfil puede incluir varias carpetas independientes.
- Cada carpeta puede tener exclusiones.
- Filtros por extensión, tamaño y patrones.
- Selección de perfil completo o respaldo parcial de carpetas.
- Etiquetas y opciones Restic configurables con validación.
- Un perfil puede dirigirse a uno o varios repositorios.
- Los repositorios compartidos no deben producir asociaciones ambiguas.
- Respaldos manuales solo se ejecutan por acción expresa del usuario.
- Respaldos automáticos pueden omitir operaciones si no detectan cambios.
- Restic mantiene la responsabilidad de incrementalidad y deduplicación.

Entregables:

- Modelo y editor de perfiles.
- Validación previa de orígenes, destinos y exclusiones.
- Coordinador de respaldos multi-destino.
- Resultados por destino y resultado agregado del perfil.
- Prevención de ejecuciones concurrentes incompatibles.

Criterios de aceptación:

- No se mezclan carpetas o destinos de perfiles distintos.
- Cada destino tiene resultado independiente.
- Un destino fallido no se presenta como respaldo completo del perfil.
- La omisión por ausencia de cambios se diferencia de un fallo.
- La ejecución manual nunca se dispara por una programación automática accidental.

### Fase 6 — Restauración segura y recuperación

**Estado:** pendiente; requiere resolver H1 antes de ampliar su alcance.

Objetivo: ofrecer restauración de snapshots y elementos individuales sin poner en riesgo los datos existentes.

Requisitos funcionales:

- Restaurar una snapshot completa.
- Restaurar archivos o carpetas individuales.
- Vista previa del contenido y destino.
- Restauración predeterminada sobre ubicación original solo cuando exista protección suficiente.
- Alternativa en una carpeta nueva con identificador/fecha.
- Alternativa en una ubicación elegida por el usuario.
- Ubicación alternativa configurable por perfil.
- Confirmación explícita antes de modificar archivos existentes.

Diseño de seguridad requerido:

1. Resolver y validar la identidad del snapshot y del repositorio.
2. Mostrar los elementos que se restaurarán y el destino efectivo.
3. Validar todos los componentes de la ruta y los puntos de reanálisis.
4. Evitar carreras entre validación y escritura.
5. Utilizar staging privado/controlado cuando sea viable.
6. Definir conflictos y política de sobrescritura.
7. Verificar el resultado antes de considerarlo completado.
8. Diseñar recuperación o rollback ante fallos parciales.
9. Registrar qué archivos se restauraron y dónde.

Criterios de aceptación:

- Ninguna restauración se declara exitosa si no se ha verificado el resultado exigido.
- No se sobrescriben datos silenciosamente.
- La ruta efectiva coincide con la vista previa confirmada.
- Los fallos parciales quedan identificados y recuperables según la política aprobada.
- Pruebas Windows incluyen junctions, symlinks cuando el entorno lo permita, rutas inválidas, carreras y cambios concurrentes.
- Pruebas de Restic usan repositorios temporales desechables.

### Fase 7 — Exploración, integridad, retención y administración de repositorios

**Estado:** pendiente de consolidación sobre la arquitectura nueva.

Objetivos:

- Explorar snapshots y contenido de repositorios.
- Consultar espacio ocupado, número de snapshots y metadatos.
- Ejecutar verificaciones de integridad.
- Configurar retención.
- Administrar ciclo de vida de repositorios.

Requisitos:

**Exploración**
- Navegar snapshots y archivos.
- Consultar rutas, tamaños, fechas y metadatos disponibles.
- Buscar y seleccionar elementos para restaurar.

**Integridad**
- Ejecutar `restic check` con alcance explícito.
- Diferenciar comprobación rápida, parcial y completa cuando Restic lo permita.
- Mostrar fecha, resultado y errores.
- No confundir verificación estructural del repositorio con una restauración probada.

**Retención**
- Configurar últimas N snapshots.
- Reglas diarias, semanales y mensuales.
- Configuración por perfil o repositorio, según el modelo aprobado.
- Vista previa antes de aplicar.
- Diferenciar cálculo de política de ejecución efectiva de `forget` y `prune`.

**Administración**
- Registrar y desregistrar repositorios.
- Explorar contenido.
- Cambiar ubicación o mover repositorios con comprobación de destino, integridad y actualización segura de referencias.
- Diferenciar claramente desregistro y eliminación física.
- Cualquier eliminación física futura requerirá confirmación reforzada.

Criterios de aceptación:

- Los comandos destructivos de retención requieren vista previa y confirmación.
- La identidad del repositorio se valida antes de operaciones.
- La app no muestra un repositorio como íntegro si la comprobación no terminó correctamente.
- Los movimientos no dejan referencias apuntando a ubicaciones antiguas.
- La eliminación física permanece deshabilitada hasta que tenga un diseño aprobado.

### Fase 8 — Automatización de Windows y ejecución en segundo plano

**Estado:** pendiente; depende de las fases 3, 4 y 5.

Objetivo: ejecutar respaldos automáticos aunque la ventana no esté abierta, con comportamiento predecible durante inicio y apagado.

Requisitos aprobados:

- Configurar independientemente qué perfiles/repositorios se ejecutan al inicio de Windows.
- Configurar independientemente qué perfiles/repositorios se ejecutan durante el apagado.
- La ventana puede cerrarse o minimizarse a bandeja sin detener la automatización.
- Los respaldos automáticos detectan cambios y omiten operaciones innecesarias.
- Los respaldos manuales nunca se ejecutan sin orden del usuario.
- Durante un apagado normal, esperar aproximadamente 15 minutos para completar el respaldo.
- Si el plazo se agota, interrumpir de forma segura y registrar el estado.
- En la siguiente ejecución, comprobar cambios y respaldar lo que corresponda.
- No se exige protección frente a apagones súbitos o pérdida abrupta de energía.

Investigación técnica obligatoria antes de elegir mecanismo:

- Comparar Task Scheduler, proceso residente, servicio Windows y notificaciones de apagado/preshutdown.
- Evaluar permisos, cuentas de ejecución, acceso a unidades, credenciales, procesos descendientes y empaquetado.
- Comprobar qué mecanismos permiten realmente el margen de tiempo deseado.
- Probar cancelación cooperativa y recuperación con Restic real en repositorios temporales.
- No asumir que `StopPolicy.WAIT` satisface el plazo de apagado.
- No implementar terminación forzada sin demostrar sus efectos sobre Restic y los repositorios.

Criterios de aceptación:

- La automatización funciona sin ventana abierta.
- Las selecciones de inicio y apagado son independientes.
- El apagado normal respeta el presupuesto de tiempo probado.
- Una interrupción queda registrada como tal, no como éxito.
- La siguiente ejecución detecta correctamente cambios pendientes.
- Se prueba en Windows real, no solo mediante procesos simulados.

### Fase 9 — Panel, historial y experiencia de usuario

**Estado:** parcialmente disponible en upstream; pendiente de integración completa con el modelo nuevo.

Objetivo: mostrar información útil y consistente sin duplicar ni inventar estados.

Panel:

- Espacio ocupado por repositorio.
- Cantidad y listado de snapshots.
- Último respaldo por perfil/destino.
- Estado de integridad.
- Archivos añadidos, modificados y eliminados cuando Restic proporcione datos fiables.
- Historial reciente, fallos y advertencias.

Historial genérico desplegable:

- Cambios y operaciones.
- Perfil y repositorio implicados.
- Snapshot e identificador.
- Archivos procesados.
- Duración.
- Resultado observado.
- Motivo de cancelación/timeout, si existió.
- Errores y detalles relevantes.

Experiencia:

- GUI en primer plano.
- Operaciones largas en segundo plano.
- Minimización a bandeja.
- Notificaciones de finalización y errores.
- Estados coherentes entre GUI, CLI, tareas y SQLite.

Criterios de aceptación:

- Panel e historial no atribuyen snapshots ajenas a una ejecución.
- Los resultados incompletos o interrumpidos no se muestran como éxitos.
- Los datos antiguos siguen siendo consultables después de migraciones.
- Los mensajes son comprensibles y permiten diagnosticar fallos.

### Fase 10 — Empaquetado, recuperación operativa y versión estable

**Estado:** pendiente.

Objetivo: entregar una aplicación instalable y mantenible, con comportamiento verificable fuera del entorno de desarrollo.

Entregables:

- Empaquetado reproducible con PyInstaller u otra alternativa aprobada.
- Resolución correcta de recursos, iconos y dependencias.
- Instalación y actualización controladas.
- Manejo de configuración, historial y datos del usuario.
- Diagnóstico y exportación de logs sin secretos.
- Copia y recuperación de configuración.
- Documentación de instalación, uso, limitaciones y recuperación.
- Pruebas en Windows limpio o entorno equivalente.
- Pruebas de actualización y migración desde la versión anterior.

Criterios de aceptación:

- La aplicación arranca sin Python instalado.
- Las dependencias externas se detectan y sus versiones se muestran.
- Los datos de usuario sobreviven a actualización y reinstalación según la política documentada.
- No se incluyen secretos en logs ni paquetes.
- El proceso de actualización no elimina repositorios ni historial.
- Existe un procedimiento probado de recuperación.

---

## 5. Dependencias y orden de ejecución

Orden de referencia:

1. Cerrar las correcciones de seguridad y compatibilidad pendientes de las fases 2–3.
2. Fase 4: modelo de perfiles/repositorios.
3. Fase 5: perfiles y coordinación de respaldos.
4. Fase 6: restauración segura, con prioridad alta por riesgo de datos.
5. Fase 7: exploración, integridad, retención y administración.
6. Fase 8: automatización Windows, una vez que el motor y la persistencia sean fiables.
7. Fase 9: consolidación del panel e historial sobre los resultados reales.
8. Fase 10: empaquetado y versión estable.

Las fases 6, 7 y 8 pueden tener tareas de investigación paralelas, pero su implementación debe respetar las dependencias de seguridad y dominio. No implementar automatización de apagado sobre un supervisor cuya terminación segura no esté validada.

---

## 6. Estado actual conocido al consolidar este documento

Referencia de implementación auditada:

- Base upstream: `d2f258f99a56f8b40a4cd10f75e0bc2727cfc065`.
- Commit de fundación: `60635d59676676bf03324cf10591753d60f6407a`.
- Commit de correcciones H1/H2 auditado: `58d2524a07f48f32bc9eae4848266dec6636a8af`.
- Commit de seguimiento auditado: `6bd2a6a16ed2223e7a566e640fa9418356b45a59`.
- Seguimiento H2.2-R3 y H2.2-T1: auditoría independiente del diff local sobre `792802c2d4b370c3ed80f76b2d193c2ab3b5a015`.
- Rama de referencia: `codex/initial-restic-foundation`.

### Estado por fase

| Fase | Estado |
|---|---|
| 0 — Preparación | Realizada inicialmente |
| 1 — Componentes visuales | Implementada inicialmente; aceptación pendiente |
| 2 — Contención heredada | H1.1 aceptado por auditoría independiente. H1.2 documentado y H1.3 parcialmente validado |
| 3 — Supervisor Restic | H2.2 aceptado en el alcance verificado en Windows. Prueba POSIX pendiente. H2.3 resuelto. H3 pendiente de diseño |
| 4 — Modelo perfiles/repositorios | Núcleo en modo staged, pendiente de auditoría. Integración pendiente |
| 5 — Perfiles y respaldos | Pendiente |
| 6 — Restauración segura | Pendiente |
| 7 — Exploración, integridad y retención | Pendiente |
| 8 — Automatización Windows | Pendiente |
| 9 — Panel e historial | Parcial en upstream; integración pendiente |
| 10 — Empaquetado y versión estable | Pendiente |

### Deuda técnica y riesgos abiertos

- **H1.1–H1.3:** la auditoría aceptó la protección hasta confirmar la salida del hijo directo. La validación de la ruta reduce carreras y sigue teniendo límites de confinamiento. La prueba de symlinks reales en Windows queda pendiente por el error de permisos 1314.
- **H2.2–H2.3:** el registro secundario conserva el resultado y el motivo de parada. La auditoría independiente aceptó H2.2-R3 y H2.2-T1 en el alcance verificado en Windows con pruebas deterministas, una tubería nativa y procesos con tuberías heredadas. El supervisor exige EOF de stdout para confirmar el resumen final. Si solo stderr queda incompleto, el respaldo puede conservar el éxito. Se mantiene el límite de 64 pasadas. La prueba nativa en POSIX sigue pendiente. Ver [Base inicial del fork](INITIAL_FOUNDATION.md) para la evidencia y sus límites.
- **H3:** `StopPolicy.WAIT` puede esperar indefinidamente; el plazo no garantiza la terminación.
- La restauración aún no tiene confinamiento completo de escrituras, staging transaccional, verificación final ni rollback.
- Las tareas programadas heredadas, comandos fuera del supervisor, gestión de credenciales y concurrencia entre instancias necesitan revisión.
- El servicio o mecanismo de apagado de Windows no está seleccionado ni validado.
- Las pruebas con Restic real deben seguir usando repositorios temporales desechables.

La aceptación independiente de H2.2 se limita al diff auditado y al alcance verificado en Windows. La validación nativa en POSIX queda abierta.

---

## 7. Método de trabajo para cada fase

Cada fase debe seguir este ciclo:

1. **Inspección:** revisar estado real del repositorio, instrucciones, arquitectura, cambios locales y pruebas.
2. **Análisis:** identificar requisitos, código heredado, dependencias, riesgos y alternativas.
3. **Diseño:** proponer solución mínima, justificarla y señalar decisiones que requieren aprobación.
4. **Alcance:** delimitar archivos/componentes, exclusiones y criterios de aceptación.
5. **Implementación:** cambios incrementales, sin sobrescribir trabajo existente.
6. **Verificación:** pruebas automatizadas, pruebas específicas del sistema operativo y evidencia real.
7. **Auditoría:** revisar diff, seguridad, compatibilidad, estado de Git y resultados.
8. **Aceptación:** decidir explícitamente si la fase queda aceptada o requiere correcciones.
9. **Documentación:** actualizar este documento con estado, commit, pruebas, limitaciones y decisiones nuevas aprobadas.

### Reglas para agentes de IA

- Inspeccionar el repositorio antes de editar.
- No inventar rutas, archivos, resultados ni requisitos.
- No asumir que una tarea está terminada por compilar.
- No ejecutar acciones destructivas ni operaciones sobre datos reales sin autorización.
- Resolver detalles reversibles dentro del alcance.
- Detenerse ante cambios de arquitectura, alcance, costes, publicación o producción no autorizados.
- Informar pruebas ejecutadas y no ejecutadas por separado.

---

## 8. Cómo mantener esta hoja de ruta

Este archivo es el documento rector del plan. Debe actualizarse cuando:

- Una fase cambie de estado.
- Se apruebe o descarte una decisión arquitectónica.
- Se modifiquen requisitos.
- Una auditoría descubra un riesgo que cambie el orden de trabajo.
- Se complete una fase y existan pruebas verificables.

No borrar decisiones anteriores sin registrar su sustitución y motivo. Mantener los informes de implementación y auditoría como documentos complementarios; no duplicar aquí todos sus detalles.

**Regla de continuidad:** antes de iniciar cualquier nueva fase, leer este documento y contrastar su estado con el commit y el repositorio reales.
