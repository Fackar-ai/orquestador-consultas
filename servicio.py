"""
Lógica principal de la plataforma (sin interfaz).

    consultar_antecedentes(cedula, fuentes, nombre="") -> dict

- Consulta SOLO las fuentes que pide el usuario, en paralelo.
- Cada fuente deja su PDF en salida/<documento>_<fecha>/.
- Reintenta automáticamente los fallos pasajeros (página caída, captcha caducado,
  respuesta rechazada por el control de calidad).
- Escribe resumen.json con el estado, motivo, intentos y tiempo de cada fuente.

La usan main.py (línea de comandos), lote.py (CSV) y la API.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import config
from consultas import FUENTES, FUENTES_REQUIEREN_NOMBRE

# Estados en los que vale la pena volver a intentar: el fallo no es de la cédula
# (PREGUNTA_SIN_RESOLVER y RESPUESTA_RECHAZADA: al reintentar, el portal plantea otra pregunta)
ESTADOS_REINTENTABLES = {"PAGINA_CAIDA", "TIEMPO_CAPTCHA_CADUCADO",
                         "PREGUNTA_SIN_RESOLVER", "RESPUESTA_RECHAZADA"}


class SolicitudInvalida(ValueError):
    """Datos de entrada incorrectos (documento, fuentes o nombre)."""


def crear_carpeta_unica(base: Path) -> Path:
    """Crea la carpeta; si ya existe (mismo segundo) usa base_2, base_3, ..."""
    candidata, n = base, 1
    while True:
        try:
            candidata.mkdir(parents=True, exist_ok=False)
            return candidata
        except FileExistsError:
            n += 1
            candidata = base.with_name(f"{base.name}_{n}")


def normalizar_fuentes(fuentes) -> list[str]:
    if isinstance(fuentes, str):
        fuentes = re.split(r"[,\s]+", fuentes)
    limpias = []
    for f in fuentes:
        f = str(f).strip().lower()
        if not f:
            continue
        if f in {"todas", "todo", "all"}:
            return list(FUENTES)
        if f not in FUENTES:
            raise SolicitudInvalida(f"Fuente desconocida: '{f}'. Opciones: {', '.join(FUENTES)} o 'todas'.")
        if f not in limpias:
            limpias.append(f)
    if not limpias:
        raise SolicitudInvalida("Debes elegir al menos una fuente.")
    return limpias


def validar_cedula(cedula) -> str:
    cedula = re.sub(r"[.\s]", "", str(cedula or ""))
    if not re.fullmatch(r"\d{5,12}", cedula):
        raise SolicitudInvalida("La cédula debe tener solo números (entre 5 y 12 dígitos).")
    return cedula


def _consultar_fuente(fuente: str, cedula: str, carpeta, nombre: str) -> dict:
    """Ejecuta una fuente con reintentos y nunca lanza excepciones."""
    funcion = FUENTES[fuente]
    intentos_max = 1 + max(0, config.REINTENTOS_POR_FUENTE)
    t0 = time.perf_counter()
    resultado = {}

    for intento in range(1, intentos_max + 1):
        try:
            resultado = funcion(cedula=cedula, carpeta_salida=carpeta, nombre=nombre) or {}
        except Exception as e:  # red de seguridad: un módulo nunca debe tumbar el resto
            resultado = {"estado": "ERROR", "ruta": None, "motivo": f"{type(e).__name__}: {e}"[:300]}

        resultado.setdefault("estado", "ERROR")
        resultado.setdefault("ruta", None)
        resultado.setdefault("motivo", "")
        resultado["intentos"] = intento

        if resultado["estado"] not in ESTADOS_REINTENTABLES or intento == intentos_max:
            break
        print(f"[{fuente}] {resultado['estado']} -> reintento {intento + 1}/{intentos_max} "
              f"en {config.SEGUNDOS_ENTRE_REINTENTOS} s")
        time.sleep(config.SEGUNDOS_ENTRE_REINTENTOS)

    resultado["segundos"] = round(time.perf_counter() - t0, 1)
    return resultado


def consultar_antecedentes(cedula, fuentes, nombre: str = "", en_paralelo: bool = True) -> dict:
    cedula = validar_cedula(cedula)
    fuentes = normalizar_fuentes(fuentes)
    nombre = (nombre or "").strip()

    necesitan_nombre = [f for f in fuentes if f in FUENTES_REQUIEREN_NOMBRE]
    if necesitan_nombre and len(nombre.split()) < 2:
        raise SolicitudInvalida(
            f"El nombre completo es obligatorio para: {', '.join(necesitan_nombre)} "
            "(mínimo nombre y apellido).")

    inicio = datetime.now()
    carpeta = crear_carpeta_unica(Path(config.CARPETA_SALIDA) / f"{cedula}_{inicio:%Y%m%d_%H%M%S}")

    t0 = time.perf_counter()
    if en_paralelo and len(fuentes) > 1:
        with ThreadPoolExecutor(max_workers=len(fuentes)) as pool:
            futuros = {f: pool.submit(_consultar_fuente, f, cedula, carpeta, nombre) for f in fuentes}
            resultados = {f: futuro.result() for f, futuro in futuros.items()}
    else:
        resultados = {f: _consultar_fuente(f, cedula, carpeta, nombre) for f in fuentes}

    exitosas = [f for f, r in resultados.items() if r["estado"] == "EXITOSO"]
    resumen = {
        "cedula": cedula,
        "fuentes_pedidas": fuentes,
        "inicio": inicio.isoformat(timespec="seconds"),
        "segundos_total": round(time.perf_counter() - t0, 1),
        "carpeta": str(carpeta),
        "exitosas": exitosas,
        "fallidas": [f for f in fuentes if f not in exitosas],
        "resultados": resultados,
    }

    with open(carpeta / "resumen.json", "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=2, default=str)

    return resumen
