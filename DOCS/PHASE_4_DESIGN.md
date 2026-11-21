# Diseño de la fase 4 de Restic Desktop

**Propuesta para auditoría.** La fase 4 separa perfiles y repositorios, estabiliza sus identidades y prepara una transición reversible desde JSON a SQLite. La propuesta está pendiente de aprobación. La base de código analizada es `38d87c81a337926c6be31b29d257abb894158d70` en `codex/initial-restic-foundation`. El informe no activa el catálogo ni cambia el comportamiento de la aplicación.

## Alcance y evidencia en el código

- `ResticSettingsManager` guarda `repositories` y `backup_jobs` en `restic_settings.json` junto con preferencias. El trabajo es el antecedente del perfil. Conserva orígenes, etiquetas, exclusiones, opciones de Restic, programación y referencias por nombre. Conviven `repository` y `repositories`. La escritura actual reemplaza el JSON completo. [Configuración](../restic_manager.py#L4260) · [Formulario del trabajo](../restic_manager.py#L3970)
- La interfaz, el CLI, el historial y el programador dependen de nombres visibles. La resolución heredada toma el primer repositorio con el nombre buscado. Renombrar, desregistrar o duplicar un nombre puede romper o desviar referencias. El asistente de respaldo ya abre el formulario de repositorio, así que puede reutilizarse para crear y vincular destinos por UUID. [Desregistro y edición](../restic_manager.py#L6505) · [Resolución heredada](../restic_manager.py#L6798) · [Asistente](../ui/backup_wizard.py#L174)
- `restic_history.db` tiene un esquema v3 con historial, estadísticas, caché y logs. Sus nombres históricos son etiquetas. Una coincidencia por nombre, etiqueta o ruta no demuestra la identidad de una ejecución anterior. [Esquema](../core/history_db.py#L61) · [Asociación de snapshots](../restic_manager.py#L2033)
- La fase 4 comprende catálogo, relaciones, operaciones de registro e importación. La coordinación de ejecuciones corresponde a la fase 5 y la automatización de Windows a la fase 8. H3 conserva su estado y su política de parada. [Hoja de ruta](IMPLEMENTATION_ROADMAP.md#fase-4--modelo-de-dominio-y-persistencia-de-perfilesrepositorios)

## Entidades, relaciones y opciones de almacenamiento

**Perfil.** UUID local estable, nombre visible, configuración de respaldo, revisión y estado. Puede guardarse en borrador sin destino. Su activación y cada admisión de ejecución requieren al menos un destino habilitado. Se valida el conjunto completo antes de lanzar el primer respaldo.

**Repositorio.** UUID local estable, nombre visible, revisión, estado de registro y propietario exclusivo opcional. Un repositorio compartido puede existir sin perfiles. Uno exclusivo solo puede estar asociado al perfil propietario. Un perfil puede tener combinaciones de destinos compartidos y exclusivos en un orden explícito. Se conserva el registro al desregistrar, incluidas sus relaciones, y se bloquea la ejecución de perfiles que dependan de ese destino. Se permite archivarlo junto con su propietario sin convertirlo en compartido. Compartirlo o reasignarlo requiere una modificación explícita y validada.

**Ubicación.** Cada registro tiene una ubicación activa antes de poder ejecutarse. El backend, el localizador, sus parámetros y la referencia de autenticación se editan de forma separada del UUID. La huella de ubicación sirve para buscar candidatos a duplicado. El ID nativo de Restic, cuando se verifica, sirve como evidencia adicional y no es clave primaria. Dos rutas pueden conducir al mismo repositorio, y dos copias en ubicaciones diferentes pueden conservar el mismo ID nativo. Ninguna coincidencia autoriza fusionar, mover ni elegir un destino por sí sola. Un cambio de destino exige verificar su identidad antes de permitir operaciones.

**Persistencia.** Se propone un catálogo SQLite local separado del historial, con un servicio Python compartido por Qt y el CLI. Guardar UUID en el JSON existente reduce el trabajo inicial pero obliga a resolver por fuera del almacén las relaciones, las escrituras simultáneas y los reemplazos completos. Usar el SQLite de historial simplifica la cantidad de archivos, pero acopla la configuración esencial con una base cuyo respaldo es opcional y cuya restauración hoy puede reemplazarla. El catálogo separado introduce una pieza que debe incluirse siempre en el respaldo de configuración cuando esté activo. JSON conserva preferencias generales y la configuración necesaria para el modo heredado. [Configuración](../restic_manager.py#L4260) · [Respaldo y restauración](../restic_manager.py#L14166)

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
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)
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
    import_source_fingerprint TEXT
);

CREATE TABLE legacy_profiles (
    source_key TEXT NOT NULL PRIMARY KEY,
    legacy_name TEXT NOT NULL,
    profile_id TEXT NOT NULL UNIQUE
        REFERENCES profiles(profile_id) ON DELETE RESTRICT
);

CREATE TABLE legacy_repositories (
    source_key TEXT NOT NULL PRIMARY KEY,
    legacy_name TEXT NOT NULL,
    repository_id TEXT NOT NULL UNIQUE
        REFERENCES repositories(repository_id) ON DELETE RESTRICT
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

INSERT INTO catalog_state (singleton, mode) VALUES (1, 'staged');
PRAGMA user_version = 1;
COMMIT;
```

Las restricciones controlan integridad referencial, orden, duplicados de asociación y exclusividad. El servicio valida la forma del UUID, la configuración, la existencia de una ubicación, las colisiones con otros registros y la preparación del perfil para ejecutar. Los nombres visibles y las huellas son índices de búsqueda. Los casos ambiguos conservan su identidad hasta que el operador resuelva la coincidencia. Las correspondencias heredadas representan registros importados a partir de una copia con huella conocida. `source_key` identifica su posición dentro de esa copia mediante una clave opaca y determinista. Reimportar la misma copia reutiliza los UUID. Una copia distinta vuelve a revisión y exige resolver diferencias antes de activarse.

Cada conexión habilita claves foráneas. Las mutaciones usan transacciones cortas y revisión esperada para detectar ediciones obsoletas, incluidas las de una asociación o ubicación. El servicio lee y valida el plan de ejecución completo de una sola versión del catálogo. La transacción del catálogo protege su consistencia local. Coordinar respaldos concurrentes y operaciones incompatibles sobre un mismo repositorio pertenece a la fase 5. [Claves foráneas de SQLite](https://www.sqlite.org/foreignkeys.html)

## Registro, inicialización y desregistro

Registrar un repositorio existente conserva su ubicación y configuración y no ejecuta `restic init`. Si falta verificar su destino, el catálogo puede conservar el registro para revisión, con la ejecución bloqueada. El alta independiente y el asistente de perfiles pueden usar el mismo formulario. Para crear un destino exclusivo, primero se guarda el perfil en borrador. Se registra la intención de inicializar con su UUID de repositorio y estado `pending_init`, y se llama a Restic solo tras autorización explícita. La inicialización externa ocurre fuera de la transacción SQLite. Confirmado el resultado, una transacción completa el registro y el vínculo. Si la aplicación cae después de iniciar, la recuperación verifica el estado del destino antes de completar el registro. Una discrepancia requiere revisión y no se vuelve a ejecutar `init` automáticamente.

Desregistrar cambia el estado a `unregistered`, conserva los vínculos para identificar perfiles afectados y preserva datos y credenciales del backend. El servicio rechaza la ejecución del perfil mientras haya una asociación seleccionada inválida. Un cambio de ubicación que no pueda acreditar continuidad se trata como conflicto o nuevo registro mediante una decisión explícita.

## Importación, activación y reversión

1. **Inventario en solo lectura.** Identificar la ruta efectiva de configuración de GUI, CLI y tareas. Validar estrictamente una copia del JSON, distinguir archivo inválido de catálogo vacío y detectar destinos ausentes, nombres ambiguos, asociaciones contradictorias y colisiones de tareas. Mantener disponibles la copia original, el historial y las referencias cifradas. Proteger los archivos de respaldo y evitar material de autenticación en logs, informes o el catálogo.
2. **Importación en preparación.** SQLite se llena desde la copia del JSON sin convertirse en la fuente operativa. Preservar opciones, campos desconocidos, nombres, orden de destinos y programación. Usar `repositories` cuando la lista sea válida y no vacía, y el formato singular cuando corresponda. Ante referencias ambiguas, destinos duplicados o discrepancias entre ambos formatos, conservar el valor original en la copia y señalar el conflicto por clave de origen en la revisión previa. El importador solo materializa relaciones inequívocas. La instalación sigue en modo heredado mientras haya conflictos sin resolución. Un solo perfil asociado no demuestra exclusividad. Los nombres del historial y las etiquetas de snapshots existentes se conservan como evidencia histórica.
3. **Activación explícita por configuración.** La propuesta usa un marcador de modo por instalación, fuera de SQLite y separado del JSON que reescribe la versión antigua. Antes del cambio se detienen escritores y tareas incompatibles y se verifica una copia coordinada de ambos almacenes. Con la huella de origen vigente, los conflictos resueltos y las tareas verificadas, se escribe el marcador `transition` por reemplazo atómico. La GUI y el CLI con soporte de catálogo bloquean cambios y ejecuciones durante ese modo. Después se confirma `active` en SQLite y se publica el marcador `catalog`. Solo ese par habilita el catálogo. Una interrupción, un catálogo ilegible o un desacuerdo de estados requiere recuperación explícita. La ausencia de marcador con un catálogo activo se considera incoherente. El modo antiguo solo puede usarse durante el corte después de comprobar que ningún ejecutable o script anterior pueda saltarse el marcador. No hay escritura simultánea de perfiles o repositorios en JSON y SQLite.
4. **Respaldo de configuración.** Cuando SQLite esté activo, el catálogo forma parte del respaldo de configuración independientemente de si el usuario incluye historial. Usar la API de copia coherente de SQLite y coordinar la versión exportada del catálogo con la de la configuración y sus referencias. Al restaurar, validar formato, integridad y compatibilidad antes de activar la copia. Las credenciales ligadas a otra máquina que no puedan resolverse requieren reautenticación. [API de respaldo de SQLite](https://sqlite.org/backup.html)
5. **Reversión.** Antes de activar, volver al flujo heredado conserva intacto el JSON original. Después de activar, detener escritores y conservar copias de ambos almacenes. Construir una exportación heredada desde la revisión vigente del catálogo y comparar opciones, asociaciones, ubicaciones y tareas. Si hay cambios que el formato anterior no puede representar, incluida exclusividad que el lector antiguo no puede hacer cumplir o identidades históricas ambiguas, detener la reversión y conservar ambas copias. Si la exportación es fiel, usar `transition`, instalar el JSON validado por reemplazo atómico, devolver SQLite al modo `staged` y publicar el marcador `legacy`. Solo después se reanudan los consumidores compatibles. Una interrupción mantiene el bloqueo hasta comparar las copias y completar o deshacer la transición. La reversión del catálogo conserva los repositorios físicos creados después de activar. Sus registros deben reconciliarse antes de reanudar la ejecución.

## Tareas programadas y compatibilidad operativa

| Ruta heredada | Riesgo y tratamiento propuesto |
|---|---|
| Tarea Windows de un destino | El script puede ejecutar Restic directamente con destino y opciones incrustados, al margen del catálogo. Inventariar tarea, script y destino sin copiar secretos. Si la tarea puede seguir ejecutándose fuera del catálogo, bloquear la activación de esa configuración hasta una transición autorizada y comprobada que elimine ese acceso directo o lo deje inactivo. |
| Tarea Windows de varios destinos y cron | Invocan `--run-job` por nombre. Mantener la entrada antigua como resolución de compatibilidad solo si el nombre identifica un UUID inequívoco, el proceso abre la configuración correcta y respeta la admisión del catálogo. Reservar los alias necesarios mientras exista la tarea. Un alias ambiguo, reservado o ausente provoca un error explícito y no resuelve por primera coincidencia. |
| Tareas de retención y otros scripts directos | Inventariarlos también cuando apuntan a repositorios afectados. Si dependen de rutas o credenciales generadas, aplicar la misma condición de activación. Renombrar el texto visible no valida su compatibilidad. |
| Tareas nuevas o reconfiguración del SO | El catálogo conserva la configuración heredada y presenta el estado de transición. La importación no crea, elimina ni rescribe tareas. Cualquier cambio del planificador requiere una operación separada, autorización y verificación de la ruta, cuenta, destino y argumentos efectivos. |

La activación o reversión no basa sus garantías en deshabilitar internamente un perfil que un script directo puede ignorar. El inventario incluye colisiones de nombres de tarea y diferencias de rutas efectivas o directorio de trabajo. Si no se puede probar el enlace, la configuración permanece en modo heredado. No se cambia la política de parada ni se adelanta la automatización de Windows. [Programador Windows](../restic_manager.py#L4412) · [Cron](../restic_manager.py#L5007) · [Retención](../restic_manager.py#L13030) · [CLI heredado](../restic_manager.py#L15513)

## Implementación y criterios de aceptación

1. Implementar dominio y almacenamiento Python sin Qt. Probar claves foráneas, exclusividad, destinos compartidos, renombres, orden y escrituras concurrentes con SQLite temporal.
2. Construir el importador en preparación y la exportación de reversión. Probar ambos formatos de destino, JSON inválido, campos desconocidos, ambigüedades, reintentos, fallos parciales y una modificación posterior a la activación.
3. Conectar el alta independiente, el asistente y el desregistro. Probar con procesos simulados que registrar y desregistrar no inicialicen ni borren un repositorio. Probar recuperación ante interrupciones del alta exclusiva.
4. Integrar GUI y CLI con selección por UUID y resolución heredada controlada. Probar tareas simuladas con nombres, rutas explícitas o incrustadas, cuentas y configuraciones incompatibles. Verificar que un vínculo inválido no redirija la ejecución ni lance una parte de los destinos.
5. Verificar el respaldo y la restauración de configuración con y sin historial, y la activación y vuelta con datos desechables. Mantener el historial v3 y aislar las atribuciones antiguas ambiguas.

La fase se considera verificable cuando renombrar conserva IDs y relaciones, la exclusividad se exige en el catálogo, registrar y desregistrar preservan el repositorio y el cambio de modo no pierde cambios ni desvía una tarea. El modelo debe poder recuperarse de una importación interrumpida, un conflicto concurrente o un alta física completada sin su registro local.

El DDL de esta propuesta se ejecutó en memoria con SQLite 3.50.4. Se verificaron claves foráneas, destinos compartidos, rechazo de asociaciones exclusivas indebidas en altas y ediciones, protección del cambio de propietario, orden único y conservación de vínculos al renombrar. La activación, la reversión y la compatibilidad con tareas todavía son escenarios de prueba del plan.

## Decisiones abiertas para aprobación

- Aprobar el catálogo separado, el reparto entre SQLite y JSON y el almacenamiento de referencias de autenticación.
- Aprobar reglas de duplicados y qué hacer con un destino exclusivo al archivar o reasignar su propietario.
- Aprobar el criterio de activación y la transición de tareas que ejecutan Restic directamente, además del procedimiento de reversión para casos que el formato anterior no representa.
- Confirmar si la validación POSIX pendiente, H1.3 o H3 condicionan la activación de la fase 4. El roadmap establece la terminación segura como prerrequisito para automatizar el apagado. El alcance del catálogo no incluye rediseñar H3.
