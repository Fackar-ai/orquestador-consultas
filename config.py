"""
Configuración central. Todo sale de variables de entorno (o del archivo .env,
que nunca se sube a Git). Ningún otro archivo debe tener valores sensibles.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

RAIZ_PROYECTO = Path(__file__).resolve().parent

if load_dotenv:
    load_dotenv(RAIZ_PROYECTO / ".env")


def _texto(nombre: str, por_defecto: str = "") -> str:
    return os.getenv(nombre, por_defecto).strip()


def _entero(nombre: str, por_defecto: int) -> int:
    try:
        return int(_texto(nombre, str(por_defecto)))
    except ValueError:
        return por_defecto


def _decimal(nombre: str, por_defecto: float) -> float:
    try:
        return float(_texto(nombre, str(por_defecto)))
    except ValueError:
        return por_defecto


# Carpeta de resultados: salida/<documento>_<fecha>/
CARPETA_SALIDA = Path(_texto("CARPETA_SALIDA", str(RAIZ_PROYECTO / "salida")))

# Reintentos automáticos ante fallos pasajeros
REINTENTOS_POR_FUENTE = _entero("REINTENTOS_POR_FUENTE", 1)
SEGUNDOS_ENTRE_REINTENTOS = _entero("SEGUNDOS_ENTRE_REINTENTOS", 2)

# --- Simulación (solo fuentes demo) ---
# Probabilidad de que una fuente demo simule una caída o una respuesta inválida
DEMO_PROB_FALLO = _decimal("DEMO_PROB_FALLO", 0.2)
# Multiplica las latencias simuladas (0 = instantáneo, útil en tests)
DEMO_FACTOR_LATENCIA = _decimal("DEMO_FACTOR_LATENCIA", 1.0)
# Semilla para que la simulación sea reproducible (vacío = aleatoria)
DEMO_SEMILLA = _texto("DEMO_SEMILLA")
