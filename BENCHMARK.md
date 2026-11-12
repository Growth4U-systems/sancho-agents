# Benchmark de arranque de agentes (SAN-2284)

Mide cuánto cuesta que un agente de Sancho arranque: leer su definición y los ficheros de arranque, sin ejecutar ninguna skill. Sirve para comparar versiones de los stubs y cambios en Sancho con la misma tarea.

## Cómo repetirlo

1. Sesión de Claude Code con el conector de Sancho activo y este repo instalado (plugin o setup script del README). Si cambiaste los stubs, reinicia Claude Code para que los cargue.
2. Para medir en frío, vacía la caché: `rm -rf ~/.claude/sancho-cache/<agente>`.
3. Delega en el agente (por ejemplo `sanson`) **solo** este encargo, uno cada vez y nunca en paralelo:

   > Tarea de benchmark (SAN-2284). Arranca exactamente como dice tu sección «Al arrancar», sin cliente (no pases clientSlug). Cuando hayas leído `AGENT.md` y los ficheros que marque para el arranque, para. No ejecutes ninguna skill ni escribas nada en Sancho. Responde solo con: packageHash del paquete, lista de ficheros que leíste y de dónde salió cada uno (Sancho o caché local), y cualquier error o timeout.

4. Repite el mismo encargo sin vaciar la caché: es el arranque en caliente.
5. Después de cada ejecución: `python3 scripts/medir.py --ultimo` (o la ruta del transcript del subagente). Apunta duración, llamadas a Sancho, bytes devueltos y tokens.

«Sobre la base» es `tokens_contexto_final − tokens_contexto_inicial`: lo que añade el arranque al contexto, sin contar el prompt de sistema y las herramientas, que son iguales en todas las ejecuciones.

## Resultados: Sansón, 12-nov-2026

Paquete `sanson` revisión 6, `packageHash 27619785…4b86`, 72 ficheros en el manifiesto. Lee de arranque `AGENT.md`, `skills/agent-operation/SKILL.md`, `context.md` y `workflows.md` (~9,7 KB). Sesión en la nube, sin cliente.

| Ejecución | Duración | Llamadas a Sancho | Bytes devueltos | Tokens sobre la base | Tokens de entrada procesados |
| -- | --: | --: | --: | --: | --: |
| A. Stubs anteriores a 1.1.0 (sin caché) | 110 s | 6 | 29,9 KB | 39.200 | 726.000 |
| B. Plugin 1.1.0, caché vacía | 63 s | 5 | 36,9 KB | 37.600 | 735.000 |
| C. Plugin 1.1.0, caché llena | 39 s | 1 | 22,5 KB | 22.700 | 512.000 |
| D. 1.2.0 (hash con `sync.agents`), caché llena | 34 s | 1 | 11,3 KB | 16.600 | 488.000 |

Qué se ve:

- Con caché el arranque pasa de 110 s a 34 s y de 6 llamadas a Sancho a 1. El contexto que añade baja de 39.200 a 16.600 tokens.
- En 1.1.0 la única llamada en caliente era el manifiesto entero (11,7 KB en Sansón, más en agentes con paquetes grandes) solo para leer el `packageHash`. En 1.2.0 se pide con `sync.agents` y `only`, que devuelve 0,5 KB. El manifiesto solo se pide si hay que descargar.
- El arranque de Sansón es poco frente a lo medido en la demo (Company Brief 88.600 tokens, HTML de Maese Pedro 356.000, Market Intelligence 276.000). La mayor parte de ese coste está en leer skills y recursos (`get.skill.resource` con texto duplicado y páginas de ~600 bytes) y en los documentos, que son del lado de Sancho.
- En la nube la caché dura lo que dura la sesión: el primer arranque de cada agente en una sesión nueva siempre es en frío (fila B).
