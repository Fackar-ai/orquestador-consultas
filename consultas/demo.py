"""
Fuentes DEMO: simulan portales externos para poder ejecutar y probar el
orquestador sin acceder a ningún sistema real.

Cada fuente simula, de forma configurable (ver config.DEMO_*):
  - latencia variable (como un portal real),
  - caídas pasajeras (PAGINA_CAIDA, TIEMPO_CAPTCHA_CADUCADO) -> el servicio reintenta,
  - respuestas "genéricas" que NO son un certificado -> el control de calidad
    las detecta y las marca RESPUESTA_RECHAZADA en lugar de EXITOSO.

Las integraciones con portales reales viven en un repositorio privado y
cumplen exactamente la misma interfaz:
    consultar(cedula, carpeta_salida, nombre="") -> {"estado", "ruta", "motivo", ...}
"""

import html
import random
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config

# Marca que solo aparece cuando la respuesta trae el certificado de verdad.
# (En el caso real que inspiró esto, un error en la pregunta de verificación
#  devolvía una página genérica que antes se entregaba como "EXITOSO".)
MARCA_CERTIFICADO = 'class="datos-consultado"'


def contiene_certificado(respuesta_html: str) -> bool:
    """Control de calidad: ¿la respuesta es un certificado o una página genérica?"""
    return MARCA_CERTIFICADO in (respuesta_html or "")


@dataclass
class FuenteDemo:
    nombre: str
    titulo: str
    latencia_seg: tuple[float, float]
    fallos_posibles: list[str] = field(default_factory=lambda: ["PAGINA_CAIDA"])
    requiere_nombre: bool = False
    _intentos: Counter = field(default_factory=Counter, repr=False)
    _candado: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------------ API
    def consultar(self, cedula: str, carpeta_salida, nombre: str = "") -> dict:
        rng = self._rng(cedula)
        time.sleep(rng.uniform(*self.latencia_seg) * config.DEMO_FACTOR_LATENCIA)

        fallo = rng.choice(self.fallos_posibles) if rng.random() < config.DEMO_PROB_FALLO else None

        if fallo in {"PAGINA_CAIDA", "TIEMPO_CAPTCHA_CADUCADO"}:
            return {"estado": fallo, "ruta": None, "motivo": f"Simulado: {fallo.lower().replace('_', ' ')}"}

        respuesta = self._respuesta_generica() if fallo == "RESPUESTA_GENERICA" \
            else self._respuesta_certificado(cedula, nombre)

        if not contiene_certificado(respuesta):
            return {"estado": "RESPUESTA_RECHAZADA", "ruta": None,
                    "motivo": "La respuesta no contiene el certificado (página genérica)"}

        ruta = Path(carpeta_salida) / f"{self.nombre}_{cedula}.pdf"
        _crear_pdf(ruta, self.titulo, cedula, nombre)
        return {"estado": "EXITOSO", "ruta": str(ruta), "motivo": ""}

    # ------------------------------------------------------------ internos
    def _rng(self, cedula: str) -> random.Random:
        if not config.DEMO_SEMILLA:
            return random.Random()
        # Reproducible, pero distinto en cada intento (si no, un reintento repetiría el mismo fallo)
        with self._candado:
            self._intentos[cedula] += 1
            intento = self._intentos[cedula]
        return random.Random(f"{config.DEMO_SEMILLA}-{self.nombre}-{cedula}-{intento}")

    def _respuesta_certificado(self, cedula: str, nombre: str) -> str:
        return (f'<div {MARCA_CERTIFICADO}>{html.escape(nombre or "N/A")} - '
                f'{cedula}</div><h2>NO REGISTRA ANOTACIONES (DATOS FICTICIOS)</h2>')

    @staticmethod
    def _respuesta_generica() -> str:
        return "<p>Señor(a) ciudadano(a): la expedición del certificado es gratuita.</p>"


def _crear_pdf(ruta: Path, titulo: str, cedula: str, nombre: str) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    ruta.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(ruta), pagesize=A4)
    ancho, alto = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(ancho / 2, alto - 90, titulo)
    c.setFont("Helvetica", 11)
    c.drawCentredString(ancho / 2, alto - 120, f"Documento: {cedula}")
    if nombre:
        c.drawCentredString(ancho / 2, alto - 138, f"Nombre: {nombre}")
    c.drawCentredString(ancho / 2, alto - 170, "NO REGISTRA ANOTACIONES")
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(ancho / 2, 60, f"DOCUMENTO DE DEMOSTRACIÓN - datos ficticios - {datetime.now():%Y-%m-%d %H:%M}")
    c.save()


# Cuatro tipos de fuente, con perfiles inspirados en los tiempos reales medidos
JUDICIAL = FuenteDemo("judicial", "Certificado de antecedentes judiciales (DEMO)", (8, 18),
                      ["PAGINA_CAIDA", "TIEMPO_CAPTCHA_CADUCADO"])
DISCIPLINARIA = FuenteDemo("disciplinaria", "Certificado de antecedentes disciplinarios (DEMO)", (3, 10),
                           ["PAGINA_CAIDA", "RESPUESTA_GENERICA"], requiere_nombre=True)
FISCAL = FuenteDemo("fiscal", "Certificado de antecedentes fiscales (DEMO)", (1, 3), ["PAGINA_CAIDA"])
TRANSITO = FuenteDemo("transito", "Estado de cuenta de multas de tránsito (DEMO)", (8, 20), ["PAGINA_CAIDA"])
