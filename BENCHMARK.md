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
| J. 1.4.0 (herramientas exactas, texto utf8, paquete sin tests), caché vacía | 84 s | 9 (3 reintentos por conexión perdida) | 23,4 KB | 23.100 | 236.000 |

Qué se ve:

- Con caché el arranque pasa de 110 s a 34 s y de 6 llamadas a Sancho a 1. El contexto que añade baja de 39.200 a 16.600 tokens.
- En 1.1.0 la única llamada en caliente era el manifiesto entero (11,7 KB en Sansón, más en agentes con paquetes grandes) solo para leer el `packageHash`. En 1.2.0 se pide con `sync.agents` y `only`, que devuelve 0,5 KB. El manifiesto solo se pide si hay que descargar.
- El arranque de Sansón es poco frente a lo medido en la demo (Company Brief 88.600 tokens, HTML de Maese Pedro 356.000, Market Intelligence 276.000). La mayor parte de ese coste está en leer skills y recursos (`get.skill.resource` con texto duplicado y páginas de ~600 bytes) y en los documentos, que son del lado de Sancho.
- En frío, 1.4.0 (fila J) trae 23,4 KB frente a 36,9 KB de la fila B: el texto llega legible y no se vuelve a leer con Read, y el manifiesto ya no lista tests (65 ficheros frente a 72). Arranca con 12.400 tokens fijos en vez de ~31.000. La entrada procesada baja de 735.000 a 236.000.
- En la nube la caché dura lo que dura la sesión: el primer arranque de cada agente en una sesión nueva siempre es en frío (fila B).

## Herramientas del subagente (1.2.0)

Sin la línea `tools:` un subagente hereda todas las herramientas de la sesión: cada conector de claude.ai (Gmail, Notion, Slack, ElevenLabs…), sus instrucciones y la lista de herramientas diferidas. Eso es contexto fijo que se paga en cada turno. En la tarea real de Sansón (revisión de-slop de un párrafo, sin cliente) el subagente empezó con 71.600 tokens antes de hacer nada y acabó en 144.000, con 1,24 millones de tokens de entrada procesados en 12 turnos.

Prueba con Claude Code 2.1.322 y un MCP de prueba: el mismo subagente con todas las herramientas arranca con 31.500 tokens (sin conectores de claude.ai) y con `tools: Read, Bash, WebFetch, WebSearch, mcp__<servidor>` con 5.000. Las herramientas del MCP nombrado por servidor llegan cargadas, sin ToolSearch, y un servidor que no existe se ignora.

Nombrar el servidor de Sancho entero carga sus 13 herramientas (~12.000 tokens). Desde 1.3.0 cada stub declara solo las herramientas de Sancho que cita la definición de su agente, por nombre exacto y con los cuatro nombres de servidor habituales (`SanchoCMO`, `Sancho`, `sancho` y el del plugin); los que no existen se ignoran. La web solo va en los agentes que investigan. El mapa está en `POR_AGENTE` de `scripts/generar.py`: si un agente necesita una herramienta que no tiene, se añade ahí.

### Tarea real: Sansón, de-slop de un párrafo (12-nov-2026)

Encargo fijo (sin cliente, sin escribir en Sancho): pasar este párrafo por el método de-slop y devolver el párrafo corregido con los cambios.

> «En el dinámico panorama actual de las finanzas, Revolut Business se erige como una solución integral que no solo optimiza la gestión de pagos, sino que también potencia el crecimiento de las empresas. Con su enfoque innovador y centrado en el cliente, desbloquea todo el potencial de los equipos financieros, ofreciendo una experiencia fluida y sin fricciones.»

Las dos con la caché de arranque llena (4 ficheros) y los ficheros del método sin cachear.

| Ejecución | Duración | Llamadas (Sancho) | Contexto al empezar | Contexto final | Entrada procesada |
| -- | --: | --: | --: | --: | --: |
| E. Sin `tools:` (hereda todo) | 132 s | 19 (6) | 71.700 | 144.100 | 1.242.000 |
| G. Con `tools:` | 178 s | 19 (9) | 21.900 | 86.700 | 690.000 |
| H. Con `tools:` y contratos de `get.skill` en el stub | 112 s | 13 (5) | 25.000 | 80.100 | 328.000 |
| I. 1.3.0, herramientas exactas por agente | 90 s | 13 (5) | 12.400 | 66.300 | 238.000 |

Con `tools:` el contexto fijo baja un 70 % y la entrada procesada un 44 %. G gastó 4 llamadas en buscar `get.skill` (`sancho_get_operation` y `sancho_search_operations`): por eso los stubs ya llevan también el `contractHash` de `get.skill` y `get.skill.resource`. H es la misma tarea con los contratos ya en el stub: 7 turnos en vez de 12 y menos de la mitad de entrada procesada. H aún cargaba las 13 herramientas de Sancho; I solo carga las 3 de Sansón y sin web, y su contexto fijo baja a la mitad. Frente a E, I procesa un 81 % menos. Lo que queda en I son sobre todo los 84 KB que devuelven las herramientas (definición, método y patrones). La duración depende sobre todo de la latencia de Sancho y del modelo; compara tokens antes que segundos.
