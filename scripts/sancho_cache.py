#!/usr/bin/env python3
"""Caché local de los paquetes de agente de Sancho, verificada por packageHash.

Por qué existe: `get.agent` (formato portable) sirve cada fichero en base64.
Descodificarlo obligaba al agente a reescribir el base64 entero en un comando,
que es lento y caro, y además se repetía en cada arranque. Este script:

- `status <agentId> <packageHash>`: dice si ese paquete ya está en caché y lista
  sus ficheros. Si está, el agente lee de disco y no vuelve a pedir nada a Sancho.
- `save <agentId> <packageHash>`: busca en los transcripts de Claude Code de esta
  máquina las respuestas de `sancho_read` que ya llegaron (manifiesto y ficheros),
  las descodifica, comprueba el sha256 de cada fichero contra el manifiesto y
  escribe en caché solo lo que cuadra. Nadie tiene que reescribir base64.

La copia local verificada por packageHash cuenta como lectura (SAN-2008).
Caché: ~/.claude/sancho-cache/<agentId>/<packageHash>/<ruta del paquete>
"""
import base64
import hashlib
import json
import os
import pathlib
import sys
import time

CACHE = pathlib.Path(os.environ.get("SANCHO_CACHE_DIR", pathlib.Path.home() / ".claude" / "sancho-cache"))
PROJECTS = pathlib.Path.home() / ".claude" / "projects"
VENTANA = 12 * 3600  # solo transcripts tocados en las últimas 12 h


def _objetos(valor):
    """Recorre un JSON y devuelve los dicts de respuestas de get.agent portable."""
    pila = [valor]
    while pila:
        v = pila.pop()
        if isinstance(v, dict):
            if "packageHash" in v and ("files" in v or "file" in v or "resources" in v):
                yield v
            pila.extend(v.values())
        elif isinstance(v, list):
            pila.extend(v)
        elif isinstance(v, str) and "packageHash" in v and v.lstrip().startswith(("{", "[")):
            try:
                pila.append(json.loads(v))
            except ValueError:
                pass


def _fuentes():
    limite = time.time() - VENTANA
    if not PROJECTS.is_dir():
        return
    for p in PROJECTS.rglob("*"):
        if p.suffix not in (".jsonl", ".txt", ".json") or not p.is_file():
            continue
        try:
            if p.stat().st_mtime < limite:
                continue
            with p.open(errors="ignore") as fh:
                for linea in fh:
                    if "packageHash" not in linea:
                        continue
                    try:
                        yield json.loads(linea)
                    except ValueError:
                        continue
        except OSError:
            continue


def _recoger(agent, phash):
    manifiesto, partes = {}, {}
    for raiz in _fuentes():
        for o in _objetos(raiz):
            if o.get("packageHash") != phash or o.get("agentId", agent) != agent:
                continue
            for f in o.get("files") or []:
                manifiesto[f["path"]] = f
            # Una página suelta (resourcePath) o varias (resourcePaths, SAN-2284).
            for f in [o.get("file")] + list(o.get("resources") or []):
                if not isinstance(f, dict) or not f.get("sha256"):
                    continue
                manifiesto.setdefault(f["path"], {"path": f["path"], "sha256": f["sha256"], "bytes": f.get("bytes")})
                if f.get("contentBase64") is not None:
                    partes.setdefault(f["path"], {})[int(f.get("offset") or 0)] = f["contentBase64"]
                elif f.get("encoding") == "utf8" and isinstance(f.get("content"), str) and f["content"]:
                    # encoding=utf8: texto legible; offset sigue en bytes.
                    partes.setdefault(f["path"], {})[int(f.get("offset") or 0)] = base64.b64encode(f["content"].encode("utf-8")).decode()
    return manifiesto, partes


def _dir(agent, phash):
    return CACHE / agent / phash


def status(agent, phash):
    d = _dir(agent, phash)
    ficheros = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != ".manifest.json") if d.is_dir() else []
    if not ficheros:
        print(f"MISS {agent} {phash[:12]}: nada en caché")
        return
    print(f"HIT {agent} {phash[:12]}: {len(ficheros)} ficheros en {d}")
    for f in ficheros:
        print(f"  {d / f}")


def save(agent, phash):
    manifiesto, partes = _recoger(agent, phash)
    d = _dir(agent, phash)
    if (d / ".manifest.json").exists():
        manifiesto = {**json.loads((d / ".manifest.json").read_text()), **manifiesto}
    if manifiesto:
        d.mkdir(parents=True, exist_ok=True)
        (d / ".manifest.json").write_text(json.dumps(manifiesto, ensure_ascii=False))
    if not manifiesto:
        print(f"ERROR: no encuentro ficheros de {agent} {phash[:12]} en los transcripts. Pide antes get.agent con resourcePaths.")
        sys.exit(2)
    guardados, fallos = [], []
    for ruta, trozos in partes.items():
        meta = manifiesto.get(ruta)
        if not meta:
            fallos.append(f"{ruta}: no está en el manifiesto")
            continue
        try:
            datos = b"".join(base64.b64decode(trozos[k]) for k in sorted(trozos))
        except ValueError:
            fallos.append(f"{ruta}: base64 inválido")
            continue
        if hashlib.sha256(datos).hexdigest() != meta["sha256"]:
            fallos.append(f"{ruta}: incompleto o hash distinto ({len(datos)}/{meta['bytes']} bytes); pide las páginas que falten")
            continue
        destino = (d / ruta).resolve()
        if not str(destino).startswith(str(d.resolve()) + os.sep):
            fallos.append(f"{ruta}: ruta fuera del paquete")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        guardados.append(str(destino))
    print(f"Guardados {len(guardados)} ficheros verificados en {d}")
    for g in sorted(guardados):
        print(f"  {g}")
    for f in fallos:
        print(f"  FALLO {f}")


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("status", "save"):
        sys.exit("uso: sancho_cache.py status|save <agentId> <packageHash>")
    _, cmd, agent, phash = sys.argv
    if len(phash) != 64 or any(c not in "0123456789abcdef" for c in phash):
        sys.exit("packageHash inválido")
    (status if cmd == "status" else save)(agent, phash)


if __name__ == "__main__":
    main()
