import os
import sys

# Ensure package root on path for pytest execution
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from condensation.dataclasses import Layer, Assembly, Climate
from condensation.core import condensate_amount


def build_condensing_assembly():
    layers = [
        Layer("layer1", d=0.05, lambda_=0.04, mu=50, rho=200, xr_percent=5, xmax_percent=20),
        Layer("layer2", d=0.05, lambda_=0.04, mu=10, rho=200, xr_percent=5, xmax_percent=20),
    ]
    return Assembly(layers=layers, Rsi=0.13, Rse=0.04)


def build_non_condensing_assembly():
    layer = Layer("ins", d=0.1, lambda_=0.04, mu=100, rho=100, xr_percent=5, xmax_percent=20)
    return Assembly(layers=[layer], Rsi=0.13, Rse=0.04)


def test_condensing_wall_produces_positive_wk():
    assembly = build_condensing_assembly()
    climate = Climate(theta_i=20, phi_i=100, theta_e=0, phi_e=50)
    res = condensate_amount(assembly, climate, tk_hours=1)
    assert res["Wk_total"] > 0
    assert res["layers"][0]["Wk_layer"] > 0


def test_clear_wall_has_zero_wk():
    assembly = build_non_condensing_assembly()
    climate = Climate(theta_i=20, phi_i=80, theta_e=-10, phi_e=50)
    res = condensate_amount(assembly, climate, tk_hours=1)
    assert res["Wk_total"] == 0
    assert all(layer["Wk_layer"] == 0 for layer in res["layers"])

