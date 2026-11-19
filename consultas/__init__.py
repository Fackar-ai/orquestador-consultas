"""
Registro de fuentes.

Todas exponen la misma función:
    consultar(cedula, carpeta_salida, nombre="") -> {"estado", "ruta", "motivo", ...}

En este repositorio público solo hay fuentes DEMO (consultas/demo.py).
Las integraciones reales implementan la misma interfaz y se registran aquí.
"""

from .demo import DISCIPLINARIA, FISCAL, JUDICIAL, TRANSITO

_FUENTES_DEMO = [JUDICIAL, DISCIPLINARIA, FISCAL, TRANSITO]

FUENTES = {f.nombre: f.consultar for f in _FUENTES_DEMO}

# Fuentes que necesitan el nombre completo (p. ej. preguntas de verificación)
FUENTES_REQUIEREN_NOMBRE = {f.nombre for f in _FUENTES_DEMO if f.requiere_nombre}
