# Base inicial del fork

La base upstream es [Restic Desktop, commit d2f258f](https://github.com/Dallustallus/restic-desktop/commit/d2f258f99a56f8b40a4cd10f75e0bc2727cfc065). Se conserva su historial y la licencia MIT.

## Rutas de ejecución

- El respaldo manual usa `build_backup_args()`, `ui.backup_worker.BackupWorker` y `core.restic_supervisor`. Qt consulta periódicamente el progreso y recibe un resultado después de la salida del proceso. La ventana conserva la selección de perfiles, repositorios y credenciales.
- `--run-job` usa la misma construcción de argumentos y el mismo supervisor. Por compatibilidad, su entrada sigue en el módulo principal, que importa Qt. El supervisor puede importarse y utilizarse por separado con Python estándar.
- Las tareas antiguas de un solo repositorio ejecutan Restic directamente desde PowerShell. Las de varios destinos intentan entrar por `--run-job`. El generador de tareas conserva sus supuestos anteriores de rutas, credenciales y empaquetado. Las tareas ya registradas no quedan migradas por este cambio.
- Consultas, comparaciones, copias, integridad, retención, restauración y otras utilidades conservan sus ejecutores anteriores. La comparación exige salida exitosa antes de interpretar cifras. Los resultados tipados y el código real por destino se aplican a las rutas de respaldo supervisadas.

## Contrato del supervisor

`ExecutionRequest` describe ejecutable, argumentos, entorno del hijo, directorio, plazo y referencias opcionales de perfil y destino. `start()` devuelve un identificador de ejecución, un PID cuando hubo arranque, estado consultable, solicitud de cancelación, progreso separado y espera de un resultado. Un fallo previo al lanzamiento no inventa un PID ni un código. Los procesos se lanzan con una lista de argumentos, entrada cerrada y entorno propio. No se leen ajustes del escritorio.

Para respaldos JSON se exige el código de salida y el resumen final documentado de Restic. El éxito con omisión requiere un resumen válido sin ID de snapshot y la opción correspondiente habilitada. El código 3 se registra como respaldo incompleto. Los códigos desconocidos se conservan como fallos. El resumen no demuestra que el perfil incluyera todos los orígenes previstos ni sustituye una comprobación del repositorio. En el modo genérico, «completado» expresa el resultado del proceso. [Interfaz de automatización de Restic](https://restic.readthedocs.io/en/stable/075_scripting.html).

La política predeterminada espera la salida natural del hijo tras registrar la solicitud de parada. Así funciona el botón **Stop Backup Job**: el destino activo puede completar una snapshot y se omiten los demás. Un plazo vencido también queda pendiente hasta que Restic sale. La acción conserva el código real y no se registra como éxito. La política explícita `TERMINATE_CHILD` se valida con procesos simulados. No se habilitó para respaldos reales ni controla descendientes. Una señal de consola en Windows depende de la consola y del grupo del proceso, y la aplicación empaquetada carece de consola. [Señales de consola de Windows](https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent).

Se capturan ambas salidas sin depender del cierre de tuberías por descendientes. Se conserva hasta 1 MiB por flujo y el progreso usa una cola acotada. Se descartan las variables `RESTIC_*` heredadas y se aceptan las proporcionadas explícitamente. Entregar contraseñas mediante el entorno del hijo, por ejemplo con `RESTIC_PASSWORD` o una referencia `RESTIC_PASSWORD_FILE`. Las salidas redactan los valores conocidos de variables sensibles y credenciales en URLs comunes. Esto no detecta secretos arbitrarios codificados por un tercero. Los argumentos son responsabilidad de un llamador de confianza.

## Contención y límites

- **Unregister** solo quita la configuración local. La eliminación física local o remota quedó retirada del flujo. Cualquier recuperación futura de esa capacidad requiere una acción aparte con validación de identidad y alcance.
- La restauración original quedó deshabilitada y se retiró la rutina que movía archivos y borraba el temporal compartido. La restauración alternativa requiere una carpeta existente y vacía como destino, sin punto de reanálisis en ese último componente, y usa `--overwrite never`. Es una contención, todavía sin plan de conflictos, control de todos los enlaces y carreras, verificación final ni rollback.
- Las dos rutas de respaldo supervisadas conservan el código real y registran el intento por destino mediante el esquema SQLite existente. El panel presenta el resultado de ese historial, sin atribuirle la última snapshot del repositorio. Los resultados abiertos siguen en memoria y las identidades siguen siendo nombres de la configuración anterior.
- PowerShell programado, el adaptador heredado de red, el almacenamiento heredado de contraseñas y los comandos fuera del supervisor mantienen riesgos y limitaciones anteriores. Se requiere un plan independiente para cuentas de servicio, cancelación cooperativa, persistencia recuperable y concurrencia entre instancias.

## Verificación local

Con las dependencias declaradas en un entorno virtual de proyecto, ejecutar `env\Scripts\python.exe -B -m unittest discover -s tests -v`. Pasaron 22 pruebas en Python 3.14.0 y 3.13.7. Usan procesos Python controlados, un canal local para sincronizar y dobles de la aplicación. También se abrió la ventana completa en modo offscreen y se recorrieron sus ocho páginas en ambas versiones. La prueba del binario Restic incluido se limitó a versión y ayuda. No se probó un apagado de Windows.

PyInstaller 6.19.0 generó el ejecutable con `restic_manager.spec`. El primer paquete capturó una DLL ICU de Poppler desde el `PATH` del entorno y falló al importar QtCore. Una compilación con el `PATH` del proceso limitado al entorno virtual, `System32` y Windows pasó la prueba empaquetada de `--run-job` con un perfil de prueba inexistente y devolvió el código 1. Persistieron dos avisos por imports ocultos de pycparser. El instalador y la creación de tareas Windows siguen sin validarse.
