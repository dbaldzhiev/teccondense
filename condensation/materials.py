from __future__ import annotations

from pathlib import Path
import csv
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
MATERIALS_CSV = ROOT / 'context' / 'materials.csv'


def _to_float(s: str | float | int | None, default: float = 0.0) -> float:
    if s is None:
        return default
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace('\u00a0', ' ').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return default


def load_materials() -> List[Dict[str, float | str]]:
    """Load material presets from context/materials.csv if present.

    Expected columns (case-insensitive, flexible order):
    name, lambda, mu, rho, xr_percent, xmax_percent
    """
    if not MATERIALS_CSV.exists():
        return []
    out: List[Dict[str, float | str]] = []
    with MATERIALS_CSV.open('r', encoding='utf-8') as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            if not any(row.values()):
                continue
            name = (row.get('name') or row.get('Name') or '').strip()
            if not name:
                continue
            out.append({
                'name': name,
                'lambda_': _to_float(row.get('lambda') or row.get('Lambda') or row.get('lambda_'), 0.0),
                'mu': _to_float(row.get('mu') or row.get('Mu'), 1.0),
                'rho': _to_float(row.get('rho') or row.get('Rho'), 1000.0),
                'xr_percent': _to_float(row.get('xr_percent') or row.get('xr') or row.get('xr%'), 5.0),
                'xmax_percent': _to_float(row.get('xmax_percent') or row.get('xmax') or row.get('xmax%'), 20.0),
            })
    return out

