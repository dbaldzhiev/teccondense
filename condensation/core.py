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
    """Return temperatures at surfaces/interfaces: [theta_si, after each layer..., theta_se].

    - Includes surface resistances Rsi and Rse (2.4, 2.6).
    - Length = number of layers + 1 (interfaces) + 1 (external surface) => n_layers + 1.
    """
    U, R_total = u_value(assembly)
    if not math.isfinite(U) or R_total == 0:
        return [climate.theta_i] * (len(assembly.layers) + 1)

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

    # The last appended value corresponds to external surface after all layers (theta_se)
    # Adjust external surface using Rse to get exactly theta_se:
    # Recompute final external surface to ensure numerical consistency
    theta_se = climate.theta_e + q * assembly.Rse
    temps[-1] = theta_se
    return temps


def z_profile(assembly: Assembly) -> List[float]:
    """Return vapor diffusion thickness axis s = Σ(μ·d) at surfaces/interfaces.

    - Starts at 0 at internal surface.
    - Adds μ·d for each layer to the next interface.
    - Returns [0, after L1, after L2, ..., after Ln] length = n_layers + 1.
    """
    s = [0.0]
    accum = 0.0
    for layer in assembly.layers:
        accum += layer.mu * layer.d
        s.append(accum)
    return s


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
    """Linear p(s) profile along s = Σ(μ·d) from p_i to p_e per (2.3).

    Returns (s_axis, p_line) where lengths equal number of interfaces (n_layers + 1).
    Units: s in m²·hPa/kg, p in Pa (internally converted to hPa for slope, then back to Pa).
    """
    s_axis = z_profile(assembly)
    if not s_axis:
        return [], []
    p_i_pa, p_e_pa = partial_pressures(climate)
    # Work in hPa for consistency with classic z units; convert back to Pa at the end.
    p_i = p_i_pa / 100.0
    p_e = p_e_pa / 100.0
    s_total = s_axis[-1]
    if s_total == 0:
        return s_axis, [p_i_pa for _ in s_axis]
    p_line_hPa = [p_i + (p_e - p_i) * (s / s_total) for s in s_axis]
    p_line_pa = [p * 100.0 for p in p_line_hPa]
    return s_axis, p_line_pa


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


def condensate_amount(p_line: List[float], p_sat_line: List[float], z_axis: List[float]) -> float:
    """Proxy integral of excess vapor pressure over axis (Pa·axis_unit).

    NOTE: Placeholder. Normative Glaser mass Wk [kg/m²] requires layer-wise
    flux reconstruction and tk; this function intentionally returns a proxy
    magnitude useful for relative comparison, not a mass.
    """
    total = 0.0
    n = min(len(p_line), len(p_sat_line), len(z_axis))
    for i in range(1, n):
        dz = abs(z_axis[i] - z_axis[i - 1])
        excess0 = max(0.0, p_line[i - 1] - p_sat_line[i - 1])
        excess1 = max(0.0, p_line[i] - p_sat_line[i])
        area = 0.5 * (excess0 + excess1) * dz
        total += area
    return total


def drying_check(*args, **kwargs) -> bool:
    """Placeholder: drying feasibility during tu period.

    Returns True if drying likely, False if persistent moisture expected.
    TODO: Implement using reverse gradients and tk/tu conditions.
    """
    return True


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
    return {"theta_si": theta_si, "theta_s": theta_s, "risk": risk}


def analyze(assembly: Assembly, climate: Climate) -> Dict[str, object]:
    """End-to-end condensation analysis with current capabilities.

    Returns a dict suitable for reporting and UI consumption.
    """
    U, R_total = u_value(assembly)
    temps = temperature_profile(assembly, climate)
    s_axis, p_line = vapor_pressure_profile(assembly, climate)
    p_sat = saturation_pressure_profile(temps)
    zones = condensation_zones(p_line, p_sat, s_axis)
    cond_proxy = condensate_amount(p_line, p_sat, s_axis)
    # Normative periods (defaults): tk and tu in hours
    tk = 1440.0
    tu = 1440.0
    wk = condensation_mass_and_moisture(assembly, climate, tk)
    drying = drying_capacity(assembly, tu, None)
    drying_ok = None
    try:
        drying_ok = (drying["capacity_kg_m2"] >= wk["Wk_total"])  # type: ignore[index]
    except Exception:
        drying_ok = None
    surface = surface_condensation_risk(assembly, climate)
    p_i, p_e = partial_pressures(climate)
    return {
        "U": U,
        "R_total": R_total,
        "q": U * (climate.theta_i - climate.theta_e) if math.isfinite(U) else float("nan"),
        "theta_profile": temps,
        "thickness_axis": thickness_axis(assembly),
        "vapor_axis": s_axis,
        "p_line": p_line,
        "p_sat": p_sat,
        "zones": zones,
        "condensate_proxy": cond_proxy,
        "Wk_total": wk["Wk_total"],
        "Wk_layers": wk["layers"],
        "drying_capacity": drying["capacity_kg_m2"],
        "drying_ok": drying_ok,
        "surface": surface,
        "p_i": p_i,
        "p_e": p_e,
    }


