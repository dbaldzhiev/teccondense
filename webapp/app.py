
from flask import Flask, render_template, request
import sys
sys.path.append('../condensation')
from condensation.core import u_value, temperature_profile, z_profile, partial_pressures
from condensation.dataclasses import Layer, Assembly, Climate

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        # Basic input parsing (expand as needed)
        layers = [
            Layer(
                name=request.form.get('layer_name_1', 'Layer 1'),
                d=float(request.form.get('layer_d_1', 0.1)),
                lambda_=float(request.form.get('layer_lambda_1', 0.04)),
                mu=float(request.form.get('layer_mu_1', 20)),
                rho=float(request.form.get('layer_rho_1', 800)),
                xr_percent=float(request.form.get('layer_xr_1', 5)),
                xmax_percent=float(request.form.get('layer_xmax_1', 20)),
            )
        ]
        assembly = Assembly(layers=layers, Rsi=0.13, Rse=0.04)
        climate = Climate(
            theta_i=float(request.form.get('theta_i', 20)),
            phi_i=float(request.form.get('phi_i', 65)),
            theta_e=float(request.form.get('theta_e', 5)),
            phi_e=float(request.form.get('phi_e', 90)),
        )
        U, R_total = u_value(assembly)
        temp_profile = temperature_profile(assembly, climate)
        z_prof = z_profile(assembly)
        p_i, p_e = partial_pressures(climate)
        result = {
            'U': U,
            'R_total': R_total,
            'temp_profile': temp_profile,
            'z_profile': z_prof,
            'p_i': p_i,
            'p_e': p_e,
        }
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
