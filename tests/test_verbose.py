import os
import sys

# Ensure package root on path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from condensation.dataclasses import Layer, Assembly, Climate
from condensation.core import analyze

def test_analyze_verbose_produces_proof():
    layer = Layer("ins", d=0.1, lambda_=0.04, mu=20, rho=100, xr_percent=5, xmax_percent=20)
    assembly = Assembly(layers=[layer], Rsi=0.13, Rse=0.04)
    climate = Climate(theta_i=20, phi_i=65, theta_e=5, phi_e=90)
    res = analyze(assembly, climate, tk_hours=1, tu_hours=1, verbose=True)
    assert "proof" in res
    assert any("R_total" in step or "U =" in step for step in res["proof"])
