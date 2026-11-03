#!/usr/bin/env python3
"""Descarga los datos oficiales que usa La calculadora del bolsillo.

Fuentes:
- API del INDEC (api.indec.gob.ar), si existe la variable INDEC_API_TOKEN.
- API de Series de Tiempo de datos.gob.ar (sin token), como respaldo y control.
Genera data/datos.json.

Uso:  python3 scripts/actualizar_datos.py
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://apis.datos.gob.ar/series/api/series/"
DESDE = "2017-01-01"
SALIDA = Path(__file__).resolve().parent.parent / "data" / "datos.json"
RESUMEN = SALIDA.parent / "indec_resumen.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Regiones del IPC: código en la serie -> nombre
REGIONES = {
    "NAL": "Total país",
    "GBA": "GBA (CABA y conurbano)",
    "ANA": "Pampeana (incluye Córdoba, Santa Fe, La Pampa, Entre Ríos y el interior de Buenos Aires)",
    "NOA": "Noroeste",
    "NEA": "Noreste",
    "UYO": "Cuyo",
    "NIA": "Patagonia",
}
# El sufijo numérico de cada serie cambia según la región
AJUSTE_REGION = {"NAL": 0, "ANA": 0, "GBA": -5, "NOA": -5, "NEA": -5, "UYO": -4, "NIA": 1}

# Rubros (divisiones) del IPC: código, nombre corto, sufijo base
RUBROS = [
    ("ALIMEN", "Alimentos y bebidas", 45),
    ("VIVIEN", "Vivienda y servicios (alquiler, luz, gas, agua)", 52),
    ("TRANSP", "Transporte y combustible", 23),
    ("SALUD", "Salud y prepaga", 18),
    ("EDUCAC", "Educación", 22),
    ("PRENDA", "Ropa y calzado", 35),
    ("RESTAU", "Restaurantes y salidas a comer", 33),
    ("RECREA", "Recreación y cultura", 31),
    ("COMUNI", "Celular, internet y comunicaciones", 27),
    ("EQUIPA", "Equipamiento y mantenimiento del hogar", 46),
    ("BEBIDA", "Bebidas alcohólicas y tabaco", 39),
    ("BIENES", "Otros bienes y servicios", 36),
]
NIVEL_GENERAL_BASE = 26
# Segunda opción para el nivel general (otro conjunto del mismo IPC)
NIVEL_GENERAL_ALT = {
    "NAL": "145.3_INGNACNAL_DICI_M_15", "ANA": "145.3_INGPAMANA_DICI_M_15",
    "GBA": "145.3_INGGBAGBA_DICI_M_10", "NOA": "145.3_INGNOANOA_DICI_M_10",
    "NEA": "145.3_INGNEANEA_DICI_M_10", "UYO": "145.3_INGCUYUYO_DICI_M_11",
    "NIA": "145.3_INGPATNIA_DICI_M_16",
}

SALARIOS = {
    "total": ("149.1_TL_INDIIOS_OCTU_0_21", "Todos los asalariados"),
    "registrado": ("149.1_TL_REGIADO_OCTU_0_16", "Asalariados registrados (en blanco)"),
    "privado": ("149.1_SOR_PRIADO_OCTU_0_25", "Registrados del sector privado"),
    "publico": ("149.1_SOR_PUBICO_OCTU_0_14", "Sector público"),
    "no_registrado": ("149.1_SOR_PRIADO_OCTU_0_28", "No registrados (en negro)"),
}


def pedir(ids):
    params = {"ids": ",".join(ids), "start_date": DESDE, "limit": 1000, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    for intento in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "calculadora-bolsillo/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            print(f"  reintento {intento + 1}: {e}", file=sys.stderr)
            time.sleep(3 * (intento + 1))
    raise SystemExit(f"No se pudo descargar: {ids}")


def a_columnas(respuesta, n):
    """Convierte la respuesta en {fecha 'AAAA-MM': [v1..vn]}."""
    filas = {}
    for fila in respuesta["data"]:
        filas[fila[0][:7]] = [None if v is None else round(v, 4) for v in fila[1:1 + n]]
    return filas


def llenos(serie):
    return sum(v is not None for v in serie)


def mejor_serie(candidatas):
    """Devuelve el id con más datos entre varias opciones (algunas vienen vacías)."""
    mejor, mejor_n = None, 0
    for sid in candidatas:
        try:
            filas = a_columnas(pedir([sid]), 1)
        except SystemExit:
            continue
        n = sum(v[0] is not None for v in filas.values())
        if n > mejor_n:
            mejor, mejor_n = sid, n
    return mejor


def base_vacia(fuente):
    return {
        "fuente": fuente,
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "regiones": REGIONES,
        "rubros": [{"id": c, "nombre": n} for c, n, _ in RUBROS],
        "ipc": {},
        "salarios": {"series": {k: v[1] for k, v in SALARIOS.items()}},
    }


def desde_datos_gob():
    """Datos desde la API de Series de Tiempo (sin token)."""
    datos = base_vacia("INDEC, vía API de Series de Tiempo (datos.gob.ar)")
    for reg, nombre in REGIONES.items():
        aj = AJUSTE_REGION[reg]
        general = mejor_serie([f"148.3_INIVEL{reg}_DICI_M_{NIVEL_GENERAL_BASE + aj}", NIVEL_GENERAL_ALT[reg]])
        if not general:
            raise SystemExit(f"Sin nivel general para {reg}")
        ids = [general] + [f"146.3_I{c}{reg}_DICI_M_{b + aj}" for c, _, b in RUBROS]
        print(f"IPC {nombre[:20]}…")
        filas = a_columnas(pedir(ids), len(ids))
        fechas = sorted(filas)
        datos["ipc"][reg] = {
            "fechas": fechas,
            "general": [filas[f][0] for f in fechas],
            "rubros": {c: [filas[f][i + 1] for f in fechas] for i, (c, _, _) in enumerate(RUBROS)},
        }
    print("Salarios…")
    claves = list(SALARIOS)
    filas = a_columnas(pedir([SALARIOS[k][0] for k in claves]), len(claves))
    fechas = sorted(filas)
    datos["salarios"]["fechas"] = fechas
    for i, k in enumerate(claves):
        datos["salarios"][k] = [filas[f][i] for f in fechas]
    return datos


def completar(datos):
    """Rellena rubros vacíos y controla que los datos no estén rotos."""
    # Algunos rubros regionales vienen vacíos en la fuente. Se completan con el
    # dato nacional del rubro y, si tampoco está, con el nivel general de la región.
    # Se anota cada reemplazo para mostrarlo en la página.
    nac = datos["ipc"]["NAL"]
    for reg in ["NAL"] + [r for r in datos["ipc"] if r != "NAL"]:
        bloque = datos["ipc"][reg]
        bloque["sustitutos"] = {}
        assert bloque["fechas"] == nac["fechas"], f"Fechas distintas en {reg}"
        for c, _, _ in RUBROS:
            serie = bloque["rubros"][c]
            if llenos(serie) >= len(serie) - 1 and serie[-1] is not None:
                continue
            if reg != "NAL" and c not in nac["sustitutos"] and nac["rubros"][c][-1] is not None and llenos(nac["rubros"][c]) >= len(serie) - 1:
                bloque["rubros"][c] = list(nac["rubros"][c])
                bloque["sustitutos"][c] = "nacional"
            else:
                bloque["rubros"][c] = list(bloque["general"])
                bloque["sustitutos"][c] = "general"
    assert set(datos["ipc"]) == set(REGIONES), "Faltan regiones"
    assert len(nac["fechas"]) > 100, "Muy pocos meses de IPC"
    for reg, b in datos["ipc"].items():
        assert all(v is not None for v in b["general"][-13:]), f"Faltan meses recientes del IPC en {reg}"
    sal = datos["salarios"]
    assert sal["total"][-1] is not None or sal["total"][-2] is not None, "Falta el índice de salarios"
    return datos


def coinciden(a, b):
    """Compara el IPC nacional de dos fuentes en los meses que tienen en común."""
    fa = dict(zip(a["ipc"]["NAL"]["fechas"], a["ipc"]["NAL"]["general"]))
    fb = dict(zip(b["ipc"]["NAL"]["fechas"], b["ipc"]["NAL"]["general"]))
    comunes = [f for f in sorted(set(fa) & set(fb)) if fa[f] and fb[f]][-24:]
    if len(comunes) < 12:
        return False
    return all(abs(fa[f] / fb[f] - 1) < 0.005 for f in comunes)


def main():
    respaldo = None
    try:
        respaldo = completar(desde_datos_gob())
    except (AssertionError, SystemExit, KeyError, ValueError) as e:
        print(f"datos.gob.ar no sirvió esta vez: {e}")

    datos = respaldo
    token = os.environ.get("INDEC_API_TOKEN", "").strip()
    if token:
        try:
            import indec_api
            nuevo = completar(indec_api.descargar(token, base_vacia("INDEC, Catálogo API-INDEC (api.indec.gob.ar)"),
                                                  REGIONES, RUBROS, SALARIOS, RESUMEN))
            if respaldo is None or coinciden(nuevo, respaldo):
                datos = nuevo
                print("Usando la API del INDEC.")
            else:
                print("La API del INDEC no coincide con datos.gob.ar en los meses comunes; se usa datos.gob.ar.")
        except Exception as e:  # noqa: BLE001  (nunca romper la actualización por la API nueva)
            print(f"API del INDEC: no se pudo usar ({type(e).__name__}: {e}). Se usa datos.gob.ar.")
    else:
        print("Sin INDEC_API_TOKEN: se usa datos.gob.ar.")

    if datos is None:
        raise SystemExit("Ninguna fuente funcionó; los datos anteriores quedan como estaban.")

    # Si los números no cambiaron, no se toca el archivo (así no hay cambios vacíos)
    if SALIDA.exists():
        try:
            viejo = json.loads(SALIDA.read_text(encoding="utf-8"))
            if {**viejo, "actualizado": None} == {**datos, "actualizado": None}:
                print("Sin datos nuevos; datos.json queda igual.")
                return
        except ValueError:
            pass

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Listo: {SALIDA} ({SALIDA.stat().st_size // 1024} KB). Fuente: {datos['fuente']}. "
          f"Último IPC: {datos['ipc']['NAL']['fechas'][-1]}, último salario: {datos['salarios']['fechas'][-1]}")


if __name__ == "__main__":
    main()
