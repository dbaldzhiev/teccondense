import math
import os
import sys

# Ensure the package root is on the import path when running via PyTest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from condensation.dataclasses import Layer, Assembly, Climate
from condensation.core import drying_check, analyze


def build_condensing_assembly():
    layers = [
        Layer(name="layer1", d=0.05, lambda_=0.04, mu=50, rho=200, xr_percent=5, xmax_percent=20),
        Layer(name="layer2", d=0.05, lambda_=0.04, mu=10, rho=200, xr_percent=5, xmax_percent=20),
    ]
    return Assembly(layers=layers, Rsi=0.13, Rse=0.04)


def build_non_condensing_assembly():
    layer = Layer(name="ins", d=0.1, lambda_=0.04, mu=100, rho=100, xr_percent=5, xmax_percent=20)
    return Assembly(layers=[layer], Rsi=0.13, Rse=0.04)


def test_drying_check_compares_capacity_with_condensate():
    assembly = build_condensing_assembly()
    climate = Climate(theta_i=20, phi_i=100, theta_e=0, phi_e=50)
    # With default drying climate and short tu, capacity is zero -> not OK
    assert not drying_check(assembly, climate, tk_hours=1, tu_hours=1)
    # Large tu with strong reverse gradient provides enough capacity
    drying_climate = Climate(theta_i=30, phi_i=10, theta_e=0, phi_e=90)
    assert drying_check(
        assembly, climate, tk_hours=1, tu_hours=1e20, drying_climate=drying_climate
    )


def test_analyze_reports_drying_ok():
    cond_assembly = build_condensing_assembly()
    cond_climate = Climate(theta_i=20, phi_i=100, theta_e=0, phi_e=50)
    res = analyze(cond_assembly, cond_climate, tk_hours=1, tu_hours=1)
    assert res["drying_ok"] is False

    # Scenario with no condensation should report True
    clear_assembly = build_non_condensing_assembly()
    mild_climate = Climate(theta_i=20, phi_i=80, theta_e=-10, phi_e=50)
    res2 = analyze(clear_assembly, mild_climate, tk_hours=1, tu_hours=1)
    assert res2["drying_ok"] is True
