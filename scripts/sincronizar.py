#!/usr/bin/env python3
"""Copia en el repo los paquetes de agente que sirve Sancho (SAN-2284).

Uso (desde la raíz del repo):
  SANCHO_MCP_URL=https://app.sanchocmo.ai/api/mcp/sancho SANCHO_MCP_TOKEN=... \
    python3 scripts/sincronizar.py [agente ...]

Para cada agente compara el packageHash de paquetes/<id>/.sync.json con el de
sync.agents. Si cambió, baja el paquete entero con get.agent (format=portable),
verifica cada fichero por sha256 y sustituye la carpeta. Luego regenera los
stubs de agents/. Si nada cambió no toca nada, así que se puede correr cada día.

El token necesita agents:read y clients:read (o sancho:read). Nunca se pasa como
argumento ni se imprime. Solo usa la biblioteca estándar.
"""
import base64
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PAQUETES = RAIZ / "paquetes"
TIMEOUT = 300


class Sancho:
    """Cliente MCP mínimo (HTTP streamable, JSON-RPC) con token Bearer."""

    def __init__(self, url, token):
        if not url.startswith("https://") and not url.startswith("http://127.0.0.1") and not url.startswith("http://localhost"):
            sys.exit("SANCHO_MCP_URL tiene que ser https")
        self.url, self.token, self.sesion, self.n = url, token, None, 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "sancho-agents-sync", "version": "1"}})
        self._rpc("notifications/initialized", None, notificacion=True)
        self.contratos = {}

    def _rpc(self, metodo, params, notificacion=False):
        cuerpo = {"jsonrpc": "2.0", "method": metodo}
        if params is not None:
            cuerpo["params"] = params
        if not notificacion:
            self.n += 1
            cuerpo["id"] = self.n
        cab = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "Authorization": f"Bearer {self.token}"}
        if self.sesion:
            cab["Mcp-Session-Id"] = self.sesion
        req = urllib.request.Request(self.url, data=json.dumps(cuerpo).encode(), headers=cab, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            self.sesion = r.headers.get("Mcp-Session-Id") or self.sesion
            texto = r.read().decode("utf-8")
            tipo = r.headers.get("Content-Type", "")
        if notificacion:
            return None
        if "text/event-stream" in tipo:
            datos = [l[5:].strip() for l in texto.splitlines() if l.startswith("data:")]
            mensajes = [json.loads(d) for d in datos if d]
            texto_msg = next((m for m in mensajes if m.get("id") == cuerpo["id"]), None)
            respuesta = texto_msg
        else:
            respuesta = json.loads(texto)
        if not respuesta or "error" in respuesta:
            raise RuntimeError(f"{metodo}: {respuesta and respuesta.get('error')}")
        return respuesta["result"]

    def herramienta(self, nombre, argumentos):
        res = self._rpc("tools/call", {"name": nombre, "arguments": argumentos})
        texto = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if res.get("isError"):
            raise RuntimeError(f"{nombre}: {texto[:300]}")
        return json.loads(texto)

    def leer(self, operacion, argumentos):
        if operacion not in self.contratos:
            op = self.herramienta("sancho_get_operation", {"operationId": operacion, "arguments": argumentos})
            self.contratos[operacion] = (op["resource"], op["contractHash"])
        recurso, contrato = self.contratos[operacion]
        return self.herramienta("sancho_read", {"resource": recurso, "operationId": operacion,
                                                "arguments": argumentos, "contractHash": contrato})


def _local(aid):
    f = PAQUETES / aid / ".sync.json"
    return json.loads(f.read_text()) if f.exists() else {}


def bajar(s, aid, phash):
    """Baja el paquete portable entero y lo deja verificado en una carpeta temporal."""
    manifiesto, offset = [], 0
    while offset is not None:
        pag = s.leer("get.agent", {"agentId": aid, "format": "portable", "offset": offset,
                                   **({"packageHash": phash} if offset else {})})
        phash = pag["packageHash"]
        manifiesto += pag["files"]
        offset = pag.get("nextOffset")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"sancho-{aid}-"))
    for meta in manifiesto:
        trozos, offset = [], 0
        while offset is not None:
            f = s.leer("get.agent", {"agentId": aid, "format": "portable", "packageHash": phash,
                                     "resourcePath": meta["path"], "offset": offset, "encoding": "utf8"})["file"]
            trozos.append(f["content"].encode("utf-8") if f.get("encoding") == "utf8" else base64.b64decode(f["contentBase64"]))
            offset = f.get("nextOffset")
        datos = b"".join(trozos)
        if hashlib.sha256(datos).hexdigest() != meta["sha256"]:
            shutil.rmtree(tmp)
            raise RuntimeError(f"{aid}/{meta['path']}: sha256 distinto")
        destino = (tmp / meta["path"]).resolve()
        if not str(destino).startswith(str(tmp.resolve()) + os.sep):
            shutil.rmtree(tmp)
            raise RuntimeError(f"{aid}/{meta['path']}: ruta fuera del paquete")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    return tmp, phash, len(manifiesto)


def main():
    url, token = os.environ.get("SANCHO_MCP_URL", ""), os.environ.get("SANCHO_MCP_TOKEN", "").strip()
    if not url or not token:
        sys.exit("faltan SANCHO_MCP_URL y SANCHO_MCP_TOKEN en el entorno")
    s = Sancho(url, token)
    pedidos = sys.argv[1:] or sorted(p.parent.name for p in PAQUETES.glob("*/.sync.json")) or \
        sorted(p.stem for p in (RAIZ / "agents").glob("*.md"))
    cambios = []
    for aid in pedidos:
        vivo = s.leer("sync.agents", {"only": [aid]})["agents"]
        if not vivo:
            print(f"{aid}: ya no está en el catálogo de Sancho; no lo toco")
            continue
        a = vivo[0]
        if _local(aid).get("packageHash") == a["packageHash"]:
            print(f"{aid}: al día ({a['packageHash'][:12]})")
            continue
        tmp, phash, n = bajar(s, aid, a["packageHash"])
        (tmp / ".sync.json").write_text(json.dumps({
            "id": aid, "title": a.get("title") or aid, "revision": a.get("revision"), "packageHash": phash,
            "skills": a.get("skills", []), "sincronizado": datetime.date.today().isoformat()},
            ensure_ascii=False, indent=2) + "\n")
        destino = PAQUETES / aid
        if destino.exists():
            shutil.rmtree(destino)
        PAQUETES.mkdir(exist_ok=True)
        shutil.move(str(tmp), destino)
        cambios.append(aid)
        print(f"{aid}: actualizado a {phash[:12]} ({n} ficheros)")
    if cambios:
        sys.path.insert(0, str(RAIZ / "scripts"))
        import generar
        generar.desde_paquetes()
    print(f"{len(cambios)} agentes actualizados" + (f": {', '.join(cambios)}" if cambios else ""))


if __name__ == "__main__":
    main()
