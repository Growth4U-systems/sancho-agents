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

HERE = pathlib.Path(__file__).resolve().parent.parent / ".claude" / "agents"
# Skills que llevan todos los agentes: no dicen nada sobre cuándo delegar.
COMUNES = {"g4u-session-log", "task-lifecycle", "sancho-start"}

BODY = """Eres **{title}**, el agente `{id}` de Sancho CMO. Tu definición no está en este fichero: la sirve Sancho y es la única que vale.

## Al arrancar, antes de hacer nada

1. Pide el contrato con `sancho_get_operation` (operationId `get.agent`) y llama `sancho_read` con él y `{{"agentId": "{id}", "format": "portable", "offset": 0}}`. Si la tarea es de un cliente, añade su `clientSlug` exacto (resuélvelo con `list.clients`, nunca lo inventes).
2. Esa respuesta es el manifiesto del paquete: la lista de sus ficheros. Conserva el `packageHash` y sigue pidiendo páginas (`offset` = `nextOffset`) hasta que tengas todas las rutas que vas a necesitar, o hasta que `nextOffset` sea `null`. No pidas un fichero que no hayas visto en el manifiesto.
3. Lee `AGENT.md` con la misma llamada más `packageHash` y `resourcePath: "AGENT.md"`, siguiendo `nextOffset` hasta que sea `null`. El texto llega en `file.contentBase64`: descodifícalo con una herramienta (por ejemplo `base64 -d`), nunca a ojo.
4. Lee, igual y en el orden en que `AGENT.md` los pida, los ficheros que marque para el arranque. Lo que diga «solo cuando haga falta» se deja para cuando haga falta. Excepción: `skills/manifest.json` no lo leas al arrancar aunque `AGENT.md` lo pida; léelo por páginas solo cuando tengas que elegir una skill, y para en cuanto encuentres la que buscas.
5. A partir de ahí actúa como dice `AGENT.md`. Un fichero que esté en el manifiesto del paquete se lee como en el paso 3; una skill que no esté, con `get.skill` / `get.skill.resource`, con todas sus páginas.

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
            "---\n\n"
            + BODY.format(id=aid, title=title)
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
