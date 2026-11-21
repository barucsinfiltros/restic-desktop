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

## Invariantes y transiciones de exclusividad

Un repositorio con propietario exclusivo conserva exactamente una asociación con ese propietario, incluso en estado `pending_init` o `unregistered`. La asociación registra pertenencia y orden. La admisión de ejecución exige además que el perfil esté activo, el repositorio esté registrado y el destino y sus credenciales estén verificados.

| Operación explícita | Resultado al confirmar la transacción |
|---|---|
| Crear exclusivo para P | Crear registro y asociación P en la misma transacción. La asociación existe desde la reserva del alta, antes de inicializar el destino. |
| Compartido → exclusivo de P | Exigir P no archivado y autorización explícita si hay otros perfiles vinculados. Mostrar y retirar los vínculos aprobados, corregir o pasar a borrador los perfiles que queden sin destinos operables, y fijar propietario y vínculo P. Sin autorización se conserva el estado anterior. |
| Exclusivo de P → compartido | Eliminar el propietario y conservar la asociación P, su posición y el UUID del repositorio. Añadir otros perfiles requiere acción separada. |
| Exclusivo de P → exclusivo de Q | Exigir Q no archivado y confirmar el impacto en P. Retirar el vínculo P, cambiar el propietario y añadir Q en una sola transacción, con posición válida para Q. Si P queda sin destinos operables, pasa a borrador. |
| Desregistrar o archivar un perfil | Desregistrar conserva propietario y asociaciones y bloquea la admisión de los perfiles afectados. Archivar el perfil conserva sus vínculos y deja sus exclusivos inaccesibles para ejecución hasta una decisión explícita. |

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

CREATE TABLE legacy_profiles (
    import_fingerprint TEXT NOT NULL,
    source_key TEXT NOT NULL,
    legacy_name TEXT NOT NULL,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    PRIMARY KEY (import_fingerprint, source_key),
    UNIQUE (import_fingerprint, profile_id)
);

