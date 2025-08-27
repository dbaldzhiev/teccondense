"""Normative table lookups (from provided Excel tables).

- Tab. 2.2: p_max(T) saturation vapor pressure [Pa] as a function of T [°C]
- Tab. 2.1: θs (dew/surface threshold) [°C] as a function of θi [°C] and φi [%]

Implements lightweight XLSX readers via zip + XML to avoid heavy deps.
If files are not present or parsing fails, functions return None so callers
can fall back to analytical formulas (e.g., Magnus).
"""
from __future__ import annotations

from typing import Optional, Dict, List, Tuple
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import csv


ROOT = Path(__file__).resolve().parents[1]
T2_2_XLSX = ROOT / 'context' / 't2-2.xlsx'
T2_1_XLSX = ROOT / 'context' / 't2-1.xlsx'
T2_2_CSV = ROOT / 'context' / 't2-2.csv'
T2_1_CSV = ROOT / 'context' / 't2-1.csv'

_SST_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def _read_xlsx_cells(path: Path) -> List[Dict[str, str]]:
    """Return list of rows; each row is {cell_ref: value_string}.

    Resolves shared strings and returns raw text (no number formatting).
    """
    with zipfile.ZipFile(path) as z:
        ws = z.read('xl/worksheets/sheet1.xml')
        sst = z.read('xl/sharedStrings.xml')
    sst_root = ET.fromstring(sst)
    strings: List[str] = []
    for si in sst_root.iter(f'{_SST_NS}si'):
        t = ''.join(n.text or '' for n in si.iter(f'{_SST_NS}t'))
        strings.append(t)
    root = ET.fromstring(ws)
    sheet_data = root.find(f'{_SST_NS}sheetData')
    rows_el = list(sheet_data.iter(f'{_SST_NS}row')) if sheet_data is not None else []
    rows: List[Dict[str, str]] = []
    for r in rows_el:
        row_map: Dict[str, str] = {}
        for c in r.iter(f'{_SST_NS}c'):
            ref = c.attrib.get('r', '')
            t = c.attrib.get('t')
            v = c.find(f'{_SST_NS}v')
            if v is None or v.text is None:
                continue
            if t == 's':
                try:
                    idx = int(v.text)
                    row_map[ref] = strings[idx]
                except Exception:
                    row_map[ref] = ''
            else:
                row_map[ref] = v.text
        rows.append(row_map)
    return rows


def _read_csv_rows(path: Path) -> List[List[str]]:
    with path.open('r', encoding='utf-8') as f:
        rdr = csv.reader(f)
        rows = [row for row in rdr if any(cell.strip() for cell in row)]
    return rows


