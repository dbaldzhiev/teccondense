import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from condensation.dataclasses import Layer, Assembly, Climate
from condensation.core import analyze
from condensation import report as rpt

def test_report_contains_charts_and_tables():
    assembly = Assembly(layers=[Layer(name="Layer1", d=0.1, lambda_=0.04, mu=20, rho=800, xr_percent=5, xmax_percent=20)], Rsi=0.13, Rse=0.04)
    climate = Climate(theta_i=20.0, phi_i=65.0, theta_e=5.0, phi_e=90.0)
    results = analyze(assembly, climate)
    results["theta_i"] = climate.theta_i
    results["phi_i"] = climate.phi_i
    html = rpt.report(results)
    assert html.count("<img") >= 2
    assert "id='tab21'" in html
    assert "id='tab22'" in html
    assert "data:image/png;base64" in html