CREATE TABLE legacy_repositories (
    import_fingerprint TEXT NOT NULL,
    source_key TEXT NOT NULL,
    legacy_name TEXT NOT NULL,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    PRIMARY KEY (import_fingerprint, source_key),
    UNIQUE (import_fingerprint, repository_id)
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

1. Abrir una copia protegida del JSON y validar tipo de raíz, colecciones y registros. Rechazar claves duplicadas y valores no finitos. Conservar los bytes originales para recuperación. SHA-256 de esos bytes identifica una copia exacta. Una segunda huella describe el contenido canónico del lote y permite reconocer cambios de formato.
2. Para la huella canónica, serializar en UTF-8, ordenar las claves de objetos por sus puntos de código Unicode y eliminar el espacio sintáctico. Representar números por signo, coeficiente decimal sin ceros redundantes y exponente normalizado, con un solo valor para cero. Conservar los tipos JSON, los valores de texto sin normalización Unicode, los campos desconocidos y el orden de arrays. Usar una versión fija de canonicalización en el manifiesto. Las huellas de copias completas se guardan en metadatos privados de importación.
3. Dentro de una copia canónica sellada, `source_key` es el tipo y el índice original del registro. Para cada alta aprobada sin correspondencia previa, asignar UUIDv5 con el UUID persistente de instalación como espacio de nombres y el tipo, la huella del lote y la clave de origen como nombre. Confirmar juntos los registros, las asociaciones y las correspondencias. Después del alta, el UUID persiste al editar, renombrar o cambiar de orden. La posición de una copia nueva nunca se usa para identificar un registro anterior.
4. Repetir el mismo lote reutiliza sus correspondencias. Para un lote nuevo, primero usar un UUID exportado por el propio catálogo de la misma instalación, si existe y es válido. Si falta, un registro completo e idéntico que aparece una sola vez en ambas copias puede reutilizar la correspondencia, aunque haya cambiado de posición. El resto requiere una decisión explícita de vincular a un UUID, crear uno nuevo o conservarlo fuera del catálogo. Nombres, rutas y huellas de ubicación sirven como candidatos de revisión. La igualdad entre IDs nativos de Restic tampoco confirma una fusión. Ante registros idénticos duplicados, destinos ausentes, coincidencias múltiples o cambios de nombre sin correspondencia probada, conservar el original y bloquear la activación hasta resolverlos.
5. Resolver `repository` y `repositories` contra los nombres heredados exactos dentro del mismo lote, con orden conservado. Si ambos están presentes y declaran destinos incompatibles, si un nombre no es único o si se repite un destino, informar el conflicto. Las variantes de mayúsculas, Unicode y nombres normalizados del planificador se revisan para detectar colisiones. No alteran los nombres originales ni autorizan una coincidencia de respaldo.

La huella de ubicación se calcula sobre una tupla estructurada y versionada por backend. Para rutas locales o UNC se conserva el volumen o servidor y la raíz del recurso. Las rutas relativas sin base comprobada requieren revisión. Para REST, SFTP, rclone y almacenamiento de objetos se separan los componentes conocidos y se preservan capitalización y semántica de la ruta remota, nombre de remoto, bucket o prefijo. Solo se normaliza lo que el backend trate como equivalente, como el caso de un host DNS. Se excluyen credenciales y no se resuelven enlaces, alias DNS ni unidades mapeadas para fusionar registros. Los backends sin reglas suficientes conservan la representación original como candidato a revisar.

Cada conexión habilita claves foráneas. Las mutaciones usan transacciones cortas y revisión esperada para detectar ediciones obsoletas, incluidas las de una asociación o ubicación. El servicio lee y valida el plan de ejecución completo de una sola versión del catálogo. La transacción del catálogo protege su consistencia local. Coordinar respaldos concurrentes y operaciones incompatibles sobre un mismo repositorio pertenece a la fase 5. [Claves foráneas de SQLite](https://www.sqlite.org/foreignkeys.html)

## Registro, inicialización y desregistro

Registrar un repositorio existente conserva su ubicación y configuración y no ejecuta `restic init`. Si falta verificar su destino, el catálogo puede conservar el registro para revisión, con la ejecución bloqueada. El alta independiente y el asistente de perfiles pueden usar el mismo formulario. Para crear un destino exclusivo, guardar el perfil en borrador, el repositorio en `pending_init`, su ubicación y el vínculo en una sola transacción. Restic se invoca solo tras autorización explícita y fuera de esa transacción. Confirmado el resultado, otra transacción pasa el registro a `registered`. Si la aplicación cae después de iniciar, la recuperación verifica el estado del destino antes de completar el registro. Una discrepancia requiere revisión y no se vuelve a ejecutar `init` automáticamente.

Desregistrar cambia el estado a `unregistered`, conserva los vínculos para identificar perfiles afectados y preserva datos y credenciales del backend. El servicio rechaza la ejecución del perfil mientras haya una asociación seleccionada inválida. Un cambio de ubicación que no pueda acreditar continuidad se trata como conflicto o nuevo registro mediante una decisión explícita.

## Importación, activación y reversión

1. **Inventario en solo lectura.** Identificar la ruta efectiva de configuración de GUI, CLI y tareas. Validar estrictamente una copia del JSON, distinguir archivo inválido de catálogo vacío y detectar destinos ausentes, nombres ambiguos, asociaciones contradictorias y colisiones de tareas. Mantener disponibles la copia original, el historial y las referencias cifradas. Proteger los archivos de respaldo y evitar material de autenticación en logs, informes o el catálogo.
2. **Importación en preparación.** SQLite se llena desde la copia del JSON sin convertirse en la fuente operativa. Preservar opciones, campos desconocidos, nombres, orden de destinos y programación. Usar `repositories` cuando la lista sea válida y no vacía, y el formato singular cuando corresponda. Ante referencias ambiguas, destinos duplicados o discrepancias entre ambos formatos, conservar el valor original en la copia y señalar el conflicto por clave de origen en la revisión previa. El importador solo materializa relaciones inequívocas. La instalación sigue en modo heredado mientras haya conflictos sin resolución. Un solo perfil asociado no demuestra exclusividad. Los nombres del historial y las etiquetas de snapshots existentes se conservan como evidencia histórica.
3. **Activación explícita por configuración.** La propuesta usa un marcador de modo por instalación, fuera de SQLite y separado del JSON que reescribe la versión antigua. Antes del cambio se detienen escritores y tareas incompatibles y se verifica una copia coordinada de ambos almacenes. Con la huella de origen vigente, los conflictos resueltos y las tareas verificadas, se escribe el marcador `transition` por reemplazo atómico. La GUI y el CLI con soporte de catálogo bloquean cambios y ejecuciones durante ese modo. Después se confirma `active` en SQLite y se publica el marcador `catalog`. Solo ese par habilita el catálogo. Una interrupción, un catálogo ilegible o un desacuerdo de estados requiere recuperación explícita. La ausencia de marcador con un catálogo activo se considera incoherente. El modo antiguo solo puede usarse durante el corte después de comprobar que ningún ejecutable o script anterior pueda saltarse el marcador. No hay escritura simultánea de perfiles o repositorios en JSON y SQLite.
4. **Respaldo de configuración.** Cuando SQLite esté activo, el catálogo forma parte del respaldo de configuración independientemente de si el usuario incluye historial. Usar la API de copia coherente de SQLite y coordinar la versión exportada del catálogo con la de la configuración y sus referencias. Al restaurar, validar formato, integridad y compatibilidad antes de activar la copia. Las credenciales ligadas a otra máquina que no puedan resolverse requieren reautenticación. [API de respaldo de SQLite](https://sqlite.org/backup.html)
5. **Reversión.** Antes de activar, volver al flujo heredado conserva intacto el JSON original. Después de activar, detener escritores y conservar copias de ambos almacenes. Construir una exportación heredada desde la revisión vigente del catálogo y comparar opciones, asociaciones, ubicaciones y tareas. Si hay cambios que el formato anterior no puede representar, incluida exclusividad que el lector antiguo no puede hacer cumplir o identidades históricas ambiguas, detener la reversión y conservar ambas copias. Si la exportación es fiel, usar `transition`, instalar el JSON validado por reemplazo atómico, devolver SQLite al modo `staged` y publicar el marcador `legacy`. Solo después se reanudan los consumidores compatibles. Una interrupción mantiene el bloqueo hasta comparar las copias y completar o deshacer la transición. La reversión del catálogo conserva los repositorios físicos creados después de activar. Sus registros deben reconciliarse antes de reanudar la ejecución.

### Máquina de estados y recuperación

El marcador externo vive en el directorio efectivo de configuración local y contiene formato, UUID de instalación, modo, ID de transición y referencia al manifiesto protegido de recuperación. El manifiesto registra dirección del cambio, paso duradero, hashes de entradas y copias verificadas, revisión de partida y evidencia de tareas detenidas. Marcador y manifiesto se escriben mediante archivo temporal en el mismo volumen, sincronización y reemplazo atómico. Después de una caída, comparar el manifiesto con los hashes e IDs observados, incluso si el último paso se ejecutó antes de registrar su avance. `transition_id` se confirma en SQLite junto con el modo de destino. Cualquier desacuerdo inesperado de IDs, versión o hashes, marcador ilegible o ruta incorrecta deja el sistema bloqueado.

| Estado observable | Orden y comportamiento después de una interrupción |
|---|---|
| `legacy` con catálogo ausente o `staged` | JSON es la única fuente operativa. Si se cortó una importación, SQLite revierte la transacción o conserva el lote completo en preparación. Reanudar solo si la huella de origen sigue vigente. |
| `transition`, activación, antes del commit SQLite | Bloquear admisión y escrituras. Revalidar copias y tareas para reanudar, o publicar de nuevo `legacy` tras verificar que JSON sigue siendo la copia autoritativa. |
| `transition`, activación, después del commit SQLite | Si coinciden ID de transición, revisión y evidencia de tareas, completar el marcador `catalog`. Si se deshace antes de publicar ese marcador, volver SQLite a `staged` y publicar `legacy` con las copias verificadas. |
| `catalog` con SQLite `active` y la misma identidad de transición | SQLite es la única fuente operativa. Si falta la base o falla su integridad, bloquear. Recuperar una copia verificada del catálogo o reconciliar hacia adelante. |
| `transition`, reversión, antes de reemplazar JSON | Mantener el bloqueo. Reanudar con la exportación comprobada o restablecer el par `catalog` / `active` anterior. |
| `transition`, reversión, después de reemplazar JSON | Verificar su hash contra la exportación y confirmar SQLite `staged` con el ID de reversión antes de publicar `legacy`. Si se aborta, restaurar la copia anterior de JSON y el estado activo de catálogo desde el manifiesto. Ningún consumidor se reanuda mientras el par sea incoherente. |

GUI, CLI y procesos de mantenimiento comparten un bloqueo interproceso por directorio de configuración. La admisión o mutación verifica el marcador bajo ese bloqueo. Una transición obtiene acceso exclusivo, espera a que terminen las operaciones ya admitidas y comprueba el inventario antes y después del corte. Las transacciones SQLite y las revisiones esperadas evitan la pérdida de ediciones dentro del catálogo. Un binario antiguo puede ignorar el bloqueo y el marcador. Si no se puede demostrar que esos consumidores están detenidos y que sus rutas de arranque permanecen neutralizadas, no hay corte. La ausencia de marcador y catálogo solo permite establecer `legacy` en un alta inicial confirmada. Si faltan ambos en una instalación previa y se desconoce su modo, se exige recuperación explícita. Se presupone almacenamiento local y control administrativo sobre los ejecutores inventariados.

El **rollback semántico** solo procede si el formato legado puede recuperar asociaciones, orden, destinos y garantías operativas sin perder cambios posteriores. Si la exportación pierde, por ejemplo, la exclusividad o la resolución inequívoca de una tarea, se conserva el catálogo y se recupera hacia adelante en modo bloqueado hasta reconciliar el conflicto. Restaurar una copia antigua no autoriza descartar cambios posteriores. Una vuelta a una versión que no entiende las reglas nuevas requiere una validación de equivalencia y autorización separada.

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

Tomar la revisión del catálogo y las preferencias bajo el mismo bloqueo de consistencia. Copiar SQLite con su API de respaldo y verificar la revisión de la copia. El paquete cifrado incluye siempre catálogo y preferencias en modo catálogo. El manifiesto incluye versión del formato y del esquema, UUID de instalación, modo, revisión, ID de transición confirmada, fecha, lista de componentes con tamaño y SHA-256, y si se incluye historial. Identifica las referencias de credenciales necesarias y su disponibilidad, sin incluir valores en claro. Solo se respalda un estado operativo estable. El historial opcional conserva su propia fecha de captura si no comparte el mismo punto de consistencia. [API de respaldo de SQLite](https://sqlite.org/backup.html)

Restaurar primero a un área protegida de preparación. Validar autenticidad del paquete, manifiesto, versión, tamaños, hashes, identidad de instalación, revisión del catálogo, `integrity_check` y `foreign_key_check`. Comprobar exclusividad, referencias de destino, ubicación efectiva y disponibilidad de autenticación. El marcador del paquete describe su origen. El destino genera su propio marcador `transition` tras verificar el inventario de tareas, y solo publica un estado operativo tras instalar y verificar las copias. Una copia corrupta o incompatible no se instala. Las credenciales ausentes, no descifrables o ligadas a otro equipo dejan bloqueados los destinos afectados hasta reautenticar y verificar su identidad. Se conserva el contenido recuperado para revisión. Una contraseña vacía o una credencial de otro registro no suplen una referencia faltante. La restauración de configuración no activa tareas del SO por sí misma.

## Implementación y criterios de aceptación

1. Implementar dominio y almacenamiento Python sin Qt. Probar claves foráneas, exclusividad, destinos compartidos, renombres, orden y escrituras concurrentes con SQLite temporal.
2. Construir el importador en preparación y la exportación de reversión. Probar ambos formatos de destino, JSON inválido, campos desconocidos, ambigüedades, reintentos, fallos parciales y una modificación posterior a la activación.
3. Conectar el alta independiente, el asistente y el desregistro. Probar con procesos simulados que registrar y desregistrar no inicialicen ni borren un repositorio. Probar recuperación ante interrupciones del alta exclusiva.
4. Integrar GUI y CLI con selección por UUID y resolución heredada controlada. Probar tareas simuladas con nombres, rutas explícitas o incrustadas, cuentas y configuraciones incompatibles. Verificar que un vínculo inválido no redirija la ejecución ni lance una parte de los destinos.
5. Verificar el respaldo y la restauración de configuración con y sin historial, y la activación y vuelta con datos desechables. Mantener el historial v3 y aislar las atribuciones antiguas ambiguas.

| Prueba futura | Condición verificable |
|---|---|
| Exclusividad, desde SQL y desde el servicio | `COMMIT` rechaza un exclusivo sin vínculo al propietario y el borrado aislado de ese vínculo. Se rechaza un vínculo ajeno y una conversión no autorizada. La conversión a compartido conserva propietario anterior como asociado, su posición y el UUID. La transferencia fallida revierte ambos cambios. El desregistro no toca datos físicos. |
| Importación y reimportación | Cambiar espacios, orden de claves o representación numérica equivalente conserva el lote. Reordenar registros únicos conserva sus UUID. Reordenar destinos conserva el nuevo orden sin reasignar identidades. Duplicados idénticos, IDs no confiables y referencias contradictorias impiden el corte. Un reintento tras un fallo no crea registros adicionales. |
| Interrupciones y concurrencia | Inyectar un fallo antes y después de cada paso durable de activación, reversión y restauración. Reiniciar GUI y CLI y comprobar que un estado incoherente rechaza escrituras y ejecución. Dos escritores concurrentes no pierden revisiones. Un corte bloqueado por binarios anteriores no cambia la fuente operativa. |
| Tareas y argumentos | Simular backup y retención directos, tarea activa o encolada, cuenta inaccesible, script modificado, directorio diferente y alias ambiguo o reservado. En cada caso, el corte falla antes de admitir Restic. Con inventario íntegro y ejecutores verificados, un UUID resuelve solo su perfil y destinos vigentes. Si hay un vínculo inválido, no se ejecuta un subconjunto. |
| Respaldo y restauración | Probar ida y vuelta con y sin historial, corrupción, mezcla de revisiones, versión futura, interrupción durante instalación y credencial de otra máquina. Los paquetes inválidos conservan el estado operativo anterior. Las credenciales ausentes bloquean el destino hasta reautenticación. Se preservan los UUID, la exclusividad y el orden de destinos. |
| Rollback y recuperación hacia adelante | Tras activar, introducir cambios representables y verificar su regreso a JSON. Con cambios no representables, comprobar que se preservan ambas copias y se rechaza el rollback semántico. La recuperación hacia adelante no reinicializa ni elimina repositorios. |

La revisión actual es de diseño. La activación, la reversión y la compatibilidad con tareas siguen pendientes de implementación y prueba.

## Decisiones abiertas para aprobación

- Aprobar el catálogo separado, el reparto entre SQLite y JSON y el almacenamiento de referencias de autenticación.
- Aprobar reglas de duplicados y qué hacer con un destino exclusivo al archivar o reasignar su propietario.
- Aprobar el criterio de activación y la transición de tareas que ejecutan Restic directamente, además del procedimiento de reversión para casos que el formato anterior no representa.
- Confirmar si la validación POSIX pendiente, H1.3 o H3 condicionan la activación de la fase 4. El roadmap establece la terminación segura como prerrequisito para automatizar el apagado. El alcance del catálogo no incluye rediseñar H3.