def _to_float(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.strip().replace('\u00a0', ' ').replace(' ', '')
    # replace comma decimal separator
    s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None


# Cache containers
_pmax_table: Optional[Tuple[List[float], Dict[float, float]]] = None
_thetas_table: Optional[Tuple[List[float], List[float], List[List[float]]]] = None


def _ensure_pmax_table() -> bool:
    global _pmax_table
    if _pmax_table is not None:
        return True
    # Prefer CSV if available
    if T2_2_CSV.exists():
        try:
            rows_csv = _read_csv_rows(T2_2_CSV)
            mapping: Dict[float, float] = {}
            temps: List[float] = []
            for row in rows_csv:
                if not row:
                    continue
                base = _to_float(row[0])
                if base is None:
                    continue
                for j in range(1, min(11, len(row))):
                    v = _to_float(row[j])
                    if v is None:
                        continue
                    T = base + 0.1 * (j - 1)
                    if T not in mapping:  # keep first occurrence for duplicates
                        mapping[T] = v
                        temps.append(T)
            temps_sorted = sorted(set(temps))
            if temps_sorted:
                _pmax_table = (temps_sorted, mapping)
                return True
        except Exception:
            pass
    # Fallback to XLSX if present
    if not T2_2_XLSX.exists():
        return False
    try:
        rows = _read_xlsx_cells(T2_2_XLSX)
        decs: List[float] = []
        for col in 'BCDEFGHIJK':
            v = rows[2].get(f'{col}3')
            f = _to_float(v) if v is not None else None
            if f is None:
                return False
            decs.append(f)
        mapping: Dict[float, float] = {}
        temps: List[float] = []
        for r_idx in range(4, len(rows)):
            a = rows[r_idx].get('A' + str(r_idx + 1))
            base = _to_float(a) if a is not None else None
            if base is None:
                continue
            for j, col in enumerate('BCDEFGHIJK'):
                v = rows[r_idx].get(f'{col}{r_idx+1}')
                p_pa = _to_float(v)
                if p_pa is None:
                    continue
                T = base + decs[j]
                if T not in mapping:
                    mapping[T] = p_pa
                    temps.append(T)
        temps_sorted = sorted(set(temps))
        _pmax_table = (temps_sorted, mapping)
        return True
    except Exception:
        _pmax_table = None
        return False


def _interp1(x: float, xs: List[float], mapping: Dict[float, float]) -> Optional[float]:
    if not xs:
        return None
    # Clamp endpoints
    if x <= xs[0]:
        return mapping.get(xs[0])
    if x >= xs[-1]:
        return mapping.get(xs[-1])
    # Find bracketing indices
    for i in range(1, len(xs)):
        if x <= xs[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = mapping[x0], mapping[x1]
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return None


def p_max_tabulated(T_celsius: float) -> Optional[float]:
    """Return p_max(T) in Pa using Tab. 2.2, or None if table unavailable."""
    if not _ensure_pmax_table():
        return None
    xs, mapping = _pmax_table  # type: ignore
    return _interp1(T_celsius, xs, mapping)  # type: ignore


def _ensure_thetas_table() -> bool:
    global _thetas_table
    if _thetas_table is not None:
        return True
    # Prefer CSV if available
    if T2_1_CSV.exists():
        try:
            rows_csv = _read_csv_rows(T2_1_CSV)
            # No header assumed; columns: base θi, then 14 values for φ=30..95 step 5
            phis = [float(p) for p in range(30, 100, 5)]
            thetas: List[float] = []
            grid: List[List[float]] = []
            for row in rows_csv:
                if not row:
                    continue
                base = _to_float(row[0])
                if base is None:
                    continue
                vals: List[float] = []
                for j in range(1, min(1 + len(phis), len(row))):
                    v = _to_float(row[j])
                    if v is None:
                        vals.append(float('nan'))
                    else:
                        vals.append(v)
                # If shorter than phis, pad with NaN
                if len(vals) < len(phis):
                    vals.extend([float('nan')] * (len(phis) - len(vals)))
                thetas.append(base)
                grid.append(vals)
            if thetas:
                order = sorted(range(len(thetas)), key=lambda i: thetas[i])
                thetas_sorted = [thetas[i] for i in order]
                grid_sorted = [grid[i] for i in order]
                _thetas_table = (thetas_sorted, phis, grid_sorted)
                return True
        except Exception:
            pass
    # Fallback to XLSX if present
    if not T2_1_XLSX.exists():
        return False
    try:
        rows = _read_xlsx_cells(T2_1_XLSX)
        # Header φ in row 3: B3.. up to O3
        phis: List[float] = []
        cols = 'BCDEFGHIJKLMNO'
        for col in cols:
            v = rows[2].get(f'{col}3')
            f = _to_float(v) if v is not None else None
            if f is None:
                return False
            phis.append(f)
        thetas: List[float] = []
        grid: List[List[float]] = []
        for r_idx in range(3, len(rows)):
            a = rows[r_idx].get('A' + str(r_idx + 1))
            theta_i = _to_float(a) if a is not None else None
            if theta_i is None:
                continue
            row_vals: List[float] = []
            for col in cols:
                v = rows[r_idx].get(f'{col}{r_idx+1}')
                f = _to_float(v) if v is not None else None
                if f is None:
                    row_vals.append(float('nan'))
                else:
                    row_vals.append(f)
            if any(v == v for v in row_vals):
                thetas.append(theta_i)
                grid.append(row_vals)
        order = sorted(range(len(thetas)), key=lambda i: thetas[i])
        thetas_sorted = [thetas[i] for i in order]
        grid_sorted = [grid[i] for i in order]
        _thetas_table = (thetas_sorted, phis, grid_sorted)
        return True
    except Exception:
        _thetas_table = None
        return False


def _interp2(x: float, y: float, xs: List[float], ys: List[float], grid: List[List[float]]) -> Optional[float]:
    # Clamp to bounds
    if not xs or not ys:
        return None
    # Find i such that xs[i0] <= x <= xs[i1]
    if x <= xs[0]:
        i0, i1 = 0, 0
    elif x >= xs[-1]:
        i0, i1 = len(xs) - 1, len(xs) - 1
    else:
        i1 = next(i for i in range(1, len(xs)) if x <= xs[i])
        i0 = i1 - 1
    if y <= ys[0]:
        j0, j1 = 0, 0
    elif y >= ys[-1]:
        j0, j1 = len(ys) - 1, len(ys) - 1
    else:
        j1 = next(j for j in range(1, len(ys)) if y <= ys[j])
        j0 = j1 - 1
    x0, x1 = xs[i0], xs[i1]
    y0, y1 = ys[j0], ys[j1]
    f00 = grid[i0][j0]
    f01 = grid[i0][j1]
    f10 = grid[i1][j0]
    f11 = grid[i1][j1]
    if i0 == i1 and j0 == j1:
        return f00
    if i0 == i1:
        # linear in y only
        ty = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
        return f00 + ty * (f01 - f00)
    if j0 == j1:
        # linear in x only
        tx = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
        return f00 + tx * (f10 - f00)
    # bilinear
    tx = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
    ty = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
    f0 = f00 + tx * (f10 - f00)
    f1 = f01 + tx * (f11 - f01)
    return f0 + ty * (f1 - f0)


def theta_s_tabulated(theta_i: float, phi_i: float) -> Optional[float]:
    """Return θs (°C) from Tab. 2.1 for given θi and φi, or None if table unavailable."""
    if not _ensure_thetas_table():
        return None
    thetas, phis, grid = _thetas_table  # type: ignore
    return _interp2(theta_i, phi_i, thetas, phis, grid)  # type: ignore
