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

# Herramientas del subagente (SAN-2284). Sin lista hereda todas las de la sesión
# (Gmail, Notion, Slack...): ~70.000 tokens de contexto fijo. Nombrar el servidor
# de Sancho entero carga sus 13 herramientas (~12.000). Por eso cada agente lleva
# solo las de Sancho que cita su definición, por nombre exacto. Sancho tiene
# varios nombres de servidor según cómo esté conectado (claude.ai o plugin): se
# declaran todos y Claude Code ignora los que no existan.
BASE = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
WEB = ["WebFetch", "WebSearch"]
SERVIDORES = ["mcp__SanchoCMO", "mcp__Sancho", "mcp__sancho", "mcp__plugin_sancho-agents_sancho"]
# Todas: leer/escribir y sancho_get_operation para el contrato si caduca un hash.
SANCHO_BASE = ["sancho_read", "sancho_write", "sancho_get_operation"]
INTEGRACIONES = ["integrations_list_tools", "integrations_read_tool", "integrations_execute_tool"]
METRICAS = ["sancho_metrics_catalog", "sancho_metrics_query"]
# Sacado de las menciones en agents/<id>/ de sanchocmo-mcp (12-nov-2026).
# Si un agente pide una herramienta que no tiene, añádela aquí y regenera.
POR_AGENTE: dict[str, dict] = {
    "alarife": {"web": True, "sancho": INTEGRACIONES},
    "aldonza": {"web": True, "sancho": INTEGRACIONES + METRICAS + ["sancho_ingestion", "sancho_mcp_status"]},
    "basilio": {"web": True, "sancho": []},
    "cervantes": {"web": False, "sancho": ["sancho_search_operations"]},
    "dorotea": {"web": False, "sancho": INTEGRACIONES},
    "dulcinea": {"web": True, "sancho": METRICAS},
    "hamete": {"web": True, "sancho": []},
    "maese-pedro": {"web": True, "sancho": INTEGRACIONES},
    "mambrino": {"web": True, "sancho": INTEGRACIONES + METRICAS},
    "merlin": {"web": False, "sancho": METRICAS + ["sancho_search_operations"]},
    "rocinante": {"web": True, "sancho": INTEGRACIONES + METRICAS + ["sancho_mcp_status"]},
    "sancho": {"web": True, "sancho": []},
    "sanson": {"web": False, "sancho": []},
}


def herramientas(aid: str) -> str:
    cfg = POR_AGENTE.get(aid, {"web": True, "sancho": []})
    sancho = SANCHO_BASE + cfg["sancho"]
    mcp = [f"{srv}__{t}" for srv in SERVIDORES for t in sancho]
    return ", ".join(BASE + (WEB if cfg["web"] else []) + mcp)


# contractHash vigente de get.agent. Si Sancho lo cambia, el stub cae al
# sancho_get_operation y sigue funcionando; regenerar para volver a ahorrarse esa llamada.
GET_AGENT_CONTRACT = "9da3710fd60db87486f6c97d6430689f215fbe27a528f95942d17896e88d308f"
# contractHash vigente de sync.agents: con only=[agente] devuelve solo el packageHash
# (~0,5 KB) y evita pedir el manifiesto entero (~12 KB en Sansón) cuando hay caché.
SYNC_AGENTS_CONTRACT = "a3920b6ee9a3bcee057c94acc638d3eee05f585e701247bc6bedf0867d472b91"
# get.skill / get.skill.resource: sin ellos el agente gasta 3-4 llamadas en buscar la operación.
GET_SKILL_CONTRACT = "037ba841c4344d7432c0e4ceb4360a631f9c867040b8f53891f959c05868f9b5"
GET_SKILL_RESOURCE_CONTRACT = "84c1c1239ce71a52ab78e0a9721033106cd16143ffc4fb63bd9ccfe0abcecebf"

