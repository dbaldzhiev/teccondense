from .dataclasses import Layer, Assembly, Climate
from typing import List, Tuple, Optional, Dict
import math
from typing import cast

try:
    # Optional tables module providing normative lookups
    from .tables import p_max_tabulated, theta_s_tabulated  # type: ignore
    _HAS_TABLES = True
except Exception:  # pragma: no cover - optional dependency
    p_max_tabulated = None  # type: ignore
    theta_s_tabulated = None  # type: ignore
    _HAS_TABLES = False


def u_value(assembly: Assembly) -> Tuple[float, float]:
    """Return (U, R_total) where R_total includes Rsi, layers, and Rse."""
    R_layers = sum(layer.d / layer.lambda_ for layer in assembly.layers)
    R_total = assembly.Rsi + R_layers + assembly.Rse
    U = 1.0 / R_total if R_total > 0 else float('inf')
    return U, R_total


def temperature_profile(assembly: Assembly, climate: Climate) -> List[float]:
    """Return temperatures at internal/external surfaces and layer interfaces.

    The list always begins with the internal surface temperature (θsi) and ends
    with the external surface temperature (θse). Interfaces after each layer are
    included in between. For constructions without layers the result is
    ``[θsi, θse]``.
    """
    U, R_total = u_value(assembly)
    if not math.isfinite(U) or R_total == 0:
        # Degenerate case: return at least both surface temperatures
        temps = [climate.theta_i] * (len(assembly.layers) + 1)
        temps.append(climate.theta_e)
        return temps

    # Heat flux density (W/m^2)
    q = U * (climate.theta_i - climate.theta_e)

    # Internal surface temperature
    theta_si = climate.theta_i - q * assembly.Rsi
    temps = [theta_si]

    # Interface temperatures after each layer (from inside to outside)
    R_accum = assembly.Rsi
    for layer in assembly.layers:
        R_accum += layer.d / layer.lambda_
        theta_interface = climate.theta_i - q * R_accum
        temps.append(theta_interface)

    # External surface temperature using Rse (θse)
    theta_se = climate.theta_e + q * assembly.Rse
    if assembly.layers:
        # Replace the last interface temperature with θse
        temps[-1] = theta_se
    else:
        # No layers: append θse so both surfaces are present
        temps.append(theta_se)
    return temps


# Vapor permeability of still air at ~10°C in kg/(m·h·Pa)
DELTA_AIR_KG_M_H_PA = 1.86e-7


def z_profile(assembly: Assembly) -> List[float]:
    """Return vapor resistance axis z = Σ(μ·d/δ_air) at surfaces/interfaces.

    Units: m²·Pa·h/kg
    """
    z = [0.0]
    accum = 0.0
    for layer in assembly.layers:
        accum += (layer.mu * layer.d) / DELTA_AIR_KG_M_H_PA
        z.append(accum)
    return z


def thickness_axis(assembly: Assembly) -> List[float]:
    """Return physical thickness axis x = Σ(d) at surfaces/interfaces.

    - Starts at 0 at internal surface.
    - Adds d for each layer to the next interface.
    - Returns [0, after L1, ..., total_thickness]
    """
    xs = [0.0]
    accum = 0.0
    for layer in assembly.layers:
        accum += layer.d
        xs.append(accum)
    return xs


def _p_max_magnus_pa(T: float) -> float:
    """Saturation vapor pressure over water in Pa using Magnus-Tetens approximation."""
    a = 17.625
    b = 243.04  # °C
    es_hPa = 6.112 * math.exp(a * T / (b + T))  # hPa
    return es_hPa * 100.0  # Pa


def p_max(T: float) -> float:
    """Saturation vapor pressure p_max(T) in Pa.

    If table-based interpolation is available, it should be used (Tab. 2.2).
    Fallback to Magnus approximation when table data is unavailable.
    """
    # Prefer table interpolation if available and returns a value
    if _HAS_TABLES and callable(cast(object, p_max_tabulated)):
        try:
            val = cast(object, p_max_tabulated)(T)
            if val is not None:
                return float(val)
        except Exception:
            pass
    return _p_max_magnus_pa(T)


