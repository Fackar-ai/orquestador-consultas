import json
import os
import time
from pathlib import Path

import pytest

import config
import servicio
from consultas.demo import contiene_certificado
from servicio import SolicitudInvalida, consultar_antecedentes, crear_carpeta_unica


# ---------------------------------------------------------------- validaciones
@pytest.mark.parametrize("entrada, esperado", [
    ("1000000001", "1000000001"),
    ("1.000.000.001", "1000000001"),
    (" 12345 ", "12345"),
])
def test_cedula_valida(entrada, esperado):
    assert servicio.validar_cedula(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "abc", "123", "1234567890123", "12-345"])
def test_cedula_invalida(entrada):
    with pytest.raises(SolicitudInvalida):
        servicio.validar_cedula(entrada)


def test_fuentes_todas_y_sin_duplicados():
    assert servicio.normalizar_fuentes("todas") == list(servicio.FUENTES)
    assert servicio.normalizar_fuentes("fiscal, Fiscal judicial") == ["fiscal", "judicial"]
    assert servicio.normalizar_fuentes(["transito"]) == ["transito"]


@pytest.mark.parametrize("entrada", ["", "inexistente", ["fiscal", "otra"]])
def test_fuentes_invalidas(entrada):
    with pytest.raises(SolicitudInvalida):
        servicio.normalizar_fuentes(entrada)


def test_nombre_obligatorio_solo_donde_hace_falta():
    with pytest.raises(SolicitudInvalida, match="disciplinaria"):
        consultar_antecedentes("123456", "disciplinaria", nombre="SOLONOMBRE")
    # fiscal no necesita nombre
    assert consultar_antecedentes("123456", "fiscal")["exitosas"] == ["fiscal"]


# ------------------------------------------------------------- flujo completo
def test_todas_las_fuentes_demo_generan_pdf_y_resumen():
    r = consultar_antecedentes("1000000001", "todas", nombre="NOMBRE APELLIDO")
    assert r["fallidas"] == []
    for fuente, res in r["resultados"].items():
        assert res["estado"] == "EXITOSO", fuente
        assert Path(res["ruta"]).read_bytes().startswith(b"%PDF")
    resumen = json.loads((Path(r["carpeta"]) / "resumen.json").read_text(encoding="utf-8"))
    assert resumen["exitosas"] == r["exitosas"]


# ------------------------------------------------------------------ reintentos
def _fuente_que_falla(veces, estado_fallo, contador):
    def consultar(cedula, carpeta_salida, nombre=""):
        contador["n"] += 1
        if contador["n"] <= veces:
            return {"estado": estado_fallo, "ruta": None, "motivo": "simulado"}
        return {"estado": "EXITOSO", "ruta": "x.pdf", "motivo": ""}
    return consultar


def test_reintenta_fallo_pasajero_y_se_recupera(monkeypatch):
    contador = {"n": 0}
    monkeypatch.setitem(servicio.FUENTES, "fiscal", _fuente_que_falla(1, "PAGINA_CAIDA", contador))
    res = consultar_antecedentes("123456", "fiscal")["resultados"]["fiscal"]
    assert (res["estado"], res["intentos"]) == ("EXITOSO", 2)


def test_no_reintenta_errores_definitivos(monkeypatch):
    contador = {"n": 0}
    monkeypatch.setitem(servicio.FUENTES, "fiscal", _fuente_que_falla(5, "FORMULARIO_CAMBIADO", contador))
    res = consultar_antecedentes("123456", "fiscal")["resultados"]["fiscal"]
    assert (res["estado"], res["intentos"], contador["n"]) == ("FORMULARIO_CAMBIADO", 1, 1)


def test_respeta_el_limite_de_reintentos(monkeypatch):
    monkeypatch.setattr(config, "REINTENTOS_POR_FUENTE", 2)
    contador = {"n": 0}
    monkeypatch.setitem(servicio.FUENTES, "fiscal", _fuente_que_falla(99, "TIEMPO_CAPTCHA_CADUCADO", contador))
    res = consultar_antecedentes("123456", "fiscal")["resultados"]["fiscal"]
    assert (res["estado"], res["intentos"]) == ("TIEMPO_CAPTCHA_CADUCADO", 3)


def test_una_excepcion_no_tumba_las_demas_fuentes(monkeypatch):
    def revienta(**_):
        raise RuntimeError("boom")
    monkeypatch.setitem(servicio.FUENTES, "transito", revienta)
    r = consultar_antecedentes("123456", "transito fiscal")
    assert r["resultados"]["transito"]["estado"] == "ERROR"
    assert "boom" in r["resultados"]["transito"]["motivo"]
    assert r["resultados"]["fiscal"]["estado"] == "EXITOSO"


# -------------------------------------------------------------------- paralelo
def test_las_fuentes_se_consultan_en_paralelo(monkeypatch):
    def lenta(cedula, carpeta_salida, nombre=""):
        time.sleep(0.4)
        return {"estado": "EXITOSO", "ruta": "x.pdf", "motivo": ""}
    for f in servicio.FUENTES:
        monkeypatch.setitem(servicio.FUENTES, f, lenta)

    t0 = time.perf_counter()
    consultar_antecedentes("123456", "todas", nombre="NOMBRE APELLIDO")
    assert time.perf_counter() - t0 < 1.0  # en serie serían ~1.6 s


# ------------------------------------------------------------------ utilidades
def test_control_de_calidad_detecta_pagina_generica():
    assert contiene_certificado('<div class="datos-consultado">X</div>')
    assert not contiene_certificado("<p>Señor(a) ciudadano(a): ... es gratuita.</p>")
    assert not contiene_certificado("")


def test_carpetas_no_se_pisan(tmp_path):
    base = tmp_path / "123_20261119_000000"
    nombres = [crear_carpeta_unica(base).name for _ in range(3)]
    assert nombres == [base.name, f"{base.name}_2", f"{base.name}_3"]
    assert all(os.path.isdir(tmp_path / n) for n in nombres)
