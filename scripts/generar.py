#!/usr/bin/env python3
"""Genera los subagentes de Claude Code que representan a los agentes de Sancho.

Entrada: la respuesta JSON de sync.agents (Sancho MCP), por stdin o como ruta.
Salida: un <id>.md por agente en .claude/agents/ del repo. Cada fichero es un envoltorio
fino: nombre, descripción para que el hilo principal sepa cuándo delegar y la
instrucción de leer la definición VIVA de Sancho al arrancar. La definición no
se copia aquí: Sancho la sirve y no se edita a mano (SAN-1119).

Solo hay que volver a correrlo cuando cambia el catálogo (alta o baja de un
agente, cambio de título o de skills). Las revisiones del propio agente llegan
solas, porque se leen en cada arranque.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent / "agents"
# Skills que llevan todos los agentes: no dicen nada sobre cuándo delegar.
COMUNES = {"g4u-session-log", "task-lifecycle", "sancho-start"}

# Herramientas del subagente (SAN-2284). Sin esta lista hereda todas las de la
# sesión, con cada conector (Gmail, Notion, Slack...), y paga ~30.000-70.000 tokens
# de contexto fijo en cada turno. Con ella el fijo baja a ~5.000. Sancho se nombra
# por servidor: cubre el conector de claude.ai (SanchoCMO/Sancho) y el del plugin.
# Si un agente necesita otro conector, añádelo en EXTRA_TOOLS.
TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch",
         "mcp__SanchoCMO", "mcp__Sancho", "mcp__sancho", "mcp__plugin_sancho-agents_sancho"]
EXTRA_TOOLS: dict[str, list[str]] = {}

# contractHash vigente de get.agent. Si Sancho lo cambia, el stub cae al
# sancho_get_operation y sigue funcionando; regenerar para volver a ahorrarse esa llamada.
GET_AGENT_CONTRACT = "77ef5f3391e604a4573d5ca978aa7267083143a2c30054d29b69349024339d31"
# contractHash vigente de sync.agents: con only=[agente] devuelve solo el packageHash
# (~0,5 KB) y evita pedir el manifiesto entero (~12 KB en Sansón) cuando hay caché.
SYNC_AGENTS_CONTRACT = "a3920b6ee9a3bcee057c94acc638d3eee05f585e701247bc6bedf0867d472b91"

BODY = """Eres **{title}**, el agente `{id}` de Sancho CMO. Tu definición no está en este fichero: la sirve Sancho y es la única que vale.

## Al arrancar, antes de hacer nada

Cada vuelta de herramienta cuesta tiempo y tokens: lanza **en paralelo, en el mismo turno**, todas las llamadas que no dependan una de otra.

1. **Hash y caché, a la vez.** En el mismo turno:
   - `sancho_read` con `resource: "paquetes"`, `operationId: "sync.agents"`, `contractHash: "{sync_contract}"` y `arguments: {{"only": ["{id}"]}}`. Devuelve en medio KB el `packageHash` vigente, sin el manifiesto. Si la tarea es de un cliente, añade su `clientSlug` exacto (resuélvelo con `list.clients`, nunca lo inventes). Solo si contesta que el contrato no vale, pide el vigente con `sancho_get_operation` (`sync.agents`) y repite.
   - Bash: `ls ~/.claude/sancho-agents/sancho_cache.py ~/.claude/plugins/marketplaces/sancho-agents/scripts/sancho_cache.py /tmp/sancho-agents/scripts/sancho_cache.py 2>/dev/null | head -1` y quédate con la ruta que imprima: es el script de caché (las variables no pasan de una llamada de Bash a otra).
2. Con ese `packageHash` corre `python3 <script> status {id} <packageHash>`.
3. **Si dice `HIT`**, la copia local está verificada contra ese `packageHash` y cuenta como lectura de Sancho: lee con Read, en paralelo, `AGENT.md` y lo que pida para el arranque desde esa carpeta. No pidas el manifiesto ni vuelvas a descargar nada de lo que ya esté ahí.
4. **Si dice `MISS`** (o falta un fichero), pide el manifiesto: `sancho_read` con `resource: "paquetes"`, `operationId: "get.agent"`, `contractHash: "{contract}"` y `arguments: {{"agentId": "{id}", "format": "portable", "offset": 0}}` (más `clientSlug` si lo usaste en el paso 1), siguiendo `nextOffset` hasta `null`. Si su `packageHash` no coincide con el del paso 1, vale el del manifiesto. Luego pide, en paralelo, `AGENT.md` y los ficheros de arranque que ya sepas que necesitas: la misma llamada con `packageHash` y `resourcePath`, siguiendo `nextOffset` hasta `null`. Después corre `python3 <script> save {id} <packageHash>`: guarda en caché, verificados por sha256, los ficheros que ya llegaron, y te da sus rutas. Léelos de ahí con Read. **No reescribas el base64 a mano** ni lo descodifiques a ojo. Solo si el paso 1 no encontró el script, descodifica con `base64 -d`.
5. Lee los ficheros que `AGENT.md` marque para el arranque. Lo que diga «solo cuando haga falta» se deja para cuando haga falta, y entonces se pide igual (caché primero). Excepción: `skills/manifest.json` no lo leas al arrancar aunque `AGENT.md` lo pida; léelo solo cuando tengas que elegir una skill, y para en cuanto encuentres la que buscas.
6. A partir de ahí actúa como dice `AGENT.md`. Una skill que no esté en el manifiesto del paquete se lee con `get.skill` / `get.skill.resource`, que ya llega en texto.

Si el MCP de Sancho no está conectado en esta sesión, para y dilo: sin tu definición no actúas. No improvises un sustituto.

## Reglas que no dependen de la definición

- Nunca envíes nada a un cliente ni fuera del proyecto sin enseñar antes el borrador exacto y tener el ok explícito a ese texto.
- Aceptar una propuesta o completar una tarea en Sancho exige una decisión humana verificable; tu relato no la acredita.
- No actives `schedules.json` ni lances herramientas de pago, publicación o ejecución sin autorización expresa.
"""


def humanize(skill: str) -> str:
    if skill.startswith("san-"):
        skill = skill[4:]  # san-<área>-<tarea> -> <área> <tarea>
    return skill.replace("-", " ")


def main() -> None:
    src = open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin
    data = json.load(src)
    agents = data.get("agents") or []
    if not agents:
        sys.exit("sync.agents sin agentes: no toco nada")
    wanted = set()
    for a in agents:
        aid, title = a["id"], a.get("title") or a["id"]
        tareas = [humanize(s) for s in a.get("skills", []) if s not in COMUNES]
        desc = f"{title} (agente de Sancho CMO). Delega aquí para: {', '.join(tareas)}." if tareas else f"{title} (agente de Sancho CMO)."
        text = (
            "---\n"
            f"name: {aid}\n"
            f"description: {json.dumps(desc, ensure_ascii=False)}\n"
            f"tools: {', '.join(TOOLS + EXTRA_TOOLS.get(aid, []))}\n"
            "---\n\n"
            + BODY.format(id=aid, title=title, contract=GET_AGENT_CONTRACT, sync_contract=SYNC_AGENTS_CONTRACT)
        )
        (HERE / f"{aid}.md").write_text(text)
        wanted.add(f"{aid}.md")
    # Agentes retirados del catálogo: fuera.
    for f in HERE.glob("*.md"):
        if f.name not in wanted:
            f.unlink()
    print(f"{len(wanted)} agentes escritos en {HERE}")


if __name__ == "__main__":
    main()
