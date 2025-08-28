from __future__ import annotations

from pathlib import Path
import csv
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
MATERIALS_CSV = ROOT / 'context' / 'materials.csv'


def _require_float(s: str | float | int | None, field: str, row: int) -> float:
    """Parse *s* as float or raise ``ValueError`` with row context."""
    if s is None or str(s).strip() == "":
        raise ValueError(f"Missing value for {field!r} in row {row}")
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip().replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    try:
        return float(txt)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid number for {field!r} in row {row}: {s}") from exc


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
        for idx, row in enumerate(rdr, start=2):  # header is row 1
            if not any(row.values()):
                continue
            name = (row.get('name') or row.get('Name') or '').strip()
            if not name:
                raise ValueError(f"Missing value for 'name' in row {idx}")
            try:
                out.append({
                    'name': name,
                    'lambda_': _require_float(row.get('lambda') or row.get('Lambda') or row.get('lambda_'), 'lambda', idx),
                    'mu': _require_float(row.get('mu') or row.get('Mu'), 'mu', idx),
                    'rho': _require_float(row.get('rho') or row.get('Rho'), 'rho', idx),
                    'xr_percent': _require_float(row.get('xr_percent') or row.get('xr') or row.get('xr%'), 'xr_percent', idx),
                    'xmax_percent': _require_float(row.get('xmax_percent') or row.get('xmax') or row.get('xmax%'), 'xmax_percent', idx),
                })
            except ValueError as exc:
                raise ValueError(f"Error parsing materials.csv: {exc}")
    return out

