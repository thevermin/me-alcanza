"""Descarga del IPC y del índice de salarios desde el Catálogo API-INDEC.

La API es PostgREST: https://api.indec.gob.ar/v1/<tabla>?filtros, con
"Authorization: Bearer <token>" y hasta 1000 filas por pedido.

Como la API es nueva, este módulo no da por sentados los nombres exactos de
regiones, rubros ni tipos de indicador: los descubre mirando el último mes y
deja un resumen (sin datos privados) en data/indec_resumen.json para revisarlo.
"""
import json
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.indec.gob.ar/v1/"
CLAVE_IPC = ("clasificador,nivel,codigo,descripcion,periodo,anio,mes,indicador,"
             "tipo_de_indicador,tipo_de_indicador_descripcion,region,unidad_de_medida")
CLAVE_SAL = ("clasificador,nivel,codigo,descripcion,periodo,anio,mes,indicador,"
             "tipo_de_indicador,tipo_de_indicador_descripcion,unidad_de_medida")

# Cómo reconocer cada región por su nombre
REGION_PALABRAS = {
    "NAL": ["nacional", "total pais", "total del pais", "pais"],
    "GBA": ["gba", "gran buenos aires"],
    "ANA": ["pampeana"],
    "NOA": ["noroeste"],
    "NEA": ["noreste", "nordeste"],
    "UYO": ["cuyo"],
    "NIA": ["patagonia", "patagonica"],
}
# Cómo reconocer cada división del IPC (COICOP) por su nombre
RUBRO_PALABRAS = {
    "ALIMEN": ["alimentos y bebidas no alcoholicas"],
    "BEBIDA": ["bebidas alcoholicas y tabaco"],
    "PRENDA": ["prendas de vestir y calzado"],
    "VIVIEN": ["vivienda, agua, electricidad"],
    "EQUIPA": ["equipamiento y mantenimiento del hogar"],
    "SALUD": ["salud"],
    "TRANSP": ["transporte"],
    "COMUNI": ["comunicacion"],
    "RECREA": ["recreacion y cultura"],
    "EDUCAC": ["educacion"],
    "RESTAU": ["restaurantes y hoteles", "hoteles y restaurantes"],
    "BIENES": ["bienes y servicios varios"],
}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().replace(" ", " ").split())


class Cliente:
    def __init__(self, token):
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/json",
                  "User-Agent": "calculadora-bolsillo/1.0"}

    def get(self, tabla, params):
        url = BASE + tabla + "?" + urllib.parse.urlencode(params, safe=",.()*\"", quote_via=urllib.parse.quote)
        for intento in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=self.h), timeout=90) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                cuerpo = e.read()[:300].decode("utf-8", "replace")
                if e.code in (401, 403):
                    raise RuntimeError(f"el INDEC rechazó el token (HTTP {e.code}). Revisá que el secreto esté bien copiado y no haya vencido.") from None
                if e.code == 400:
                    raise RuntimeError(f"pedido inválido a {tabla}: {cuerpo}") from None
                espera = 5 * (intento + 1)
            except (urllib.error.URLError, TimeoutError) as e:
                cuerpo, espera = str(e), 5 * (intento + 1)
            print(f"  INDEC {tabla}: reintento {intento + 1} ({cuerpo[:80]})")
            time.sleep(espera)
        raise RuntimeError(f"no respondió {tabla}")

    def todo(self, tabla, filtros, clave, columnas):
        filas, offset = [], 0
        while True:
            lote = self.get(tabla, {**filtros, "select": columnas, "order": clave, "limit": 1000, "offset": offset})
            filas += lote
            if len(lote) < 1000:
                return filas
            offset += 1000
            if offset > 200000:
                raise RuntimeError(f"demasiadas filas en {tabla}")


