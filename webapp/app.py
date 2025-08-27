
from flask import Flask, render_template, request, jsonify, redirect, url_for
import sys
from pathlib import Path

# Ensure repository root is on sys.path for package import
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from condensation.core import analyze
from condensation.dataclasses import Layer, Assembly, Climate
try:
    from condensation.materials import load_materials
except Exception:  # fallback if module missing
    def load_materials():
        return []

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['GET', 'POST'])
def analyze_api():
    # Simple help on GET to avoid 405 if user navigates directly
    if request.method == 'GET':
        return jsonify({
            'ok': True,
            'usage': 'POST JSON to this endpoint with {layers, Rsi, Rse, climate}',
            'example': {
                'layers': [{'name':'Insulation','d':0.1,'lambda_':0.04,'mu':20,'rho':800,'xr_percent':5,'xmax_percent':20}],
                'Rsi': 0.13,
                'Rse': 0.04,
                'climate': {'theta_i':20,'phi_i':65,'theta_e':5,'phi_e':90}
            }
        })
    try:
        data = request.get_json(force=True)
        layers_in = data.get('layers', [])
        if not isinstance(layers_in, list) or not layers_in:
            return jsonify({'ok': False, 'error': 'No layers provided'}), 400
        layers: list[Layer] = []
        for idx, L in enumerate(layers_in):
            try:
                layers.append(Layer(
                    name=str(L.get('name', f'Layer {idx+1}')),
                    d=float(L['d']),
                    lambda_=float(L['lambda_']),
                    mu=float(L['mu']),
                    rho=float(L['rho']),
                    xr_percent=float(L.get('xr_percent', 5.0)),
                    xmax_percent=float(L.get('xmax_percent', 20.0)),
                ))
            except Exception as e:
                return jsonify({'ok': False, 'error': f'Invalid layer at index {idx}: {e}'}), 400
        Rsi = float(data.get('Rsi', 0.13))
        Rse = float(data.get('Rse', 0.04))
        assembly = Assembly(layers=layers, Rsi=Rsi, Rse=Rse)
        cl = data.get('climate', {})
        climate = Climate(
            theta_i=float(cl.get('theta_i', 20)),
            phi_i=float(cl.get('phi_i', 65)),
            theta_e=float(cl.get('theta_e', 5)),
            phi_e=float(cl.get('phi_e', 90)),
        )
        tk = float(data.get('tk_hours', 1440))
        tu = float(data.get('tu_hours', 1440))
        result = analyze(assembly, climate, tk_hours=tk, tu_hours=tu)
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/materials', methods=['GET'])
def materials_api():
    mats = load_materials()
    q = request.args.get('q')
    if q:
        ql = q.lower()
        mats = [m for m in mats if ql in m.get('name','').lower()]
    return jsonify({'ok': True, 'materials': mats})


@app.errorhandler(405)
def handle_405(e):
    # If someone POSTs to '/', redirect to the main page
    if request.path == '/':
        return redirect(url_for('index'), code=303)
    return jsonify({'ok': False, 'error': 'Method Not Allowed', 'hint': 'GET / for UI, POST JSON to /analyze'}), 405

if __name__ == '__main__':
    app.run(debug=True)