def dew_point(theta: float, phi: float) -> float:
    """Dew point temperature (°C) from air temperature θ (°C) and RH φ (%).

    Fallback to inverse Magnus. If Tab. 2.1 (θs) is available, a lookup-based
    implementation should replace this for surface-risk checks.
    """
    if phi <= 0:
        return -273.15
    a = 17.625
    b = 243.04
    rh = phi / 100.0
    alpha = math.log(rh) + (a * theta) / (b + theta)
    td = (b * alpha) / (a - alpha)
    return td


def partial_pressures(climate: Climate) -> Tuple[float, float]:
    """Return (p_i, p_e) partial vapor pressures in Pa at interior and exterior air."""
    p_i = climate.phi_i / 100.0 * p_max(climate.theta_i)
    p_e = climate.phi_e / 100.0 * p_max(climate.theta_e)
    return p_i, p_e


def vapor_pressure_profile(assembly: Assembly, climate: Climate) -> Tuple[List[float], List[float]]:
    """Linear p(z) profile along z from p_i to p_e per (2.3). p in Pa, z in m²·Pa·h/kg."""
    z_axis = z_profile(assembly)
    if not z_axis:
        return [], []
    p_i, p_e = partial_pressures(climate)
    z_total = z_axis[-1]
    if z_total == 0:
        return z_axis, [p_i for _ in z_axis]
    g0 = (p_i - p_e) / z_total  # kg/(m²·h)
    p_line = [p_i - g0 * z for z in z_axis]
    return z_axis, p_line


def saturation_pressure_profile(temps: List[float]) -> List[float]:
    """Return p_sat(T) in Pa for each temperature in temps."""
    return [p_max(T) for T in temps]


def condensation_zones(p_line: List[float], p_sat_line: List[float], z_axis: List[float]):
    """Detect intervals along axis where p_line > p_sat_line with linear interpolation at crossings.

    Returns list of dicts: {start_z, end_z, max_excess_pa} where z can be Σ(μ·d) or thickness.
    """
    zones = []
    in_zone = False
    start_z: Optional[float] = None
    max_excess = 0.0
    n = min(len(p_line), len(p_sat_line), len(z_axis))
    if n == 0:
        return zones

    def interp_z(i0: int, i1: int) -> float:
        # Linear interpolation z* where p_line - p_sat crosses zero between i0 and i1
        x0, x1 = z_axis[i0], z_axis[i1]
        y0 = p_line[i0] - p_sat_line[i0]
        y1 = p_line[i1] - p_sat_line[i1]
        if y1 == y0:
            return x0
        t = -y0 / (y1 - y0)
        return x0 + t * (x1 - x0)

    prev_excess = p_line[0] - p_sat_line[0]
    for i in range(1, n):
        excess = p_line[i] - p_sat_line[i]
        # Track max within current zone
        if in_zone:
            max_excess = max(max_excess, excess)

        # Check for crossing
        if prev_excess <= 0 < excess and not in_zone:
            # Entering zone: interpolate start
            start_z = interp_z(i - 1, i)
            in_zone = True
            max_excess = excess
        elif prev_excess > 0 and excess <= 0 and in_zone:
            # Exiting zone: interpolate end
            end_z = interp_z(i - 1, i)
            zones.append({"start_z": start_z, "end_z": end_z, "max_excess_pa": max(0.0, max_excess)})
            in_zone = False
            start_z = None
            max_excess = 0.0
        prev_excess = excess

    # If still in zone at end, close at the last coordinate
    if in_zone and start_z is not None:
        zones.append({"start_z": start_z, "end_z": z_axis[n - 1], "max_excess_pa": max(0.0, max_excess)})
    return zones