def elegir_tipo_indice(filas):
    """Entre los tipos de indicador, el que es un índice (no una variación ni una incidencia)."""
    tipos = {}
    for f in filas:
        tipos.setdefault((f["tipo_de_indicador"], f.get("tipo_de_indicador_descripcion")), []).append(f)
    candidatos = []
    for (tipo, desc), fs in tipos.items():
        texto = norm(f"{tipo} {desc}")
        if "indice" in texto and "variacion" not in texto and "incidencia" not in texto:
            valores = [f["valor"] for f in fs if isinstance(f.get("valor"), (int, float))]
            if valores and max(valores) > 150:  # base 100: un índice de hoy es mucho mayor que 100
                candidatos.append((len(fs), tipo))
    if not candidatos:
        raise RuntimeError(f"no encontré el tipo 'índice'. Tipos vistos: {sorted({str(t) for t, _ in tipos})}")
    return max(candidatos)[1]


def region_de(texto):
    t = norm(texto)
    for clave, palabras in REGION_PALABRAS.items():
        if any(p == t or p in t for p in palabras):
            return clave
    return None


def rubro_de(texto):
    t = norm(texto)
    if "nivel general" in t:
        return "GENERAL"
    for clave, palabras in RUBRO_PALABRAS.items():
        if any(t == p or t.startswith(p) for p in palabras):
            return clave
    return None


def a_fecha(periodo):
    p = str(periodo).replace("-", "")
    return f"{p[:4]}-{p[4:6]}"


