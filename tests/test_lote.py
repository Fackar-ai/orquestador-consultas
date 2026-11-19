import csv

import pytest

import config
import lote


def _leer_resultados():
    carpeta = next(config.CARPETA_SALIDA.glob("lote_*"))
    with open(carpeta / "resultados.csv", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


@pytest.mark.parametrize("separador, codificacion", [(";", "utf-8-sig"), (",", "cp1252")])
def test_lote_lee_csv_de_excel_y_continua_tras_errores(tmp_path, separador, codificacion):
    filas = [
        ["CEDULA", "NOMBRE", "FUENTES"],
        ["1000000001", "JOSÉ PÉREZ", "fiscal"],
        ["abc", "", "fiscal"],                    # cédula inválida
        ["1000000003", "", "disciplinaria"],      # falta el nombre
        ["1000000004", "", ""],                   # usa --fuentes
    ]
    ruta = tmp_path / "entrada.csv"
    with open(ruta, "w", encoding=codificacion, newline="") as fh:
        csv.writer(fh, delimiter=separador).writerows(filas)

    assert lote.main([str(ruta), "--fuentes", "transito", "--pausa", "0"]) == 0

    resultados = _leer_resultados()
    assert [r["CEDULA"] for r in resultados] == ["1000000001", "abc", "1000000003", "1000000004"]
    assert resultados[0]["ESTADO_FISCAL"] == "EXITOSO"
    assert "solo números" in resultados[1]["ERROR"]
    assert "nombre completo" in resultados[2]["ERROR"]
    assert resultados[3]["ESTADO_TRANSITO"] == "EXITOSO"


def test_lote_sin_columna_cedula(tmp_path):
    ruta = tmp_path / "malo.csv"
    ruta.write_text("DOCUMENTO;NOMBRE\n123;X\n", encoding="utf-8")
    assert lote.main([str(ruta), "--pausa", "0"]) == 2
