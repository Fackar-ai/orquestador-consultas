"""
PROCESAMIENTO POR LOTES desde un CSV.

Lee un CSV con cédulas, consulta cada una con las fuentes elegidas y deja:
    salida/<cedula>_<fecha>/...pdf          (un PDF por fuente, igual que main.py)
    salida/lote_<fecha>/resultados.csv      (una fila por cédula con el estado de cada fuente)

El CSV de entrada solo necesita una columna CEDULA (o "cedula").
Opcionales: NOMBRE (obligatorio para algunas fuentes) y FUENTES
(si una fila trae FUENTES, manda sobre --fuentes; ej. "judicial transito").
Detecta solo el separador (, o ;) y la codificación (UTF-8 o la de Excel).

Ejemplos:
    python lote.py ejemplos/lote_ejemplo.csv --fuentes judicial fiscal
    python lote.py mi_lote.csv --fuentes todas --limite 3      (solo las 3 primeras filas)
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from consultas import FUENTES
from servicio import SolicitudInvalida, consultar_antecedentes, crear_carpeta_unica


def _leer_csv(ruta: Path) -> list[dict]:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            texto = ruta.read_text(encoding=codificacion)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit(f"No pude leer {ruta}: codificación desconocida.")

    primera_linea = texto.splitlines()[0] if texto else ""
    separador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
    filas = list(csv.DictReader(texto.splitlines(), delimiter=separador))

    # Normaliza nombres de columna: "cedula", " CEDULA " -> "CEDULA"
    return [{(k or "").strip().upper(): (v or "").strip() for k, v in fila.items()} for fila in filas]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Consulta por lotes desde un CSV.")
    parser.add_argument("csv", help="Ruta del CSV de entrada (columna CEDULA; opcionales NOMBRE y FUENTES).")
    parser.add_argument("--fuentes", nargs="+", default=["todas"],
                        help=f"Fuentes por defecto: {' '.join(FUENTES)} | todas")
    parser.add_argument("--limite", type=int, default=0, help="Procesar solo las N primeras filas (0 = todas).")
    parser.add_argument("--pausa", type=float, default=2.0, help="Segundos de pausa entre cédulas.")
    args = parser.parse_args(argv)

    ruta = Path(args.csv)
    if not ruta.exists():
        print(f"❌ No existe {ruta}")
        return 2

    filas = _leer_csv(ruta)
    if filas and "CEDULA" not in filas[0]:
        print(f"❌ El CSV no tiene columna CEDULA. Columnas encontradas: {', '.join(filas[0])}")
        return 2
    if args.limite:
        filas = filas[: args.limite]

    carpeta_lote = crear_carpeta_unica(Path(config.CARPETA_SALIDA) / f"lote_{datetime.now():%Y%m%d_%H%M%S}")
    ruta_resultados = carpeta_lote / "resultados.csv"

    columnas = (["FILA", "CEDULA", "FUENTES", "SEGUNDOS", "EXITOSAS", "FALLIDAS"]
                + [f"ESTADO_{f.upper()}" for f in FUENTES]
                + [f"MOTIVO_{f.upper()}" for f in FUENTES]
                + ["CARPETA", "ERROR"])

    print(f"Lote: {len(filas)} cédula(s) de {ruta.name}  ->  {ruta_resultados}\n")
    contadores = {"ok": 0, "parcial": 0, "fallo": 0}
    t_lote = time.perf_counter()

    with open(ruta_resultados, "w", newline="", encoding="utf-8-sig") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas, delimiter=";")
        escritor.writeheader()

        for i, fila in enumerate(filas, start=1):
            cedula = fila.get("CEDULA", "")
            fuentes = fila.get("FUENTES") or args.fuentes
            salida = {"FILA": i, "CEDULA": cedula,
                      "FUENTES": fuentes if isinstance(fuentes, str) else " ".join(fuentes)}
            print(f"[{i}/{len(filas)}] {cedula} ...")

            try:
                r = consultar_antecedentes(cedula, fuentes, nombre=fila.get("NOMBRE", ""))
                salida.update({
                    "SEGUNDOS": r["segundos_total"],
                    "EXITOSAS": " ".join(r["exitosas"]),
                    "FALLIDAS": " ".join(r["fallidas"]),
                    "CARPETA": r["carpeta"],
                })
                for fuente, res in r["resultados"].items():
                    salida[f"ESTADO_{fuente.upper()}"] = res["estado"]
                    salida[f"MOTIVO_{fuente.upper()}"] = (res.get("motivo") or "")[:200]
                    icono = "✅" if res["estado"] == "EXITOSO" else "❌"
                    aviso = f"  ⚠️ {res['motivo']}" if res.get("motivo") else ""
                    print(f"      {icono} {fuente:<13} {res['estado']:<24} {res['segundos']} s{aviso}")
                clave = "ok" if not r["fallidas"] else ("parcial" if r["exitosas"] else "fallo")
            except SolicitudInvalida as e:
                salida["ERROR"] = str(e)
                print(f"      ❌ {e}")
                clave = "fallo"
            except Exception as e:  # no cortar el lote por una fila
                salida["ERROR"] = f"{type(e).__name__}: {e}"[:300]
                print(f"      ❌ Error inesperado: {salida['ERROR']}")
                clave = "fallo"

            contadores[clave] += 1
            escritor.writerow(salida)
            fh.flush()  # si se corta el lote, lo hecho ya queda guardado

            if i < len(filas):
                time.sleep(args.pausa)

    minutos = (time.perf_counter() - t_lote) / 60
    print(f"\nTerminado en {minutos:.1f} min: {contadores['ok']} completas, "
          f"{contadores['parcial']} parciales, {contadores['fallo']} fallidas.")
    print(f"Resultados: {ruta_resultados}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