def descargar(token, datos, regiones, rubros, salarios_def, archivo_resumen):
    cli = Cliente(token)
    resumen = {}

    # 1) Último mes del IPC y sus filas, para descubrir nombres y códigos
    ultimo = cli.get("ipc_nacional", {"select": "periodo", "order": "periodo.desc", "limit": 1})[0]["periodo"]
    muestra = cli.todo("ipc_nacional", {"periodo": f"eq.{ultimo}"}, CLAVE_IPC,
                       "clasificador,nivel,codigo,descripcion,tipo_de_indicador,tipo_de_indicador_descripcion,region,valor")
    tipo = elegir_tipo_indice(muestra)
    resumen["ipc"] = {
        "ultimo_periodo": ultimo,
        "tipos": sorted({f"{f['tipo_de_indicador']} | {f.get('tipo_de_indicador_descripcion')}" for f in muestra}),
        "regiones": sorted({str(f["region"]) for f in muestra}),
        "niveles": sorted({str(f["nivel"]) for f in muestra}),
        "clasificadores": sorted({str(f["clasificador"]) for f in muestra}),
        "tipo_elegido": tipo,
    }

    # Filas que sirven: índice, nivel general o división, de una región conocida.
    # Si un nombre aparece en varios niveles (p. ej. "Salud"), se queda el nivel más agregado.
    elegidas = {}
    for f in muestra:
        if f["tipo_de_indicador"] != tipo:
            continue
        reg, rub = region_de(f["region"]), rubro_de(f["descripcion"])
        if not reg or not rub:
            continue
        clave = (reg, rub)
        nivel = norm(f["nivel"])
        prioridad = 0 if ("general" in nivel or "divis" in nivel) else 1
        if clave not in elegidas or prioridad < elegidas[clave][0]:
            elegidas[clave] = (prioridad, f)
    resumen["ipc"]["combinaciones_encontradas"] = len(elegidas)
    resumen["ipc"]["mapa"] = {f"{r}/{u}": f"{f['codigo']} · {f['descripcion']} · {f['region']} · {f['nivel']}"
                              for (r, u), (_, f) in sorted(elegidas.items())}
    faltan_general = [r for r in regiones if (r, "GENERAL") not in elegidas]
    if faltan_general:
        raise RuntimeError(f"no encontré el nivel general de {faltan_general}. Regiones vistas: {resumen['ipc']['regiones']}")

    # 2) Serie completa de esas filas
    codigos = sorted({f["codigo"] for _, f in elegidas.values()})
    clasif = sorted({f["clasificador"] for _, f in elegidas.values()})
    filtros = {"tipo_de_indicador": f"eq.{tipo}",
               "codigo": "in.(" + ",".join(f'"{c}"' for c in codigos) + ")",
               "clasificador": "in.(" + ",".join(f'"{c}"' for c in clasif) + ")"}
    filas = cli.todo("ipc_nacional", filtros, CLAVE_IPC, "clasificador,nivel,codigo,descripcion,periodo,region,valor")
    buscado = {(f["clasificador"], f["nivel"], f["codigo"], f["region"]): clave for clave, (_, f) in elegidas.items()}
    series = {}
    for f in filas:
        clave = buscado.get((f["clasificador"], f["nivel"], f["codigo"], f["region"]))
        if clave and f.get("valor") is not None:
            series.setdefault(clave, {})[a_fecha(f["periodo"])] = round(float(f["valor"]), 4)
    fechas = sorted(series[("NAL", "GENERAL")])
    for reg in regiones:
        datos["ipc"][reg] = {
            "fechas": fechas,
            "general": [series.get((reg, "GENERAL"), {}).get(m) for m in fechas],
            "rubros": {c: [series.get((reg, c), {}).get(m) for m in fechas] for c, _, _ in rubros},
        }

    # 3) Índice de salarios
    ult_s = cli.get("indice_salarios", {"select": "periodo", "order": "periodo.desc", "limit": 1})[0]["periodo"]
    muestra_s = cli.todo("indice_salarios", {"periodo": f"eq.{ult_s}"}, CLAVE_SAL,
                         "clasificador,nivel,codigo,descripcion,tipo_de_indicador,tipo_de_indicador_descripcion,valor")
    tipo_s = elegir_tipo_indice(muestra_s)
    resumen["salarios"] = {
        "ultimo_periodo": ult_s,
        "tipos": sorted({f"{f['tipo_de_indicador']} | {f.get('tipo_de_indicador_descripcion')}" for f in muestra_s}),
        "descripciones": sorted({str(f["descripcion"]) for f in muestra_s if f["tipo_de_indicador"] == tipo_s}),
        "tipo_elegido": tipo_s,
    }

    def clave_salario(desc):
        t = norm(desc)
        if "no registrado" in t:
            return "no_registrado"
        if "publico" in t:
            return "publico"
        if "privado" in t:
            return "privado"
        if "registrado" in t:
            return "registrado"
        if "total" in t or "nivel general" in t or t == "indice de salarios":
            return "total"
        return None

    elegidas_s = {}
    for f in muestra_s:
        if f["tipo_de_indicador"] == tipo_s:
            k = clave_salario(f["descripcion"])
            if k and k not in elegidas_s:
                elegidas_s[k] = f
    resumen["salarios"]["mapa"] = {k: f"{f['codigo']} · {f['descripcion']}" for k, f in elegidas_s.items()}
    if "total" not in elegidas_s:
        raise RuntimeError(f"no encontré el índice de salarios total. Vistas: {resumen['salarios']['descripciones']}")
    cods = sorted({f["codigo"] for f in elegidas_s.values()})
    filas_s = cli.todo("indice_salarios", {"tipo_de_indicador": f"eq.{tipo_s}",
                                           "codigo": "in.(" + ",".join(f'"{c}"' for c in cods) + ")"},
                       CLAVE_SAL, "clasificador,nivel,codigo,descripcion,periodo,valor")
    por_clave = {(f["clasificador"], f["nivel"], f["codigo"]): k for k, f in elegidas_s.items()}
    ss = {}
    for f in filas_s:
        k = por_clave.get((f["clasificador"], f["nivel"], f["codigo"]))
        if k and f.get("valor") is not None:
            ss.setdefault(k, {})[a_fecha(f["periodo"])] = round(float(f["valor"]), 4)
    fechas_s = sorted(ss["total"])
    datos["salarios"]["fechas"] = fechas_s
    for k in salarios_def:
        datos["salarios"][k] = [ss.get(k, {}).get(m) for m in fechas_s]

    archivo_resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"API del INDEC: IPC hasta {fechas[-1]}, salarios hasta {fechas_s[-1]}. Resumen en {archivo_resumen.name}")
    return datos