def condensation_mass_and_moisture(assembly: Assembly, climate: Climate, tk_hours: float) -> Dict[str, object]:
    """Compute Wk [kg/m²] and Δx_dif per layer according to Glaser-like layer summation.

    Method: for each layer segment in s-axis (Σμd), compare pressure drops of linear p(s)
    and p_sat(T) across that layer. Excess drop implies condensation rate:
      g_excess = max(0, Δp_line_hPa - Δp_sat_hPa) / z_layer
      Wk_layer = g_excess * tk_hours
      Δx_dif_layer[%] = Wk_layer / (d_layer * ρ_layer) * 100
    """
    s_axis, p_line_pa = vapor_pressure_profile(assembly, climate)
    temps = temperature_profile(assembly, climate)
    p_sat_pa = saturation_pressure_profile(temps)
    # Convert to hPa to match z units
    p_line_hPa = [p / 100.0 for p in p_line_pa]
    p_sat_hPa = [p / 100.0 for p in p_sat_pa]

    layers_out: List[Dict[str, float]] = []
    Wk_total = 0.0
    # Each segment i corresponds to layer i
    nseg = min(len(assembly.layers), len(s_axis) - 1, len(p_line_hPa) - 1, len(p_sat_hPa) - 1)
    for i in range(nseg):
        z_layer = s_axis[i + 1] - s_axis[i]
        if z_layer <= 0:
            layers_out.append({
                "index": float(i),
                "Wk_layer": 0.0,
                "delta_x_percent": 0.0,
            })
            continue
        dp_line = max(0.0, p_line_hPa[i] - p_line_hPa[i + 1])
        dp_sat = max(0.0, p_sat_hPa[i] - p_sat_hPa[i + 1])
        g_excess = max(0.0, dp_line - dp_sat) / z_layer  # kg/(m² h)
        Wk_layer = g_excess * tk_hours  # kg/m²
        layer = assembly.layers[i]
        dz = max(layer.d, 1e-9)
        rho = max(layer.rho, 1e-9)
        delta_x_percent = Wk_layer / (dz * rho) * 100.0
        layers_out.append({
            "index": float(i),
            "Wk_layer": Wk_layer,
            "delta_x_percent": delta_x_percent,
        })
        Wk_total += Wk_layer

    return {"Wk_total": Wk_total, "layers": layers_out}


def drying_capacity(assembly: Assembly, tu_hours: float, drying_climate: Optional[Climate]) -> Dict[str, float | bool]:
    """Compute drying capacity under drying climate over tu.

    If drying_climate is None, use normative default: θi = θe = 18°C, φi = φe = 65%.
    Capacity [kg/m²] ≈ |(p_i - p_e)| / Σz * tu.
    """
    if drying_climate is None:
        drying_climate = Climate(theta_i=18.0, phi_i=65.0, theta_e=18.0, phi_e=65.0)
    p_i, p_e = partial_pressures(drying_climate)
    # Use hPa for consistency with z units
    p_i_hPa = p_i / 100.0
    p_e_hPa = p_e / 100.0
    # Total vapor resistance Σz
    s_total = z_profile(assembly)[-1] if assembly.layers else 0.0
    if s_total <= 0:
        return {"capacity_kg_m2": 0.0, "ok": False}
    g = abs(p_i_hPa - p_e_hPa) / s_total  # kg/(m² h)
    capacity = g * tu_hours  # kg/m²
    # Compare with Wk from condensation period
    # Note: caller should compute Wk_total and compare; here we return capacity only.
    return {"capacity_kg_m2": capacity, "ok": capacity > 0.0}