def condensate_amount(
    assembly: Assembly, climate: Climate, tk_hours: float
) -> Dict[str, object]:
    """Compute condensate mass ``Wk`` over period ``tk``.

    This implementation follows the classic Glaser construction.  The final
    vapour pressure profile is obtained via :func:`glaser_profile` which yields
    the vapour flux immediately before and after each condensation zone.  The
    accumulated mass is ``(g_before - g_after) * tk`` and is distributed across
    the overlapping layers proportionally to their share of the zone.

    Parameters
    ----------
    assembly:
        Layer stack under analysis.
    climate:
        Indoor/outdoor design conditions for the condensation period.
    tk_hours:
        Duration of the condensation period ``tk`` in hours.

    Returns
    -------
    dict
        ``{"Wk_total": float, "layers": [{"index", "Wk_layer",
        "delta_x_percent"}]}``
    """

    gp = glaser_profile(assembly, climate)
    zones = gp.get("zones", [])
    z_axis = z_profile(assembly)

    per_layer_wk = [0.0 for _ in assembly.layers]
    Wk_total = 0.0
    for z in zones:
        dz_zone = max(0.0, z["end_z"] - z["start_z"])
        if dz_zone <= 0:
            continue
        g_before = z.get("g_before", 0.0)
        g_after = z.get("g_after", 0.0)
        Wk_rate = max(0.0, g_before - g_after)  # kg/(m²·h)
        Wk_total += Wk_rate * tk_hours
        for i in range(len(assembly.layers)):
            z0, z1 = z_axis[i], z_axis[i + 1]
            overlap = max(0.0, min(z1, z["end_z"]) - max(z0, z["start_z"]))
            if overlap > 0 and dz_zone > 0:
                per_layer_wk[i] += Wk_rate * tk_hours * (overlap / dz_zone)

    layers_out: List[Dict[str, float]] = []
    for i, layer in enumerate(assembly.layers):
        Wk_layer = per_layer_wk[i]
        dz_phys = max(layer.d, 1e-9)
        rho = max(layer.rho, 1e-9)
        delta_x_percent = Wk_layer / (dz_phys * rho) * 100.0
        layers_out.append({
            "index": float(i),
            "Wk_layer": Wk_layer,
            "delta_x_percent": delta_x_percent,
        })

    return {"Wk_total": Wk_total, "layers": layers_out}


def glaser_profile(assembly: Assembly, climate: Climate) -> Dict[str, object]:
    """Construct Glaser-style condensation-limited p(z) with zones and slopes.

    Returns dict keys: z_axis, p_sat, p_linear, z_final, p_final, zones[{start_z,end_z,g_before,g_after}]
    """
    z_axis, p_lin = vapor_pressure_profile(assembly, climate)
    temps = temperature_profile(assembly, climate)
    p_sat = saturation_pressure_profile(temps)
    if not z_axis:
        return {"z_axis": [], "p_sat": [], "p_linear": [], "z_final": [], "p_final": [], "zones": []}

    # Differences at interfaces
    diff = [pl - ps for pl, ps in zip(p_lin, p_sat)]
    # Find merged condensation intervals [a,b]
    intervals = []  # type: List[Tuple[float, float]]
    for i in range(len(z_axis) - 1):
        z0, z1 = z_axis[i], z_axis[i + 1]
        d0, d1 = diff[i], diff[i + 1]
        if d0 > 0 and d1 > 0:
            if intervals and abs(intervals[-1][1] - z0) < 1e-12:
                intervals[-1] = (intervals[-1][0], z1)
            else:
                intervals.append((z0, z1))
        elif d0 <= 0 < d1:
            # enter zone between z0..z1
            t = 0.0 if (d1 - d0) == 0 else (-d0) / (d1 - d0)
            za = z0 + t * (z1 - z0)
            intervals.append((za, z1))
        elif d0 > 0 >= d1:
            # leave zone
            t = 0.0 if (d1 - d0) == 0 else (-d0) / (d1 - d0)
            zb = z0 + t * (z1 - z0)
            if intervals:
                a, _ = intervals[-1]
                intervals[-1] = (a, zb)
            else:
                intervals.append((z0, zb))

    # Merge overlaps
    merged: List[Tuple[float, float]] = []
    for a, b in intervals:
        if a > b:
            a, b = b, a
        if not merged:
            merged.append((a, b))
        else:
            pa, pb = merged[-1]
            if a <= pb + 1e-12:
                merged[-1] = (pa, max(pb, b))
            else:
                merged.append((a, b))

    if not merged:
        return {"z_axis": z_axis, "p_sat": p_sat, "p_linear": p_lin, "z_final": z_axis, "p_final": p_lin, "zones": []}

    def interp(zq: float, zs: List[float], arr: List[float]) -> float:
        if zq <= zs[0]:
            return arr[0]
        if zq >= zs[-1]:
            return arr[-1]
        for i in range(1, len(zs)):
            if zq <= zs[i]:
                z0, z1 = zs[i - 1], zs[i]
                a0, a1 = arr[i - 1], arr[i]
                t = 0.0 if (z1 - z0) == 0 else (zq - z0) / (z1 - z0)
                return a0 + t * (a1 - a0)
        return arr[-1]

    zones_out: List[Dict[str, float]] = []
    z_final: List[float] = [z_axis[0]]
    p_final: List[float] = [p_lin[0]]

    # Compute slopes and assemble piecewise
    # Leftmost to first a
    a0, b0 = merged[0]
    p_a0 = interp(a0, z_axis, p_sat)
    g_left = (p_final[0] - p_a0) / max(a0 - z_final[0], 1e-12)
    if a0 > z_final[0] + 1e-12:
        z_final.append(a0)
        p_final.append(p_a0)
    last_b = b0
    p_last_b = interp(b0, z_axis, p_sat)
    zones_out.append({"start_z": a0, "end_z": b0, "g_before": g_left, "g_after": 0.0})

    # Middle segments
    for k in range(1, len(merged)):
        a, b = merged[k]
        p_a = interp(a, z_axis, p_sat)
        # linear segment from last_b to a
        g_mid = (p_last_b - p_a) / max(a - last_b, 1e-12)
        z_final.append(a)
        p_final.append(p_a)
        zones_out[-1]["g_after"] = g_mid
        # zone [a,b]
        p_b = interp(b, z_axis, p_sat)
        zones_out.append({"start_z": a, "end_z": b, "g_before": g_mid, "g_after": 0.0})
        last_b, p_last_b = b, p_b

    # Rightmost from last_b to z_total to meet p_e
    z_total = z_axis[-1]
    p_e = p_lin[-1]
    g_right = (p_last_b - p_e) / max(z_total - last_b, 1e-12)
    zones_out[-1]["g_after"] = g_right
    if z_final[-1] < z_total - 1e-12:
        z_final.append(z_total)
        p_final.append(p_e)

    return {"z_axis": z_axis, "p_sat": p_sat, "p_linear": p_lin, "z_final": z_final, "p_final": p_final, "zones": zones_out}


