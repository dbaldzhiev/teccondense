import sys
from pathlib import Path
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from condensation import materials


def test_load_materials_parses_csv(tmp_path, monkeypatch):
    csv_text = (
        "name,lambda,mu,rho,xr_percent,xmax_percent\n"
        "Sample,0.5,5,1000,1,2\n"
    )
    f = tmp_path / "materials.csv"
    f.write_text(csv_text, encoding="utf-8")
    monkeypatch.setattr(materials, "MATERIALS_CSV", f)
    data = materials.load_materials()
    assert data == [
        {
            "name": "Sample",
            "lambda_": 0.5,
            "mu": 5.0,
            "rho": 1000.0,
            "xr_percent": 1.0,
            "xmax_percent": 2.0,
        }
    ]


def test_load_materials_raises_on_bad_row(tmp_path, monkeypatch):
    csv_text = (
        "name,lambda,mu,rho,xr_percent,xmax_percent\n"
        "Bad,not_a_number,5,1000,1,2\n"
    )
    f = tmp_path / "materials.csv"
    f.write_text(csv_text, encoding="utf-8")
    monkeypatch.setattr(materials, "MATERIALS_CSV", f)
    with pytest.raises(ValueError):
        materials.load_materials()