BODY = """Eres **{title}**, el agente `{id}` de Sancho CMO. Tu definición no está en este fichero: la sirve Sancho y es la única que vale.

## Al arrancar, antes de hacer nada

Cada vuelta de herramienta cuesta tiempo y tokens: lanza **en paralelo, en el mismo turno**, todas las llamadas que no dependan una de otra.

1. **Hash y caché, a la vez.** En el mismo turno:
   - `sancho_read` con `resource: "paquetes"`, `operationId: "sync.agents"`, `contractHash: "{sync_contract}"` y `arguments: {{"only": ["{id}"]}}`. Devuelve en medio KB el `packageHash` vigente, sin el manifiesto. Si la tarea es de un cliente, añade su `clientSlug` exacto (resuélvelo con `list.clients`, nunca lo inventes). Solo si contesta que el contrato no vale, pide el vigente con `sancho_get_operation` (`sync.agents`) y repite.
   - Bash: `ls ~/.claude/sancho-agents/sancho_cache.py ~/.claude/plugins/marketplaces/sancho-agents/scripts/sancho_cache.py /tmp/sancho-agents/scripts/sancho_cache.py 2>/dev/null | head -1` y quédate con la ruta que imprima: es el script de caché (las variables no pasan de una llamada de Bash a otra).
2. Con ese `packageHash` corre `python3 <script> status {id} <packageHash>`.
3. **Si dice `HIT`**, la copia local está verificada contra ese `packageHash` y cuenta como lectura de Sancho: lee con Read, en paralelo, `AGENT.md` y lo que pida para el arranque desde esa carpeta. No pidas el manifiesto ni vuelvas a descargar nada de lo que ya esté ahí.
4. **Si dice `MISS`** (o falta un fichero), pide el manifiesto: `sancho_read` con `resource: "paquetes"`, `operationId: "get.agent"`, `contractHash: "{contract}"` y `arguments: {{"agentId": "{id}", "format": "portable", "offset": 0}}` (más `clientSlug` si lo usaste en el paso 1), siguiendo `nextOffset` hasta `null`. Si su `packageHash` no coincide con el del paso 1, vale el del manifiesto. Luego pide, en paralelo, `AGENT.md` y los ficheros de arranque que ya sepas que necesitas: la misma llamada con `packageHash`, `resourcePath` y `"encoding": "utf8"`, siguiendo `nextOffset` hasta `null`. Los ficheros de texto llegan legibles en `file.content`: úsalos tal cual y **no los vuelvas a leer con Read**. Después corre `python3 <script> save {id} <packageHash>`, que los guarda en caché verificados por sha256 para el próximo arranque. Un binario llega en `contentBase64`: no lo reescribas a mano; `save` lo guarda y te da su ruta.
5. Lee los ficheros que `AGENT.md` marque para el arranque. Lo que diga «solo cuando haga falta» se deja para cuando haga falta, y entonces se pide igual (caché primero). Excepción: `skills/manifest.json` no lo leas al arrancar aunque `AGENT.md` lo pida; léelo solo cuando tengas que elegir una skill, y para en cuanto encuentres la que buscas.
6. A partir de ahí actúa como dice `AGENT.md`. Una skill que no esté en tu caché se lee directamente, sin buscarla ni pedir antes `sancho_get_operation`: `sancho_read` con `resource: "paquetes"`, `operationId: "get.skill"`, `contractHash: "{skill_contract}"` y `arguments: {{"name": "<slug>"}}`; sus recursos con `operationId: "get.skill.resource"`, `contractHash: "{resource_contract}"` y `arguments` con `skill` (el slug), `type`, `client_scope`, `expected` (el pin que devolvió `get.skill`) y `path`. El texto llega una sola vez, en `skillMdSegments` o `contentSegments`: únelos en orden. Solo si un contrato no vale, pide el vigente con `sancho_get_operation`.

Si el MCP de Sancho no está conectado en esta sesión, para y dilo: sin tu definición no actúas. No improvises un sustituto.

## Reglas que no dependen de la definición

- Nunca envíes nada a un cliente ni fuera del proyecto sin enseñar antes el borrador exacto y tener el ok explícito a ese texto.
- Aceptar una propuesta o completar una tarea en Sancho exige una decisión humana verificable; tu relato no la acredita.
- No actives `schedules.json` ni lances herramientas de pago, publicación o ejecución sin autorización expresa.
"""


# SAN-2284: con el paquete copiado en paquetes/<id>/ el stub lleva dentro los
# ficheros de arranque y el agente arranca sin llamar a Sancho.
PAQUETES = pathlib.Path(__file__).resolve().parent.parent / "paquetes"
ARRANQUE = ["AGENT.md", "skills/agent-operation/SKILL.md", "context.md", "workflows.md"]

