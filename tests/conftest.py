import pytest

import config


@pytest.fixture(autouse=True)
def entorno_de_pruebas(tmp_path, monkeypatch):
    """Cada test escribe en una carpeta temporal y sin esperas reales."""
    monkeypatch.setattr(config, "CARPETA_SALIDA", tmp_path / "salida")
    monkeypatch.setattr(config, "SEGUNDOS_ENTRE_REINTENTOS", 0)
    monkeypatch.setattr(config, "REINTENTOS_POR_FUENTE", 1)
    monkeypatch.setattr(config, "DEMO_FACTOR_LATENCIA", 0)
    monkeypatch.setattr(config, "DEMO_PROB_FALLO", 0)
    monkeypatch.setattr(config, "DEMO_SEMILLA", "")
    return tmp_path
