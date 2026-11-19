"""
PUNTO DE ENTRADA (línea de comandos).

Ejemplos:
    python main.py --cedula 1234567890 --fuentes fiscal
    python main.py --cedula 1234567890 --fuentes judicial transito
    python main.py --cedula 1234567890 --fuentes todas --nombre "JUAN PEREZ GOMEZ"
    python main.py            (sin argumentos: te pregunta los datos)

Los PDF quedan en salida/<cedula>_<fecha>/ junto con resumen.json.
"""

import argparse
import sys

from consultas import FUENTES
from servicio import SolicitudInvalida, consultar_antecedentes


def _pedir_datos_por_consola():
    cedula = input("Cédula: ").strip()
    print(f"Fuentes disponibles: {', '.join(FUENTES)} (o 'todas')")
    fuentes = input("¿Qué fuentes consultar? (separadas por espacio): ").strip()
    nombre = input("Nombre completo (obligatorio para algunas fuentes, Enter para omitir): ").strip()
    return cedula, fuentes, nombre


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Consulta de antecedentes por fuente (devuelve un PDF por fuente).")
    parser.add_argument("--cedula", help="Número de cédula (solo números).")
    parser.add_argument("--fuentes", nargs="+", help=f"Una o varias: {' '.join(FUENTES)} | todas")
    parser.add_argument("--nombre", default="", help="Nombre completo (obligatorio para algunas fuentes, p. ej. disciplinaria).")
    parser.add_argument("--secuencial", action="store_true", help="Consultar una fuente tras otra (útil para depurar).")
    args = parser.parse_args(argv)

    if args.cedula and args.fuentes:
        cedula, fuentes, nombre = args.cedula, args.fuentes, args.nombre
    else:
        cedula, fuentes, nombre = _pedir_datos_por_consola()

    try:
        resumen = consultar_antecedentes(cedula, fuentes, nombre=nombre, en_paralelo=not args.secuencial)
    except SolicitudInvalida as e:
        print(f"\n❌ {e}")
        return 2

    print("\n" + "=" * 70)
    print(f"Cédula {resumen['cedula']}  |  {resumen['segundos_total']} s  |  {resumen['carpeta']}")
    print("=" * 70)
    for fuente, r in resumen["resultados"].items():
        icono = "✅" if r["estado"] == "EXITOSO" else "❌"
        detalle = r["ruta"] if r["estado"] == "EXITOSO" else ""
        if r.get("motivo"):
            detalle = f"{detalle}  ⚠️ {r['motivo']}" if detalle else r["motivo"]
        print(f"{icono} {fuente:<13} {r['estado']:<24} ({r['segundos']} s, {r['intentos']} intento/s)  {detalle}")

    return 0 if not resumen["fallidas"] else 1


if __name__ == "__main__":
    sys.exit(main())
