# Instrucciones para Restic Desktop

- Responde en español. Trabaja dentro del alcance solicitado y conserva los cambios existentes.
- Antes de editar, revisa el estado Git y las instrucciones aplicables. Consulta `DOCS/IMPLEMENTATION_ROADMAP.md` y, para el catálogo, `DOCS/PHASE_4_DESIGN.md`.
- Usa la rama `codex/initial-restic-foundation` salvo indicación expresa. No reescribas historial ni uses force push. No ejecutes operaciones Restic sobre repositorios personales sin autorización.
- Verifica los cambios según su alcance. Para la suite Windows usa `env\Scripts\python.exe -B -m unittest discover -s tests -v`. Informa fallos, pruebas omitidas y limitaciones.
- Tras cada tarea con cambios, revisa el diff, crea un commit descriptivo con los archivos de la tarea y publícalo en la rama de trabajo en `origin`. Si el usuario limita expresamente la publicación o existe un conflicto, respeta esa instrucción e informa el pendiente. No incluyas secretos ni cambios ajenos.
- Después del push, entrega un prompt breve y copiable para una auditoría de solo lectura mediante el complemento de GitHub. Incluye repositorio, rama, enlace directo al commit, objetivo y puntos que revisar.
- Para consultas sin cambios, responde sin crear commits vacíos.
