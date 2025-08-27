def report(results: dict) -> str:
    """Generate a minimal HTML report from analysis results.

    This is a starter implementation; charts and normative tables are TODO.
    """
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
    return "\n".join([
        "<h2>Condensation Risk Report</h2>",
        "<ul>",
        *lis,
        "</ul>",
    ])
