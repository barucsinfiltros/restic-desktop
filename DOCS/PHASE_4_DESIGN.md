# Diseño de la fase 4 de Restic Desktop

> **Documento histórico.** Los requisitos vigentes se encuentran en [RESTIC_DESKTOP_DESIGN.md](RESTIC_DESKTOP_DESIGN.md). La importación heredada y el esquema v2 de linaje han quedado fuera del alcance.

**Propuesta para auditoría.** La fase 4 separa perfiles y repositorios, estabiliza sus identidades y prepara una transición reversible desde JSON a SQLite. La propuesta está pendiente de aprobación. La base de código analizada es `38d87c81a337926c6be31b29d257abb894158d70` en `codex/initial-restic-foundation`. El informe no activa el catálogo ni cambia el comportamiento de la aplicación.

## Alcance y evidencia en el código

- `ResticSettingsManager` guarda `repositories` y `backup_jobs` en `restic_settings.json` junto con preferencias. El trabajo es el antecedente del perfil. Conserva orígenes, etiquetas, exclusiones, opciones de Restic, programación y referencias por nombre. Conviven `repository` y `repositories`. La escritura actual reemplaza el JSON completo. [Configuración](../restic_manager.py#L4260) · [Formulario del trabajo](../restic_manager.py#L3970)
- La interfaz, el CLI, el historial y el programador dependen de nombres visibles. La resolución heredada toma el primer repositorio con el nombre buscado. Renombrar, desregistrar o duplicar un nombre puede romper o desviar referencias. El asistente de respaldo ya abre el formulario de repositorio, así que puede reutilizarse para crear y vincular destinos por UUID. [Desregistro y edición](../restic_manager.py#L6505) · [Resolución heredada](../restic_manager.py#L6798) · [Asistente](../ui/backup_wizard.py#L174)
- `restic_history.db` tiene un esquema v3 con historial, estadísticas, caché y logs. Sus nombres históricos son etiquetas. Una coincidencia por nombre, etiqueta o ruta no demuestra la identidad de una ejecución anterior. [Esquema](../core/history_db.py#L61) · [Asociación de snapshots](../restic_manager.py#L2033)
- La fase 4 comprende catálogo, relaciones, operaciones de registro e importación. La coordinación de ejecuciones corresponde a la fase 5 y la automatización de Windows a la fase 8. H3 conserva su estado y su política de parada. [Hoja de ruta](IMPLEMENTATION_ROADMAP.md#fase-4--modelo-de-dominio-y-persistencia-de-perfilesrepositorios)

## Entidades, relaciones y opciones de almacenamiento

**Perfil.** UUID local estable, nombre visible, configuración de respaldo, revisión y estado. Puede guardarse en borrador sin destino. Su activación y cada admisión de ejecución requieren al menos un destino habilitado. Se valida el conjunto completo antes de lanzar el primer respaldo.

**Repositorio.** UUID local estable, nombre visible, revisión, estado de registro y propietario exclusivo opcional. Un repositorio compartido puede existir sin perfiles. Uno exclusivo solo puede estar asociado al perfil propietario. Un perfil puede tener combinaciones de destinos compartidos y exclusivos en un orden explícito. Se conserva el registro al desregistrar, incluidas sus relaciones, y se bloquea la ejecución de perfiles que dependan de ese destino. Antes de archivar al perfil propietario, cada repositorio exclusivo debe transferirse explícitamente a otro perfil no archivado o convertirse explícitamente en compartido, incluso si está desregistrado o pendiente de inicialización. No se realizan conversiones ni transferencias automáticas.

**Ubicación.** Cada registro tiene una ubicación activa antes de poder ejecutarse. El backend, el localizador, sus parámetros y la referencia de autenticación se editan de forma separada del UUID. La huella de ubicación sirve para buscar candidatos a duplicado. El ID nativo de Restic, cuando se verifica, sirve como evidencia adicional y no es clave primaria. Dos rutas pueden conducir al mismo repositorio, y dos copias en ubicaciones diferentes pueden conservar el mismo ID nativo. Ninguna coincidencia autoriza fusionar, mover ni elegir un destino por sí sola. Un cambio de destino exige verificar su identidad antes de permitir operaciones.

**Persistencia.** Se propone un catálogo SQLite local separado del historial, con un servicio Python compartido por Qt y el CLI. Guardar UUID en el JSON existente reduce el trabajo inicial pero obliga a resolver por fuera del almacén las relaciones, las escrituras simultáneas y los reemplazos completos. Usar el SQLite de historial simplifica la cantidad de archivos, pero acopla la configuración esencial con una base cuyo respaldo es opcional y cuya restauración hoy puede reemplazarla. El catálogo separado introduce una pieza que debe incluirse siempre en el respaldo de configuración cuando esté activo. JSON conserva preferencias generales y la configuración necesaria para el modo heredado. [Configuración](../restic_manager.py#L4260) · [Respaldo y restauración](../restic_manager.py#L14166)

## Invariantes y transiciones de exclusividad

Un repositorio con propietario exclusivo conserva exactamente una asociación con ese propietario, incluso en estado `pending_init` o `unregistered`. La asociación registra pertenencia y orden. La admisión de ejecución exige además que el perfil esté activo, el repositorio esté registrado y el destino y sus credenciales estén verificados.

| Operación explícita | Resultado al confirmar la transacción |
|---|---|
| Crear exclusivo para P | Crear registro y asociación P en la misma transacción. La asociación existe desde la reserva del alta, antes de inicializar el destino. |
| Compartido → exclusivo de P | Exigir P no archivado y autorización explícita si hay otros perfiles vinculados. Mostrar y retirar los vínculos aprobados, corregir o pasar a borrador los perfiles que queden sin destinos operables, y fijar propietario y vínculo P. Sin autorización se conserva el estado anterior. |
| Exclusivo de P → compartido | Eliminar el propietario y conservar la asociación P, su posición y el UUID del repositorio. Añadir otros perfiles requiere acción separada. |
| Exclusivo de P → exclusivo de Q | Exigir Q no archivado y confirmar el impacto en P. Retirar el vínculo P, cambiar el propietario y añadir Q en una sola transacción, con posición válida para Q. Si P queda sin destinos operables, pasa a borrador. |
| Desregistrar un repositorio | Conserva propietario y asociaciones y bloquea la admisión de los perfiles afectados. |
| Archivar un perfil | Se rechaza mientras sea propietario de algún repositorio exclusivo, incluido uno en `pending_init` o `unregistered`. Antes deben transferirse todos explícitamente a otro perfil no archivado o convertirse explícitamente en compartidos. No hay transferencias ni conversiones automáticas. El archivado conserva las asociaciones restantes y no elimina datos físicos. |

SQLite obliga a que exista el vínculo del propietario mediante una clave foránea compuesta diferida hasta `COMMIT`. Los triggers impiden vínculos ajenos al propietario. Borrar o cambiar su único vínculo sin cambiar la propiedad en la misma transacción falla al confirmar. El servicio autoriza conversiones y reasignaciones, calcula el impacto, valida el estado de los perfiles y controla revisiones y operaciones en curso. El orden de escritura para una reasignación es quitar el vínculo anterior, cambiar el propietario y crear el nuevo vínculo.

## DDL SQLite propuesto

Esquema v1 para una base de catálogo nueva. `options_json` y `backend_config_json` son objetos validados por Python según versión y backend. Esta decisión evita depender de extensiones SQLite para validarlos. El localizador y los parámetros excluyen secretos. Las referencias de credenciales se resuelven en ejecución. Su almacenamiento y recuperación deben aprobarse antes de activar el catálogo.

```sql
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE profiles (
    profile_id TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    state TEXT NOT NULL CHECK (state IN ('draft', 'active', 'archived')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    options_json TEXT NOT NULL
);

CREATE TABLE repositories (
    repository_id TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    state TEXT NOT NULL CHECK (
        state IN ('pending_init', 'registered', 'unregistered')
    ),
    exclusive_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    FOREIGN KEY (exclusive_profile_id, repository_id)
        REFERENCES profile_repositories(profile_id, repository_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE repository_locations (
    repository_id TEXT NOT NULL PRIMARY KEY
        REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    backend TEXT NOT NULL CHECK (length(trim(backend)) > 0),
    locator TEXT NOT NULL CHECK (length(trim(locator)) > 0),
    location_fingerprint TEXT,
    verified_restic_id TEXT,
    backend_config_json TEXT NOT NULL,
    credential_ref TEXT
);

CREATE TABLE profile_repositories (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    repository_id TEXT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (profile_id, repository_id),
    UNIQUE (profile_id, position)
);

CREATE TABLE catalog_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    mode TEXT NOT NULL CHECK (mode IN ('staged', 'active')),
    installation_id TEXT NOT NULL,
    transition_id TEXT,
    catalog_revision INTEGER NOT NULL DEFAULT 0 CHECK (catalog_revision >= 0),
    import_source_fingerprint TEXT
);

CREATE TABLE legacy_import_batches (
    batch_id TEXT NOT NULL PRIMARY KEY,
    canonicalization_version INTEGER NOT NULL CHECK (canonicalization_version > 0),
    source_fingerprint TEXT NOT NULL,
    canonical_fingerprint TEXT NOT NULL,
    base_catalog_revision INTEGER NOT NULL CHECK (base_catalog_revision >= 0)
);

CREATE TABLE legacy_profiles (
    batch_id TEXT NOT NULL REFERENCES legacy_import_batches(batch_id) ON DELETE RESTRICT,
    source_key TEXT NOT NULL,
    legacy_name TEXT NOT NULL,
    record_fingerprint TEXT NOT NULL,
    baseline_json TEXT NOT NULL,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    predecessor_batch_id TEXT,
    predecessor_source_key TEXT,
    link_method TEXT NOT NULL CHECK (link_method IN ('new', 'managed', 'reviewed')),
    decision_ref TEXT NOT NULL,
    PRIMARY KEY (batch_id, source_key),
    UNIQUE (batch_id, profile_id),
    UNIQUE (batch_id, source_key, profile_id),
    CHECK ((predecessor_batch_id IS NULL) = (predecessor_source_key IS NULL)),
    FOREIGN KEY (predecessor_batch_id, predecessor_source_key, profile_id)
        REFERENCES legacy_profiles(batch_id, source_key, profile_id) ON DELETE RESTRICT
);

CREATE TABLE legacy_repositories (
    batch_id TEXT NOT NULL REFERENCES legacy_import_batches(batch_id) ON DELETE RESTRICT,
    source_key TEXT NOT NULL,
    legacy_name TEXT NOT NULL,
    record_fingerprint TEXT NOT NULL,
    baseline_json TEXT NOT NULL,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    predecessor_batch_id TEXT,
    predecessor_source_key TEXT,
    link_method TEXT NOT NULL CHECK (link_method IN ('new', 'managed', 'reviewed')),
    decision_ref TEXT NOT NULL,
    PRIMARY KEY (batch_id, source_key),
    UNIQUE (batch_id, repository_id),
    UNIQUE (batch_id, source_key, repository_id),
    CHECK ((predecessor_batch_id IS NULL) = (predecessor_source_key IS NULL)),
    FOREIGN KEY (predecessor_batch_id, predecessor_source_key, repository_id)
        REFERENCES legacy_repositories(batch_id, source_key, repository_id) ON DELETE RESTRICT
);

CREATE TABLE legacy_job_aliases (
    alias TEXT COLLATE BINARY NOT NULL PRIMARY KEY
        CHECK (length(trim(alias)) > 0),
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT
);

CREATE INDEX profiles_listing_idx ON profiles(state, display_name);
CREATE INDEX repositories_listing_idx ON repositories(state, display_name);
CREATE INDEX repositories_owner_idx ON repositories(exclusive_profile_id);
CREATE INDEX locations_lookup_idx ON repository_locations(backend, location_fingerprint);
CREATE INDEX locations_restic_id_idx ON repository_locations(verified_restic_id);
CREATE INDEX profile_repositories_reverse_idx
    ON profile_repositories(repository_id, profile_id);
CREATE INDEX legacy_profiles_name_idx ON legacy_profiles(legacy_name);
CREATE INDEX legacy_repositories_name_idx ON legacy_repositories(legacy_name);
CREATE INDEX legacy_profiles_target_idx ON legacy_profiles(profile_id);
CREATE INDEX legacy_repositories_target_idx ON legacy_repositories(repository_id);
CREATE INDEX legacy_job_aliases_profile_idx ON legacy_job_aliases(profile_id);

CREATE TRIGGER enforce_exclusive_link_insert
BEFORE INSERT ON profile_repositories
WHEN EXISTS (
    SELECT 1 FROM repositories
    WHERE repository_id = NEW.repository_id
      AND exclusive_profile_id IS NOT NULL
      AND exclusive_profile_id <> NEW.profile_id
)
BEGIN
    SELECT RAISE(ABORT, 'exclusive repository belongs to another profile');
END;

CREATE TRIGGER enforce_exclusive_link_update
BEFORE UPDATE OF repository_id, profile_id ON profile_repositories
WHEN EXISTS (
    SELECT 1 FROM repositories
    WHERE repository_id = NEW.repository_id
      AND exclusive_profile_id IS NOT NULL
      AND exclusive_profile_id <> NEW.profile_id
)
BEGIN
    SELECT RAISE(ABORT, 'exclusive repository belongs to another profile');
END;

CREATE TRIGGER enforce_exclusive_owner_update
BEFORE UPDATE OF exclusive_profile_id ON repositories
WHEN NEW.exclusive_profile_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM profile_repositories
    WHERE repository_id = NEW.repository_id
      AND profile_id <> NEW.exclusive_profile_id
)
BEGIN
    SELECT RAISE(ABORT, 'repository has associations with another profile');
END;

PRAGMA user_version = 1;
COMMIT;
```

Después de crear el esquema, el servicio inserta la fila de `catalog_state` con el UUID persistente de instalación y modo `staged`. Hasta entonces se rechaza la apertura operativa del catálogo. El servicio valida la forma del UUID, las opciones, la ubicación, las colisiones y la preparación del perfil. Cada mutación del catálogo incrementa su revisión global en la misma transacción. El SQLite de historial sigue separado.

## Identidad e importación determinista

### F4-01 — Linaje persistente y reimportación

1. Validar el JSON en una copia local protegida. Aceptar únicamente la forma esperada, UTF-8 y valores JSON finitos. Rechazar claves duplicadas y secuencias Unicode inválidas. Guardar SHA-256 de los bytes originales y una huella canónica del lote. La canonicalización versionada ordena claves por puntos de código, elimina espacios sintácticos y normaliza números decimales exactos, incluido el cero. Conserva tipos, textos sin normalización Unicode, campos desconocidos y orden de arrays. Las huellas son metadatos privados.
2. Sellar cada lote con su UUID de lote, la instalación, la versión de canonicalización y la huella canónica. El servicio asigna el UUID de lote al preparar la operación y lo conserva para reintentos. Dos exportaciones gestionadas pueden tener contenido idéntico y linajes distintos. Por eso la huella no sustituye al UUID de lote. Dentro de un lote, `source_key` identifica la fila por tipo e índice. Para un alta confirmada, asignar UUIDv5 a partir del UUID de instalación y la tupla inequívoca de tipo, UUID de lote y `source_key`. El UUID de entidad permanece estable. El índice solo identifica una fila dentro de ese lote y nunca se compara entre lotes.
3. Persistir en `legacy_import_batches`, `legacy_profiles` y `legacy_repositories` el lote aceptado y el vínculo de cada fila a su UUID. El vínculo conserva huella, proyección canónica sin secretos para comparar campos, antecedente del mismo UUID cuando exista, método y referencia a la decisión. El servicio exige que el antecedente sea una correspondencia ya aceptada y que pertenezca al mismo linaje, sin ciclos. Los campos omitidos de la proyección requieren revisión si afectan la equivalencia. El lote conserva la revisión base de la instalación. El servicio registra quién autorizó la correspondencia, qué revisión examinó y la acción resultante. Los vínculos aceptados son de solo adición. Una fila ausente conserva su identidad histórica. Archivar o desregistrar requiere una orden propia.
4. Resolver identidades antes de aplicar contenido. El reintento de un lote identificado por su UUID y sello verificado devuelve el mapa confirmado sin reaplicar valores. Si una entrada externa sin UUID de lote produce exactamente el contenido ya importado, informar la coincidencia y permitir omitirla sin escribir. Para reutilizar correspondencias se exige un mapa verificable o revisión. En un lote nuevo, el vínculo automático requiere un mapa emitido por el servicio, persistido para la misma instalación y ligado al UUID y sello del lote. El mapa vincula cada fila concreta al UUID del tipo correcto. La edición gestionada prepara cambios sobre UUID y guarda el borrador y su mapa en metadatos privados de preparación, separados de los lotes aceptados. Sella el borrador antes de entregarlo y, si se interrumpe la entrega, conserva el mismo mapa solo para ese lote y contenido. Al aceptar el borrador, valida otra vez el sello contra el mapa privado y confirma el linaje junto con los cambios. Una restauración verificada recupera los mapas ya aceptados. Los borradores que no se recuperen requieren nueva revisión. Un UUID insertado en el JSON o un manifiesto de un lote anterior no acredita una copia editada externamente. La autenticación de un paquete no concede por sí sola autoridad para vincular registros.
5. En lotes sin mapa válido, usar la igualdad del registro completo para sugerir candidatos, incluso tras reordenarlo. Comparar huellas de registro, nombres, referencias, opciones y ubicación contra el último antecedente de cada UUID. Mostrar los cambios al operador. Un nombre, posición, ruta, ID nativo, similitud o igualdad de contenido puede aparecer en una fila nueva y no acredita continuidad. Requerir revisión explícita, individual o de un mapa visible completo. El operador elige vincular al UUID anterior, crear uno nuevo o excluir la fila justificadamente. Duplicados idénticos, sustituciones y correspondencias de varios a uno nunca se resuelven automáticamente. Si una persona autorizada tampoco puede comprobar la continuidad, no reutilizar un UUID. Mantener el conflicto bloqueante hasta resolver los vínculos y las referencias afectados.
6. Comparar el contenido de una fila vinculada con su antecedente y con la revisión vigente de la entidad. Conservar el UUID si hubo un cambio verificable. Cuando catálogo y JSON hayan cambiado desde el antecedente, aplicar una comparación de tres versiones: conservar cambios unilaterales o idénticos, y someter valores divergentes, cambios de destino y relaciones incompatibles a revisión. La aceptación de identidad no aprueba por sí sola cambios de configuración. Una ubicación nueva exige verificar el destino antes de admitir ejecuciones. Confirmar decisiones, correspondencias, actualizaciones y asociaciones en una transacción contra la revisión esperada. Una revisión obsoleta obliga a recomputar el plan y renovar la aprobación afectada. El reintento de una transacción interrumpida recupera el lote confirmado o repite el plan sin altas adicionales.
7. Resolver `repository` y `repositories` en el nuevo lote por nombres heredados exactos y sus correspondencias confirmadas, conservando el orden. Un destino ausente, repetido o ambiguo, o una discrepancia entre ambos formatos, impide la activación mientras siga pendiente. Revisar también colisiones de mayúsculas, Unicode y normalización del planificador sin alterar nombres originales ni resolver por similitud.

La huella de ubicación es una tupla versionada por backend. Preserva la raíz o el recurso compartido en rutas locales y UNC, y la semántica de ruta, bucket, prefijo o remoto en backends remotos. Normaliza solo equivalencias documentadas por el backend, como el caso de un host DNS. Excluye credenciales y evita resolver enlaces, alias DNS o unidades mapeadas con fines de identidad. Las rutas relativas sin base comprobada y los backends sin reglas suficientes requieren revisión. El JSON legado editado fuera del servicio puede carecer de toda evidencia de continuidad. En ese caso, la conservación del UUID depende de una correspondencia comprobada y aprobada, y no puede garantizarse automáticamente. [UUIDv5](https://www.rfc-editor.org/rfc/rfc9562.html#name-uuid-version-5)

## Contrato del servicio de dominio

GUI, CLI, importación, alta, desregistro, restauración y mantenimiento solicitan al mismo servicio las mutaciones operativas. El servicio es el único escritor autorizado del catálogo. Las reparaciones y transiciones tienen comandos explícitos del mismo servicio con acceso exclusivo. Cada conexión habilita claves foráneas antes de iniciar transacciones. Una mutación ordinaria verifica bajo bloqueo el par marcador/almacén, la autorización y las revisiones esperadas. En una sola transacción valida el estado previo, aplica el cambio, verifica las invariantes finales e incrementa las revisiones de las entidades afectadas y del catálogo. Un fallo revierte toda la mutación.

- Validar que los UUID existan y sean del tipo correcto, que el esquema, las opciones, los localizadores, las referencias y el orden sean válidos y que no se reaproveche un UUID para otra entidad. Rechazar importaciones o edición directa que intenten omitir estas comprobaciones.
- Validar exclusividad antes y después de convertir, transferir o archivar. La confirmación de impacto identifica propietario, destinos, posiciones y perfiles afectados para la revisión aprobada. Exigir propietario de destino no archivado, autorización de cada retiro y ajuste explícito de perfiles que pierdan destinos operables. Rechazar el archivado mientras el perfil conserve cualquier propiedad exclusiva, independientemente del estado del repositorio. Bloquear cambios incompatibles con operaciones ya admitidas. SQLite impone las restricciones estructurales y el servicio aplica las reglas de estado, autorización e impacto.
- Admitir ejecución solamente desde un par coherente y con un plan completo de una misma revisión. Resolver todos los destinos seleccionados, verificar estado y ubicación, y comprobar autenticación en el contexto de la cuenta que ejecutará la operación. Si un destino requerido está bloqueado, rechazar el plan antes de lanzar Restic. Reservar el plan bajo el mismo bloqueo para impedir cambios incompatibles entre la validación y la admisión. La coordinación general de ejecuciones corresponde a la fase 5. [Claves foráneas de SQLite](https://www.sqlite.org/foreignkeys.html)

## Registro, inicialización y desregistro

Registrar un repositorio existente conserva su ubicación y configuración y no ejecuta `restic init`. Si falta verificar su destino, el catálogo puede conservar el registro para revisión, con la ejecución bloqueada. El alta independiente y el asistente de perfiles pueden usar el mismo formulario. Para crear un destino exclusivo, guardar el perfil en borrador, el repositorio en `pending_init`, su ubicación y el vínculo en una sola transacción. Restic se invoca solo tras autorización explícita y fuera de esa transacción. Confirmado el resultado, otra transacción pasa el registro a `registered`. Si la aplicación cae después de iniciar, la recuperación verifica el estado del destino antes de completar el registro. Una discrepancia requiere revisión y no se vuelve a ejecutar `init` automáticamente.

Desregistrar cambia el estado a `unregistered`, conserva los vínculos para identificar perfiles afectados y preserva datos y credenciales del backend. El servicio rechaza la ejecución del perfil mientras haya una asociación seleccionada inválida. Un cambio de ubicación que no pueda acreditar continuidad se trata como conflicto o nuevo registro mediante una decisión explícita.

## Importación, activación y reversión

El catálogo en `staged` permite preparar lotes bajo control del servicio mientras JSON sigue siendo la única fuente operativa. La preparación conserva los valores de origen y los campos desconocidos en una copia local protegida. Solo tras resolver las asociaciones y los conflictos se puede solicitar la activación. Un único perfil asociado no demuestra exclusividad. El historial y las etiquetas de snapshots existentes conservan su valor histórico.

### Protocolo durable de transición

GUI, CLI y mantenimiento coordinan el acceso por directorio efectivo. Una transición adquiere un bloqueo interproceso exclusivo, impide nuevas admisiones y espera a que terminen las ya admitidas. El bloqueo de proceso desaparece al caer el proceso. El marcador externo persiste y obliga a recuperar el estado antes de escribir o ejecutar. Los binarios antiguos pueden ignorar ambos mecanismos. Se requiere evidencia de que están detenidos y de que sus vías de arranque fueron neutralizadas, incluidas tareas de respaldo y retención. Si esta evidencia falta o deja de ser vigente en el ámbito controlado, bloquear el corte o la reanudación.

| Paso durable | Operación y condición de avance |
|---|---|
| 1. Preparar | Bajo bloqueo exclusivo, resolver conflictos, comprobar la revisión y huella de origen, verificar tareas y capturar copias coherentes y verificadas. Escribir un manifiesto protegido con la dirección, el ID de transición, el estado operativo anterior, identidades, revisiones, evidencia de tareas y los hashes de entradas, copias y archivos preparados. Conservar evidencia y copias hasta confirmar el corte y cerrar la recuperación. |
| 2. Bloquear | Publicar el marcador `transition` con ID y referencia al manifiesto antes de tocar archivos operativos. Desde este punto se impiden mutaciones ordinarias y ejecución. |
| 3. Instalar | Para activar, confirmar modo `active` e ID en una transacción SQLite. Para revertir, instalar primero el JSON de exportación validado y confirmar después SQLite `staged` con el ID de reversión. Para restaurar, instalar cada archivo preparado bajo bloqueo, con SQLite cerrado y sin archivos WAL anteriores que puedan reaplicarse. La copia instalada confirma su modo e ID de destino en una transacción propia. Registrar un punto de avance por archivo o commit verificable. |
| 4. Verificar y publicar | Reabrir y comprobar modo, instalación, ID, revisiones y consistencia. Comparar las definiciones y el estado de los ejecutores con la evidencia vigente y confirmar que las rutas neutralizadas siguen inactivas. Publicar el marcador final `catalog` o `legacy` como última escritura que habilita operación. Reanudar solo consumidores compatibles, una vez verificado el par final. |

El marcador registra su formato, la instalación, el modo, el ID de transición y la referencia al manifiesto. Los reemplazos usan temporales del mismo volumen, vaciado de los datos y persistencia del cambio de nombre según la plataforma. La implementación deberá demostrar las garantías de ese mecanismo y del commit SQLite en los sistemas de archivos soportados. Si no puede confirmar la persistencia, no habilita ejecución. El manifiesto registra el avance después de cada operación. Al recuperar, se lee la evidencia observable antes de repetirla, incluso si la interrupción ocurrió entre completar un paso y registrar su avance. Los hashes verifican copias y archivos durante el corte. Tras publicar el marcador final, las escrituras normales pueden cambiar legítimamente la revisión y el hash.

| Estado observable | Recuperación |
|---|---|
| Marcador anterior y preparación incompleta | Mantener la fuente operativa anterior si el par es coherente. Revalidar o descartar la preparación, sin aplicar cambios parciales. Un alta inicial confirmada puede establecer `legacy` sin catálogo. Una instalación previa de modo desconocido exige recuperación explícita. |
| `transition` antes del primer reemplazo o commit | Revalidar todas las entradas y el inventario. Completar el cambio o verificar el par anterior y volver a publicar su marcador. |
| `transition` tras un reemplazo o commit | Comparar cada archivo, estado SQLite e ID con el paso previo y el preparado. Si coincide con un punto conocido, reanudar desde el siguiente paso o restaurar las copias anteriores completas y verificarlas antes de publicar el marcador anterior. Cualquier resultado inesperado queda bloqueado para reconciliación. |
| Marcador final | `catalog` exige SQLite `active` con la misma instalación e ID. `legacy` exige el JSON válido de la instalación y el catálogo `staged` del corte si existe. Un marcador ilegible o ausente fuera del alta inicial, una revisión incompatible o datos incoherentes bloquean mutaciones y ejecución. No se cambia automáticamente de fuente. |

### Reversión semántica y recuperación hacia adelante

Antes de activar, abandonar la preparación conserva JSON intacto. Después de activar, la reversión semántica exige una exportación desde la revisión vigente y autorización explícita. Comprobar equivalencia de asociaciones, orden, destinos, opciones y resolución de tareas con el lector que volverá a usarse. Si el formato anterior pierde exclusividad, identidad de una tarea u otros cambios posteriores, conservar ambas copias y recuperar hacia adelante sin habilitar operaciones hasta reconciliar el conflicto. Reinstalar un respaldo antiguo también exige revisar los cambios posteriores y autorizar el punto de retorno. Una reversión conserva los repositorios físicos y obliga a reconciliar los registros creados desde el corte antes de reanudar. El protocolo presupone almacenamiento local y control administrativo de los ejecutores inventariados.

## Tareas programadas y compatibilidad operativa

| Ruta heredada | Riesgo y tratamiento propuesto |
|---|---|
| Tarea Windows de un destino | El script puede ejecutar Restic directamente con destino y opciones incrustados, al margen del catálogo. Inventariar tarea, script y destino sin copiar secretos. Si la tarea puede seguir ejecutándose fuera del catálogo, bloquear la activación de esa configuración hasta una transición autorizada y comprobada que elimine ese acceso directo o lo deje inactivo. |
| Tarea Windows de varios destinos y cron | Invocan `--run-job` por nombre. En modo catálogo, la interfaz propuesta es `--run-job-id <UUID>`. El argumento heredado solo resuelve mediante un alias exacto registrado y aprobado para esa instalación, vinculado a un único UUID. Una colisión con otro alias o nombre vigente bloquea la resolución. Un alias desconocido, ambiguo, con propietario no ejecutable o cuyo destino no esté verificado falla antes de invocar Restic. El alias aprobado se reserva mientras exista la tarea, incluso si el nombre visible cambia. |
| Tareas de retención y otros scripts directos | Inventariarlos también cuando apuntan a repositorios afectados. Si dependen de rutas o credenciales generadas, aplicar la misma condición de activación. Renombrar el texto visible no valida su compatibilidad. |
| Tareas nuevas o reconfiguración del SO | El catálogo conserva la configuración heredada y presenta el estado de transición. La importación no crea, elimina ni rescribe tareas. Cualquier cambio del planificador requiere una operación separada, autorización y verificación de la ruta, cuenta, destino y argumentos efectivos. |

Inventariar tareas de backup y retención por cuenta, acciones, desencadenadores, estado y última ejecución. Resolver ejecutable, directorio de trabajo, scripts y argumentos efectivos, incluidas llamadas encadenadas, ruta de configuración, destino y referencias de credenciales. Registrar rutas o argumentos saneados y huellas de los scripts. Evitar volcar contraseñas, tokens o entornos completos. Comparar el ámbito afectado con los UUID de catálogo y detectar colisiones de nombres de tarea, incluido el reemplazo de espacios por guiones bajos.

Con autorización separada, deshabilitar o sustituir las entradas directas, comprobar que no quedan instancias activas o encoladas y verificar que los scripts obsoletos no tengan una vía de lanzamiento dentro del ámbito controlado. Para cada entrada que se mantiene, demostrar que llama a la versión nueva, usa el mismo directorio efectivo y resuelve por UUID o alias verificado y reservado. Volver a leer el inventario antes de publicar el marcador final. Inventario incompleto, cuenta sin acceso, lanzador desconocido, tarea activa fuera del catálogo o definición modificada desde el inventario bloquean el corte. Deshabilitar internamente un perfil no neutraliza un script directo. El control abarca ejecutores inventariados bajo administración de la instalación. Un administrador que reactive rutas antiguas fuera de ese control puede saltarlo. La fase 4 define la condición de activación y la compatibilidad. El rediseño del programador corresponde a fases posteriores. [Programador Windows](../restic_manager.py#L4412) · [Cron](../restic_manager.py#L5007) · [Retención](../restic_manager.py#L13030) · [CLI heredado](../restic_manager.py#L15513)

## Consistencia de respaldo y restauración

### F4-02 — Formato criptográfico y clave de recuperación

El formato portable propuesto `RDCATBKP` v1 se exporta desde un catálogo activo y estable. Usa AES-256-GCM de la dependencia `cryptography` ya fijada. Cada paquete se cifra una sola vez con una clave de 32 bytes y un nonce de 12 bytes, ambos generados con el CSPRNG del sistema. Un reintento genera un par nuevo. La cabecera fija contiene, en este orden, el identificador ASCII `RDCATBKP` (8 bytes), la versión `1` (entero de 16 bits), un identificador de paquete UUIDv4 (16 bytes en orden de red), el nonce y el tamaño del texto cifrado incluido el tag (entero de 64 bits). Los enteros se codifican en big endian. La cabecera completa, sin reserializar, se autentica como datos AEAD asociados. A continuación van el texto cifrado y el tag de 16 bytes que devuelve `AESGCM`. El lector exige la longitud exacta y un máximo de 256 MiB de texto claro en v1 antes de reservar memoria o descifrar. Si el historial excede el límite se puede volver a exportar sin él con consentimiento, dejando constancia. [API AESGCM](https://cryptography.io/en/46.0.5/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM) · [NIST SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final)

El texto claro contiene la longitud del manifiesto (entero big endian de 32 bits), el manifiesto JSON UTF-8 y los bytes de cada componente concatenados en el orden listado. El manifiesto exige versión, UUID de paquete e instalación, versión de esquema, modo, revisión, ID del último corte y fecha UTC. Cada componente tiene tipo, tamaño y SHA-256. Aceptar únicamente modo `catalog` y los tipos únicos `catalog`, `preferences` y, si existe, `history`, en ese orden. Catálogo y preferencias son obligatorios. El manifiesto se limita a 1 MiB. Validar delimitación exacta, límites, tipos y ausencia de claves duplicadas. No se aceptan rutas de extracción. La autenticidad e integridad criptográficas provienen del tag, comprobado antes de interpretar el manifiesto o abrir SQLite. Los hashes sirven además para cotejar archivos en preparación e instalación. El formato aporta autenticidad frente a terceros sin clave. La posesión de la clave permite abrir y falsificar el paquete y no acredita por sí sola al autor ni la vigencia de la copia.

La clave se entrega como registro de recuperación `rdcat1:<uuid canónico del paquete>:<32 bytes en base64url sin padding>`. El registro se guarda separadamente del paquete en un almacén controlado por el usuario, fuera del equipo de origen para permitir recuperación ante pérdida de ese equipo. No se deriva de una contraseña ni depende del inicio de sesión de la aplicación, DPAPI, llavero o acceso al equipo de origen. Para declarar el respaldo recuperable, el usuario confirma la custodia y el exportador relee el paquete con el registro exportado, verifica el tag y comprueba el manifiesto antes de publicar la copia final. No almacenar la clave junto al paquete ni registrarla en logs. La pérdida de todas sus copias impide recuperar el paquete.

Para rotar la clave de una copia retenida, autenticarla con el registro anterior y reexportar el contenido completo con un nuevo UUID, clave y nonce. Verificar la nueva pareja antes de retirar la anterior. Las copias antiguas conservan su clave original mientras se necesiten. La rotación no retira acceso a copias ya obtenidas por terceros. En otra máquina, importar paquete y clave por separado, comprobar UUID, autenticar y presentar instalación y revisión para confirmación. En una recuperación de la misma instalación se conservan los UUID y el linaje de importación. Si el equipo de destino ya tiene otro catálogo, bloquear el reemplazo automático. Restaurar una revisión antigua exige reconciliar o autorizar expresamente la pérdida de cambios posteriores.

### Consistencia y tratamiento de credenciales

Tomar la revisión del catálogo y las preferencias bajo el mismo bloqueo, usando la API de respaldo de SQLite. El historial opcional registra su propio punto de captura si no comparte el del catálogo. El paquete incluye referencias opacas de credenciales, sus requisitos de resolución y las decisiones de linaje aceptadas. Verificar que los componentes saneados representen la misma revisión y permitan reconstruir asociaciones y linaje. Excluye contraseñas Restic, tokens, claves de backend, variables secretas, material DPAPI o de llavero y archivos como `rclone.conf` que puedan contener secretos. También excluye copias crudas de JSON legado. Construir componentes portables desde campos permitidos y desde el linaje saneado. Los campos desconocidos se conservan localmente para revisión, fuera del paquete. Si un campo requerido o un historial solicitado no puede exportarse sin riesgo de incluir secretos, informar la omisión solicitando confirmación, o rechazar el respaldo si no queda una copia recuperable. La copia saneada se construye en una base limpia para evitar exportar valores antiguos mediante WAL o páginas libres. Las copias locales de recuperación que preserven bytes originales siguen bajo permisos restringidos y fuera del formato portable. [API de respaldo de SQLite](https://sqlite.org/backup.html)

Restaurar a un área de preparación protegida. Comprobar esquema soportado, instalación, revisión, modo, referencias, exclusividad, `integrity_check` y `foreign_key_check`. Autenticar el paquete no autoriza instalación. El servicio solicita aprobación del punto de restauración y aplica el protocolo durable, con marcador nuevo e inventario de tareas del destino. El catálogo puede restaurarse aunque falten credenciales Restic. En otra máquina, volver a verificar localizadores y referencias antes de habilitar cualquier destino. Mientras falte esa verificación, mantenerlo bloqueado para la ejecución. Una referencia solo se resuelve con el proveedor de credenciales y la cuenta de ejecución previstos. Para habilitar el destino, reautenticar en esa cuenta y comprobar el ID Restic esperado mediante una comprobación de solo lectura. Si no hay identidad esperada verificable, exigir revisión explícita del destino. Una contraseña vacía o credenciales de otro registro no suplen una referencia faltante. La restauración no activa tareas del SO. Los paquetes heredados siguen sujetos a su lector y a una importación en preparación con los mismos controles. Un fallo de autenticación de v1 no vuelve a intentar la apertura como formato legado.

## Implementación y criterios de aceptación

1. Implementar dominio y almacenamiento Python sin Qt. Probar claves foráneas, exclusividad, destinos compartidos, renombres, orden y escrituras concurrentes con SQLite temporal.
2. Construir el importador en preparación y la exportación de reversión. Probar ambos formatos de destino, JSON inválido, campos desconocidos, ambigüedades, reintentos, fallos parciales y una modificación posterior a la activación.
3. Conectar el alta independiente, el asistente y el desregistro. Probar con procesos simulados que registrar y desregistrar no inicialicen ni borren un repositorio. Probar recuperación ante interrupciones del alta exclusiva.
4. Integrar GUI y CLI con selección por UUID y resolución heredada controlada. Probar tareas simuladas con nombres, rutas explícitas o incrustadas, cuentas y configuraciones incompatibles. Verificar que un vínculo inválido no redirija la ejecución ni lance una parte de los destinos.
5. Verificar el respaldo y la restauración de configuración con y sin historial, y la activación y vuelta con datos desechables. Mantener el historial v3 y aislar las atribuciones antiguas ambiguas.

| Capa | Garantía prevista y prueba futura |
|---|---|
| DDL SQLite | Con claves foráneas habilitadas, `COMMIT` rechaza un exclusivo sin vínculo a su propietario, borrar ese vínculo de forma aislada o referenciar una entidad inexistente. Los triggers rechazan vínculos ajenos y la asignación de un propietario cuando permanecen otros vínculos. Verificar unicidad de asociaciones, posiciones y vínculos por lote. Probar también que un antecedente apunte a una correspondencia existente del mismo tipo y UUID. |
| Servicio de dominio | Verificar en cada entrada de escritura las revisiones, la autorización, las transiciones y su efecto sobre el perfil. Probar que una conversión a compartido conserva la asociación, posición y UUID, y que una transferencia o cambio de ubicación fallido revierte todos los cambios. Probar el rechazo del archivado para exclusivos registrados, pendientes o desregistrados sin alterar el catálogo ni su revisión, y el archivado tras transferirlos o compartirlos explícitamente, conservando las asociaciones restantes y los datos físicos. Probar que un perfil con un destino requerido bloqueado no ejecuta un subconjunto. |
| Servicio de importación | Probar igualdad frente a cambios de formato y reintento exacto sin reescritura, reordenamiento gestionado y externo, cambios de nombre, opciones, ubicación o destino, y edición simultánea en JSON y SQLite. Un mapa válido conserva UUID. Un mapa alterado, de otra instalación o lote, un reemplazo por fila idéntica o una coincidencia múltiple exigen revisión. Probar correspondencia autorizada después de modificar contenido, alta independiente, ausencia temporal y reaparición, y que ninguna ruta asigne el mismo UUID a dos filas del mismo tipo y lote. Un fallo antes o después del commit no deja altas ni correspondencias parciales. |
| Integración de transición | Inyectar fallos antes y después de cada reemplazo, commit y publicación, incluidos los fallos entre aplicar un paso y registrar su avance. Simular escritores concurrentes, lectura de marcador incoherente y operaciones ya admitidas. Reiniciar GUI y CLI y comprobar que, sin par coherente, no escriben ni ejecutan. Probar en los sistemas de archivos soportados y comprobar el rechazo cuando la durabilidad no se pueda garantizar. |
| Integración de tareas | Simular backup y retención directos, tareas activas o encoladas, cuenta inaccesible, script modificado después del inventario, otro directorio de configuración y alias ambiguo o reservado. Cualquier bypass vigente bloquea el corte. Con el inventario verificado, un UUID resuelve solo el perfil, las asociaciones y los destinos vigentes. |
| Integración de formato y claves | Usar un vector fijo de interoperabilidad y comprobar ida y vuelta con y sin historial. Alterar cabecera, nonce, ciphertext y tag. Probar longitud manipulada, truncamiento, bytes extra, versión desconocida, clave incorrecta y manifiesto autenticado inválido. Verificar que se rechacen antes de instalar y que un error de v1 no abra el lector legado. Probar reintentos con claves frescas y rotación verificada. Solo la clave antigua abre la copia antigua y solo la nueva abre la nueva. |
| Integración de restauración | Restaurar en otra máquina sin acceso a llavero, DPAPI ni equipo original. Comprobar ausencia de secretos y páginas residuales en los componentes exportados. Probar mezcla de revisiones, copia antigua, destino con otro catálogo, referencias o localizadores ausentes y credenciales ligadas al equipo de origen. Restaurar UUID, linaje, exclusividad y orden con destinos bloqueados hasta reautenticación y verificación. Comprobar que no se habiliten tareas del SO y que una copia inválida preserve la instalación anterior. |
| Integración de rollback | Verificar equivalencia al volver a JSON con cambios representables. Con cambios no representables, conservar ambos almacenes y bloquear el rollback semántico. Probar recuperación hacia adelante tras una interrupción sin reinicializar ni eliminar repositorios. |

La revisión actual es de diseño. Las garantías del DDL son estructurales y dependen de conexiones con claves foráneas habilitadas. Las decisiones de identidad, credenciales, autorización y admisión corresponden al servicio. Las pruebas de integración verifican los límites entre procesos, archivos, almacenes y tareas. Se ejecutarán al implementar la fase.

## Decisiones abiertas para aprobación

- Aprobar el catálogo separado, el reparto entre SQLite y JSON y la política de referencias opacas con reautenticación. Aprobar el formato portable v1, las claves individuales custodiadas por el usuario, el límite de 256 MiB y la exclusión de secretos y copias crudas. Una pérdida de la clave impide recuperar su paquete y una filtración permite abrirlo o falsificarlo.
- Aprobar la revisión obligatoria para reimportaciones externas sin mapa verificable y el registro persistente de linaje. El JSON antiguo puede carecer de evidencia suficiente para conservar una identidad sin información externa.
- Aprobar las plataformas y sistemas de archivos donde se verificará el protocolo durable, y el procedimiento administrativo de neutralización, activación y reversión de ejecutores heredados. El diseño presupone control sobre el ámbito inventariado y no puede impedir que un administrador habilite rutas antiguas fuera de él.
- Confirmar si la validación POSIX pendiente, H1.3 o H3 condicionan la activación de la fase 4. El roadmap sí exige terminación segura antes de automatizar el apagado. El alcance del catálogo conserva el comportamiento de H3.
