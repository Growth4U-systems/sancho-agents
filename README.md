# Agentes de Sancho CMO para Claude Code

Este repo trae los agentes de [Sancho CMO](https://app.sanchocmo.ai) (Sancho, Hamete, Dulcinea, Sansón, Rocinante y los demás) como subagentes de Claude Code. Abre una sesión aquí, en la nube o en tu ordenador, y podrás pedir cosas como «que Sansón revise este brief» o «que Hamete prepare el company brief de este cliente».

## Instalar en la nube (claude.ai/code)

1. Conecta Sancho en tu cuenta de claude.ai (Ajustes → Conectores → Añadir conector personalizado, URL `https://app.sanchocmo.ai/api/mcp/sancho`) e inicia sesión con tu propio usuario de Sancho.
2. Abre una sesión nueva en [claude.ai/code](https://claude.ai/code) sobre este repo. Tiene que ser una sesión normal, no un Proyecto: los hilos de un Proyecto no cargan `.claude/agents/`.
3. Activa el conector de Sancho en esa sesión.

No hace falta script de instalación ni token: los agentes se cargan solos desde `.claude/agents/` al arrancar la sesión, y cada uno habla con Sancho a través de tu conector. Por eso solo ves los clientes a los que tienes acceso.

## Instalar en tu ordenador

```bash
git clone https://github.com/Growth4U-systems/sancho-agents.git
cp sancho-agents/.claude/agents/*.md ~/.claude/agents/
```

Necesitas el MCP de Sancho conectado en tu Claude Code.

## Cómo funcionan

Los ficheros de `.claude/agents/` **no llevan la definición del agente**. Al arrancar, cada agente la lee de Sancho (`get.agent`, formato portable) y sigue lo que dice su `AGENT.md`. Así siempre corre la revisión vigente: cuando Sancho cambia un agente, el cambio llega en el siguiente arranque sin tocar este repo.

Si el conector de Sancho no está activo en la sesión, el agente se para y lo dice.

Delega en un agente cada vez. Cada arranque lee varios ficheros de Sancho, y con muchos en paralelo Sancho no da abasto: en una prueba con 13 a la vez, las lecturas acabaron en timeout y la sesión del conector se cayó.

## Cuándo se regenera

Solo cuando cambia el catálogo: entra o sale un agente, o cambia su título o sus skills. Se guarda la respuesta de `sync.agents` de Sancho en un JSON y se corre:

```bash
python3 scripts/generar.py sync.json
```