def drying_check(
    assembly: Assembly,
    climate: Climate,
    tk_hours: float,
    tu_hours: float,
    drying_climate: Optional[Climate] = None,
) -> bool:
    """Return True if drying during ``tu`` can remove condensate from ``tk``.

    The function first estimates the amount of condensate accumulated during the
    condensation period ``tk`` using :func:`condensate_amount`.  It
    then computes the reverse vapour flow possible during the drying period
    ``tu`` via :func:`drying_capacity`.  Drying is considered adequate only when
    the drying capacity exceeds the accumulated condensate mass ``Wk_total``.
    """

    wk = condensate_amount(assembly, climate, tk_hours)
    wk_total = float(wk.get("Wk_total", 0.0))
    capacity = float(
        drying_capacity(assembly, tu_hours, drying_climate).get("capacity_kg_m2", 0.0)
    )
    return capacity >= wk_total


def moisture_limits_check(assembly: Assembly, wk_layers: List[Dict[str, float]]) -> List[Dict[str, float | bool]]:
    """Check x_uk' = xr' + Δx_dif < x_max for each layer.

    wk_layers: list of dicts with keys index, delta_x_percent from condensate_amount.
    Returns list of {index, x_uk_prime, x_max, ok}.
    """
    out: List[Dict[str, float | bool]] = []
    for i, layer in enumerate(assembly.layers):
        dx = 0.0
        for row in wk_layers:
            if int(row.get("index", -1)) == i:
                dx = float(row.get("delta_x_percent", 0.0))
                break
        x_uk = layer.xr_percent + dx
        ok = x_uk < layer.xmax_percent
        out.append({"index": float(i), "x_uk_prime": x_uk, "x_max": layer.xmax_percent, "ok": ok})
    return out


