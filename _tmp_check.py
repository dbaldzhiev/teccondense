import json
from condensation.dataclasses import Layer, Assembly, Climate
from condensation.core import analyze
layers=[Layer('Insul',0.1,0.04,20,30,5,20)]
A=Assembly(layers,0.13,0.04)
C=Climate(20,65,5,90)
res = analyze(A,C)
print('OK', round(res['U'],4), res['surface']['risk'], bool(res.get('internal_condensation')))
