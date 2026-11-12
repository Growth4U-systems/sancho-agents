#!/usr/bin/env python3
"""Mide lo que costó una ejecución de un subagente a partir de su transcript.

Uso:
  python3 scripts/medir.py <transcript.jsonl> [más transcripts...]
  python3 scripts/medir.py --ultimo        # el subagente más reciente de esta máquina

Los transcripts de los subagentes están en
~/.claude/projects/<proyecto>/<sesión>/subagents/agent-*.jsonl.

Saca, por transcript:
- duración (primer a último mensaje),
- turnos del modelo y llamadas a herramientas (total, a Sancho, por herramienta),
- bytes que devolvieron las herramientas (lo que entra en contexto),
- tokens: contexto inicial (prompt de sistema + herramientas + encargo, antes
  de hacer nada), contexto final (lo que el panel de Claude Code llama «tokens»),
  tokens de entrada procesados sumando todos los turnos y tokens de salida.

Sirve para comparar el arranque antes y después de SAN-2284 con la misma tarea
(ver BENCHMARK.md).
"""
import collections
import datetime
import json
import pathlib
import sys


def _ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def medir(path):
    vistos, tiempos = {}, []
    llamadas = collections.Counter()
    bytes_resultado = 0
    for linea in open(path, errors="ignore"):
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        if d.get("timestamp"):
            tiempos.append(_ts(d["timestamp"]))
        m = d.get("message") or {}
        contenido = m.get("content")
        if d.get("type") == "assistant":
            mid = m.get("id") or d.get("uuid")
            if m.get("usage"):
                vistos[mid] = m["usage"]
            for c in contenido if isinstance(contenido, list) else []:
                if c.get("type") == "tool_use":
                    llamadas[c["name"]] += 1
        elif d.get("type") == "user" and isinstance(contenido, list):
            for c in contenido:
                if c.get("type") == "tool_result":
                    r = c.get("content")
                    bytes_resultado += len(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))
    usos = list(vistos.values())
    entrada = lambda u: u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    final = usos[-1] if usos else {}
    return {
        "transcript": str(path),
        "duracion_s": round((max(tiempos) - min(tiempos)).total_seconds()) if tiempos else 0,
        "turnos": len(usos),
        "llamadas": sum(llamadas.values()),
        "llamadas_sancho": sum(v for k, v in llamadas.items() if "Sancho" in k or "sancho" in k),
        "por_herramienta": dict(llamadas.most_common()),
        "bytes_resultados": bytes_resultado,
        "tokens_contexto_inicial": entrada(usos[0]) if usos else 0,
        "tokens_contexto_final": entrada(final) + final.get("output_tokens", 0),
        "tokens_entrada_procesados": sum(entrada(u) for u in usos),
        "tokens_salida": sum(u.get("output_tokens", 0) for u in usos),
    }


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args == ["--ultimo"]:
        todos = sorted(pathlib.Path.home().glob(".claude/projects/*/*/subagents/agent-*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not todos:
            sys.exit("no hay transcripts de subagentes en esta máquina")
        args = [str(todos[-1])]
    for a in args:
        print(json.dumps(medir(a), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
