"""Generate HTML reports with charts and normative table snippets."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Iterable, List, Tuple

try:  # pragma: no cover - matplotlib is optional at runtime
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - gracefully degrade if missing
    plt = None  # type: ignore

try:  # pragma: no cover - tables are optional
    from .tables import p_max_tabulated, theta_s_tabulated
except Exception:  # pragma: no cover
    p_max_tabulated = None  # type: ignore
    theta_s_tabulated = None  # type: ignore


def _encode_fig(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _plot_temperature(xs: Iterable[float], ys: Iterable[float]) -> str:
    if plt is None:
        return ""
    fig, ax = plt.subplots()
    ax.plot(list(xs), list(ys))
    ax.set_xlabel("Σd [m]")
    ax.set_ylabel("θ [°C]")
    ax.set_title("Temperature profile")
    return _encode_fig(fig)


def _plot_vapor(xs: Iterable[float], p: Iterable[float], ps: Iterable[float]) -> str:
    if plt is None:
        return ""
    fig, ax = plt.subplots()
    ax.plot(list(xs), list(p), label="p")
    ax.plot(list(xs), list(ps), label="p_sat")
    ax.set_xlabel("Σ(μ·d) [m²·Pa·h/kg]")
    ax.set_ylabel("p [Pa]")
    ax.set_title("Vapor pressure profile")
    ax.legend()
    return _encode_fig(fig)


def _tab21(theta_i: float | None, phi_i: float | None) -> str:
    if theta_i is None or phi_i is None or theta_s_tabulated is None:
        return "<p>Tab. 2.1 unavailable.</p>"
    try:
        theta_s = theta_s_tabulated(theta_i, phi_i)  # type: ignore[misc]
    except Exception:
        theta_s = None
    if theta_s is None:
        return "<p>Tab. 2.1 unavailable.</p>"
    return (
        "<table id='tab21'>"
        "<tr><th>θi (°C)</th><th>φi (%)</th><th>θs (°C)</th></tr>"
        f"<tr><td>{theta_i:.1f}</td><td>{phi_i:.0f}</td><td>{theta_s:.1f}</td></tr>"
        "</table>"
    )


def _tab22(temps: Iterable[float]) -> str:
    if p_max_tabulated is None:
        return "<p>Tab. 2.2 unavailable.</p>"
    rows: List[Tuple[float, float]] = []
    for T in list(temps)[:5]:
        try:
            p = p_max_tabulated(T)  # type: ignore[misc]
        except Exception:
            p = None
        if p is not None:
            rows.append((T, float(p)))
    if not rows:
        return "<p>Tab. 2.2 unavailable.</p>"
    trs = "".join(
        f"<tr><td>{T:.1f}</td><td>{p:.0f}</td></tr>" for T, p in rows
    )
    return (
        "<table id='tab22'>"
        "<tr><th>T (°C)</th><th>p_sat (Pa)</th></tr>"
        f"{trs}</table>"
    )


def report(results: dict) -> str:
    """Generate an HTML report from analysis results with charts and table data."""

    surface = results.get("surface", {})
    zones = results.get("zones", [])
    lis = [
        f"<li>U-value: {results.get('U', float('nan')):.4f} W/m²K</li>",
        f"<li>ΣR: {results.get('R_total', float('nan')):.4f} m²K/W</li>",
        f"<li>q: {results.get('q', float('nan')):.3f} W/m²</li>",
        f"<li>Surface risk: {'Yes' if surface.get('risk') else 'No'} (θsi={surface.get('theta_si', float('nan')):.2f}°C vs θs={surface.get('theta_s', float('nan')):.2f}°C)</li>",
        f"<li>θ profile: {results.get('theta_profile')}</li>",
        f"<li>Σd: {results.get('thickness_axis')}</li>",
        f"<li>Σ(μ·d): {results.get('vapor_axis')}</li>",
        f"<li>p_i: {results.get('p_i', float('nan')):.0f} Pa, p_e: {results.get('p_e', float('nan')):.0f} Pa</li>",
        f"<li>Condensation zones: {zones}</li>",
        f"<li>Condensate proxy: {results.get('condensate_proxy', 0.0):.1f}</li>",
    ]

    temp_chart = _plot_temperature(
        results.get("thickness_axis", []), results.get("theta_profile", [])
    )
    vapor_chart = _plot_vapor(
        results.get("vapor_axis", []),
        results.get("p_line", []),
        results.get("p_sat", []),
    )

    tab21_html = _tab21(results.get("theta_i"), results.get("phi_i"))
    tab22_html = _tab22(results.get("theta_profile", []))

    parts = [
        "<h2>Condensation Risk Report</h2>",
        "<ul>",
        *lis,
        "</ul>",
        "<h3>Charts</h3>",
        f"<img src='data:image/png;base64,{temp_chart}' alt='Temperature chart' />" if temp_chart else "",
        f"<img src='data:image/png;base64,{vapor_chart}' alt='Vapor chart' />" if vapor_chart else "",
        "<h3>Tab. 2.1 excerpt</h3>",
        tab21_html,
        "<h3>Tab. 2.2 excerpt</h3>",
        tab22_html,
    ]
    return "\n".join([p for p in parts if p])