PAQUETE_BODY = """Eres **{title}**, el agente `{id}` de Sancho CMO.

Abajo va tu definición vigente, copiada de Sancho: paquete `{id}`, revisión {revision}, `packageHash` `{phash}`, sincronizada el {fecha}. Es una copia verificada por sha256 y cuenta como lectura de Sancho (SAN-2008), así que no la pidas otra vez. Ya tienes aquí `AGENT.md`, `skills/agent-operation/SKILL.md`, `context.md` y `workflows.md`: no los leas.

## Tus ficheros

El resto del paquete está en la carpeta `paquetes/{id}/` del repo sancho-agents: skills, recursos, `agents/_shared/` y `skills/manifest.json`. Para encontrarla, corre una vez en Bash `find / -path '*/paquetes/{id}/.sync.json' -not -path '/proc/*' 2>/dev/null | head -1` y quédate con su carpeta. Lee de ahí con Read solo lo que tu definición o el encargo pidan, cuando haga falta. Las skills y sus recursos se leen de ahí, no de Sancho; `skills/manifest.json` solo cuando tengas que elegir skill, y para en cuanto encuentres la que buscas. Una skill asignada solo a un cliente puede no estar en el repo: esa sí se pide a Sancho con `get.skill`.

## Si Sancho dice que tu versión ya no vale

Si al arrancar un run o al usar una skill Sancho responde que el paquete o la publicación cambió (`agent_package_changed_restart`, un 409 o un pin distinto), esta copia está atrasada. Pide el paquete vigente: `sancho_read` con `resource: "paquetes"`, `operationId: "sync.agents"`, `contractHash: "{sync_contract}"` y `arguments: {{"only": ["{id}"]}}` para el `packageHash`; luego `get.agent` (`contractHash: "{contract}"`) con `{{"agentId": "{id}", "format": "portable", "packageHash": "<hash>", "resourcePath": "<ruta>", "encoding": "utf8"}}` para cada fichero que necesites. Sancho actualiza el repo solo en unos minutos.

## Reglas que no dependen de la definición

- Nunca envíes nada a un cliente ni fuera del proyecto sin enseñar antes el borrador exacto y tener el ok explícito a ese texto.
- Aceptar una propuesta o completar una tarea en Sancho exige una decisión humana verificable; tu relato no la acredita.
- No actives `schedules.json` ni lances herramientas de pago, publicación o ejecución sin autorización expresa.

{ficheros}"""


def _stub(aid: str, title: str, skills: list, paquete: dict | None = None) -> str:
    tareas = [humanize(s) for s in skills if s not in COMUNES]
    desc = f"{title} (agente de Sancho CMO). Delega aquí para: {', '.join(tareas)}." if tareas else f"{title} (agente de Sancho CMO)."
    cabecera = ("---\n" f"name: {aid}\n" f"description: {json.dumps(desc, ensure_ascii=False)}\n"
                f"tools: {herramientas(aid)}\n" "---\n\n")
    if paquete is None:
        return cabecera + BODY.format(id=aid, title=title, contract=GET_AGENT_CONTRACT, sync_contract=SYNC_AGENTS_CONTRACT,
                                      skill_contract=GET_SKILL_CONTRACT, resource_contract=GET_SKILL_RESOURCE_CONTRACT)
    carpeta = PAQUETES / aid
    ficheros = "\n\n".join(f"## Fichero `{ruta}`\n\n{(carpeta / ruta).read_text()}" for ruta in ARRANQUE if (carpeta / ruta).exists())
    return cabecera + PAQUETE_BODY.format(id=aid, title=title, revision=paquete.get("revision"), phash=paquete["packageHash"],
                                          fecha=paquete.get("sincronizado"), contract=GET_AGENT_CONTRACT,
                                          sync_contract=SYNC_AGENTS_CONTRACT, ficheros=ficheros)


def desde_paquetes() -> None:
    """Regenera los stubs de los agentes que tienen paquete en paquetes/."""
    n = 0
    for f in sorted(PAQUETES.glob("*/.sync.json")):
        p = json.loads(f.read_text())
        (HERE / f"{p['id']}.md").write_text(_stub(p["id"], p.get("title") or p["id"], p.get("skills", []), p))
        n += 1
    print(f"{n} stubs generados desde paquetes/")


def humanize(skill: str) -> str:
    if skill.startswith("san-"):
        skill = skill[4:]  # san-<área>-<tarea> -> <área> <tarea>
    return skill.replace("-", " ")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--paquetes":
        return desde_paquetes()
    src = open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin
    data = json.load(src)
    agents = data.get("agents") or []
    if not agents:
        sys.exit("sync.agents sin agentes: no toco nada")
    wanted = set()
    for a in agents:
        aid, title = a["id"], a.get("title") or a["id"]
        paquete = PAQUETES / aid / ".sync.json"
        datos = json.loads(paquete.read_text()) if paquete.exists() else None
        (HERE / f"{aid}.md").write_text(_stub(aid, title, a.get("skills", []), datos))
        wanted.add(f"{aid}.md")
    # Agentes retirados del catálogo: fuera.
    for f in HERE.glob("*.md"):
        if f.name not in wanted:
            f.unlink()
    print(f"{len(wanted)} agentes escritos en {HERE}")


if __name__ == "__main__":
    main()