def surface_condensation_risk(assembly: Assembly, climate: Climate) -> Dict[str, float | bool]:
    """Check surface condensation risk per θsi vs θs.

    - θsi via (2.4): θsi = θi − q·Rsi.
    - θs approximated via dew_point(θi, φi) until Tab. 2.1 is integrated.
    Returns dict with keys: theta_si, theta_s, risk (bool)
    """
    U, R_total = u_value(assembly)
    if not math.isfinite(U) or R_total == 0:
        return {"theta_si": climate.theta_i, "theta_s": dew_point(climate.theta_i, climate.phi_i), "risk": False}
    q = U * (climate.theta_i - climate.theta_e)
    theta_si = climate.theta_i - q * assembly.Rsi
    # Prefer tabulated θs if available; fallback to dew point
    theta_s = None
    if _HAS_TABLES and callable(cast(object, theta_s_tabulated)):
        try:
            theta_s = cast(object, theta_s_tabulated)(climate.theta_i, climate.phi_i)
        except Exception:
            theta_s = None
    if theta_s is None:
        theta_s = dew_point(climate.theta_i, climate.phi_i)
    risk = theta_si < theta_s
    # External surface check
    theta_se = temperature_profile(assembly, climate)[-1]
    theta_s_e = None
    if _HAS_TABLES and callable(cast(object, theta_s_tabulated)):
        try:
            theta_s_e = cast(object, theta_s_tabulated)(climate.theta_e, climate.phi_e)
        except Exception:
            theta_s_e = None
    if theta_s_e is None:
        theta_s_e = dew_point(climate.theta_e, climate.phi_e)
    risk_e = theta_se < theta_s_e
    return {"theta_si": theta_si, "theta_s": theta_s, "risk": risk, "theta_se": theta_se, "theta_s_e": theta_s_e, "risk_e": risk_e}


def analyze(assembly: Assembly, climate: Climate, tk_hours: float = 1440.0, tu_hours: float = 1440.0) -> Dict[str, object]:
    """End-to-end condensation analysis with current capabilities.

    Returns a dict suitable for reporting and UI consumption.
    """
    U, R_total = u_value(assembly)
    temps = temperature_profile(assembly, climate)
    z_axis, p_line = vapor_pressure_profile(assembly, climate)
    p_sat = saturation_pressure_profile(temps)
    gp = glaser_profile(assembly, climate)
    z_final = gp["z_final"]
    p_final = gp["p_final"]
    zones = gp["zones"]
    wk = condensate_amount(assembly, climate, tk_hours)
    cond_proxy = wk["Wk_total"]
    drying = drying_capacity(assembly, tu_hours, None)
    # Determine if the drying period can remove accumulated condensate
    drying_ok = drying_check(assembly, climate, tk_hours, tu_hours)
    surface = surface_condensation_risk(assembly, climate)
    p_i, p_e = partial_pressures(climate)
    return {
        "U": U,
        "R_total": R_total,
        "q": U * (climate.theta_i - climate.theta_e) if math.isfinite(U) else float("nan"),
        "theta_profile": temps,
        "thickness_axis": thickness_axis(assembly),
        "vapor_axis": z_axis,
        "p_line": p_line,
        "vapor_axis_final": z_final,
        "p_final": p_final,
        "p_sat": p_sat,
        "zones": zones,
        "condensate_proxy": cond_proxy,
        "Wk_total": wk["Wk_total"],
        "Wk_layers": wk["layers"],
        "drying_capacity": drying["capacity_kg_m2"],
        "drying_ok": drying_ok,
        "moisture_limits": moisture_limits_check(assembly, wk["layers"]),
        "surface": surface,
        "p_i": p_i,
        "p_e": p_e,
    }


def condensation_mass_and_moisture(
    assembly: Assembly, climate: Climate, tk_hours: float
) -> Dict[str, object]:
    """Compatibility wrapper for :func:`condensate_amount`.

    The project historically exposed ``condensation_mass_and_moisture``.  It now
    simply forwards to :func:`condensate_amount` which performs the actual
    Bulgarian-method integration.
    """

    return condensate_amount(assembly, climate, tk_hours)


def drying_capacity(assembly: Assembly, tu_hours: float, drying_climate: Optional[Climate]) -> Dict[str, float | bool]:
    """Compute drying capacity under drying climate over tu.

    If drying_climate is None, use normative default: θi = θe = 18°C, φi = φe = 65%.
    Capacity [kg/m²] ≈ |(p_i - p_e)| / Σz * tu.
    """
    if drying_climate is None:
        drying_climate = Climate(theta_i=18.0, phi_i=65.0, theta_e=18.0, phi_e=65.0)
    p_i, p_e = partial_pressures(drying_climate)
    # Total vapor resistance Σz (m²·Pa·h/kg)
    s_total = z_profile(assembly)[-1] if assembly.layers else 0.0
    if s_total <= 0:
        return {"capacity_kg_m2": 0.0, "ok": False}
    g = abs(p_i - p_e) / s_total  # kg/(m² h)
    capacity = g * tu_hours  # kg/m²
    # Compare with Wk from condensation period
    # Note: caller should compute Wk_total and compare; here we return capacity only.
    return {"capacity_kg_m2": capacity, "ok": capacity > 0.0}

