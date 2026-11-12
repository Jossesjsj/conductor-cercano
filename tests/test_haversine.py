"""Pruebas de la fórmula de Haversine propia."""

from __future__ import annotations

import math

import pytest

from algoritmos.haversine import RADIO_TERRESTRE_METROS, calcular_haversine


def test_coordenadas_identicas():
    assert calcular_haversine(-12.1211, -77.0297, -12.1211, -77.0297) == 0.0


def test_distancia_pequena_un_milesimo_de_grado_de_latitud():
    # 0.001° de latitud ≈ R·π/180·0.001 ≈ 111.195 m
    esperado = RADIO_TERRESTRE_METROS * math.radians(0.001)
    assert calcular_haversine(-12.120, -77.03, -12.121, -77.03) == pytest.approx(esperado, rel=1e-9)


def test_distancia_entre_distritos_plaza_de_armas_a_parque_kennedy():
    # Plaza Mayor de Lima → Parque Kennedy (Miraflores): ≈ 8.4 km en línea recta.
    distancia = calcular_haversine(-12.0464, -77.0428, -12.1211, -77.0297)
    assert 8_300 < distancia < 8_500


def test_simetria_y_coordenadas_diferentes():
    a = calcular_haversine(-12.05, -77.10, -12.20, -76.95)
    b = calcular_haversine(-12.20, -76.95, -12.05, -77.10)
    assert a == pytest.approx(b, rel=1e-12) and a > 0


def test_casos_limite_antipodas_polos_y_antimeridiano():
    assert calcular_haversine(0, 0, 0, 180) == pytest.approx(math.pi * RADIO_TERRESTRE_METROS, rel=1e-12)
    assert calcular_haversine(90, 0, -90, 0) == pytest.approx(math.pi * RADIO_TERRESTRE_METROS, rel=1e-12)
    # Cruce del antimeridiano: 179.9 y -179.9 están a 0.2° de longitud.
    assert calcular_haversine(0, 179.9, 0, -179.9) == pytest.approx(RADIO_TERRESTRE_METROS * math.radians(0.2), rel=1e-9)


def test_coordenadas_invalidas():
    with pytest.raises(ValueError):
        calcular_haversine(95, 0, 0, 0)
    with pytest.raises(ValueError):
        calcular_haversine(0, 0, 0, 181)
