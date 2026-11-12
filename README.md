# Agentes de Sancho CMO para Claude Code

Este repo trae los agentes de [Sancho CMO](https://app.sanchocmo.ai) (Sancho, Hamete, Dulcinea, Sansón, Rocinante y los demás) como subagentes de Claude Code. Abre una sesión aquí, en la nube o en tu ordenador, y podrás pedir cosas como «que Sansón revise este brief» o «que Hamete prepare el company brief de este cliente».

## Instalar en tu Claude Code (ordenador)

Dentro de Claude Code:

```
/plugin marketplace add Growth4U-systems/sancho-agents
/plugin install sancho-agents@sancho-agents
```

Reinicia Claude Code, entra en `/mcp`, elige `plugin:sancho-agents:sancho` y conéctate con tu usuario de Sancho. Ya puedes pedir cosas como «que Sansón revise este brief».

El plugin trae los 13 agentes y el conector de Sancho. Para recibir agentes nuevos: `/plugin marketplace update sancho-agents`.

## Instalar en la nube (claude.ai/code)

1. Conecta Sancho en tu cuenta de claude.ai (Ajustes → Conectores → Añadir conector personalizado, URL `https://app.sanchocmo.ai/api/mcp/sancho`) e inicia sesión con tu propio usuario de Sancho.
2. Abre una sesión nueva en [claude.ai/code](https://claude.ai/code) sobre este repo. Tiene que ser una sesión normal, no un Proyecto: los hilos de un Proyecto no cargan agentes.
3. Activa el conector de Sancho en esa sesión.

Para tenerlos en cualquier repo, añade esto al setup script del entorno:

```bash
git clone --depth 1 https://github.com/Growth4U-systems/sancho-agents /tmp/sancho-agents || true
mkdir -p ~/.claude/agents
cp /tmp/sancho-agents/agents/*.md ~/.claude/agents/ || true
```

En ningún caso hace falta token: cada agente habla con Sancho a través de tu conector, así que solo ves los clientes a los que tienes acceso.

## Cómo funcionan

Los ficheros de `agents/` **no llevan la definición del agente**. Al arrancar, cada agente la lee de Sancho (`get.agent`, formato portable) y sigue lo que dice su `AGENT.md`. Así siempre corre la revisión vigente: cuando Sancho cambia un agente, el cambio llega en el siguiente arranque sin tocar este repo.

Si el conector de Sancho no está activo en la sesión, el agente se para y lo dice.

Delega en un agente cada vez. Cada arranque lee varios ficheros de Sancho, y con muchos en paralelo Sancho no da abasto: en una prueba con 13 a la vez, las lecturas acabaron en timeout y la sesión del conector se cayó.

## Cuándo se regenera

Solo cuando cambia el catálogo: entra o sale un agente, o cambia su título o sus skills. Se guarda la respuesta de `sync.agents` de Sancho en un JSON y se corre:

```bash
python3 scripts/generar.py sync.json
```
