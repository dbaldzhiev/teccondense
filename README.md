# TecCondense — Кондензационен пад (BG норми)

Инструмент (Python библиотека + уеб UI) за проверка на риск от повърхностна и вътрешна кондензация в многослойни ограждащи конструкции по българската методика („Глазер“), със справки по табл. 2.1 и 2.2 и отчет с диаграми.

- Ядро: `condensation/` — изчисления, интерполации и отчет.
- Уеб приложение: `webapp/` — лек Flask UI и JSON API.
- Нормативни данни/материали: `context/` — таблици и библиотека от материали.

Кодът следва Приложение № 6 (чл. 25, ал. 5): температурно поле, парциални/максимални налягания, зона на кондензация, количество конденз, навлажняване и проверка на съхнене. Включени са и проверки за повърхностна кондензация (θsi ≥ θs).

## Основни възможности
- U‑стойност, топлинен поток `q`, профил на температурата по интерфейси.
- Линеен профил на парциалното налягане `p(z)` и `p_sat(T)`; откриване на зони на конденз.
- Интегрално количество конденз `Wk` за период на навлажняване `tk` и разпределение по слоеве (Δx_dif).
- Проверка x′uk = xr′ + Δx_dif < xmax по слой и проверка за съхнене през `tu` (нормативен режим по подразбиране).
- Проверка за повърхностна кондензация (θsi срещу θs по табл. 2.1; при липса на таблица — обратна Magnus аппроксимация).
- HTML отчет с диаграми (температура, p/p_sat, визуализация на зоните), работещ и в среда без matplotlib (degrade‑gracefully).

## Изисквания и инсталация
- Python 3.10+ (заради анотации от вида `float | bool`).
- Зависимости: Flask и (по избор) Matplotlib за графики.

Стъпки:
```
python -m venv .venv
. .venv/Scripts/activate    # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# (по избор за тестове)
pip install pytest
```

## Стартиране (уеб UI)
```
python webapp/app.py
# или
flask --app webapp.app run --reload
```
Отворете http://127.0.0.1:5000/ и въведете слоевете (от вътре навън), климат и Rsi/Rse. В падащото меню има пресети за външната проектна температура (по климатични зони): 5°C / −5°C / −10°C. Материалите се зареждат от `context/materials.csv`.

## JSON API
- `GET /` — HTML UI.
- `POST /analyze` — изчисления по JSON.
- `GET /materials?q=` — списък материали (филтър по име).

Пример заявка към `/analyze`:
```
curl -X POST http://127.0.0.1:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{
        "layers": [
          {"name":"Insulation","d":0.10,"lambda_":0.04,"mu":20,"rho":800,"xr_percent":5,"xmax_percent":20}
        ],
        "Rsi": 0.13,
        "Rse": 0.04,
        "climate": {"theta_i":20, "phi_i":65, "theta_e":5, "phi_e":90},
        "tk_hours": 1440,
        "tu_hours": 1440
      }'
```

### Входна схема (JSON)
- `layers[]` (от вътре навън): за всеки слой
  - `name`, `d` [m], `lambda_` [W/mK], `mu` [-], `rho` [kg/m3], `xr_percent` [%], `xmax_percent` [%]
- `Rsi`, `Rse` [м2K/W] — по БДС EN ISO 6946 (конфигурируеми).
- `climate`: `{ theta_i[°C], phi_i[%], theta_e[°C], phi_e[%] }`
- Опции: `tk_hours` (по подразбиране 1440 h), `tu_hours` (1440 h), `verbose` (True/False)

Забележки:
- Период на навлажняване `tk`: 1440 h; период на съхнене `tu`: 1440 h (за сгради без климатизация), освен ако проектът задава други условия.
- Режим за съхнене по подразбиране: θi = θe = 18°C, φi = φe = 65%.
- За периода на кондензация: φe = 90%, θe се избира според климатичната зона (5/−5/−10°C). Подайте стойностите в `climate`.

### Изходни полета (основни)
- Флагове: `surface.risk`, `internal_condensation` (true при намерени зони), `drying_ok`.
- Числени: `U`, `R_total`, `q`, `theta_profile` (по интерфейси), `thickness_axis` (x), `vapor_axis` (Σμd/δ_air), `p_line`, `p_sat`, `vapor_axis_final` и `p_final` (ограничен профил по Глазер), `zones[]` (интервали по z), `Wk_total`, `Wk_layers[]` (по слоеве), `moisture_limits[]` (x′uk и статус), `p_i`, `p_e`.
- Отчет: `report_html` (компактен HTML за вграждане).

## Python API (ядро)
Минимален пример:
```python
from condensation.dataclasses import Layer, Assembly, Climate
from condensation.core import analyze

layers = [
    Layer("Insulation", d=0.10, lambda_=0.040, mu=20, rho=800, xr_percent=5, xmax_percent=20)
]
asm = Assembly(layers=layers, Rsi=0.13, Rse=0.04)
cl = Climate(theta_i=20, phi_i=65, theta_e=5, phi_e=90)
res = analyze(asm, cl, tk_hours=1440, tu_hours=1440, verbose=True)
print(res["U"], res["Wk_total"], res["drying_ok"])  # и др.
```
Полезни функции: `u_value`, `temperature_profile`, `z_profile`, `p_max`, `dew_point`, `condensation_zones`, `condensate_amount`, `drying_check` и `report.report(results)`.

## Данни и интерполации
- Таблица 2.1 (θs) и Таблица 2.2 (p_max) се четат от `context/t2-1.csv` и `context/t2-2.csv` (или от съответните XLSX, ако са налични). При липса на таблици се използват аппроксимации Magnus за p_sat и обратна Magnus за θs, с което се отбелязва намалена точност.
- Библиотека от материали: `context/materials.csv` (зареждана от `condensation.materials.load_materials`). Редовете трябва да съдържат: `name, lambda, mu, rho, xr_percent, xmax_percent`.

## Ограничения и проверки (норма)
- Не се прилага за подове/стени към земя (изискване от методиката).
- Материали без стойности за `mu`, `xr_percent`, `xmax_percent` са недопустими в зони с очакван конденз.
- При φ/θ извън таблични граници — интерполация/екстраполация с предупреждение (в отчета).
- Изходните единици: m, W/mK, kg/m³, Pa.

## Структура на репото
```
condensation/   # ядро: изчисления, таблици, отчет
webapp/         # Flask уеб приложение (UI + JSON API)
context/        # таблични данни (p_max, θs) и материали
tests/          # pytest тестове за ядро/отчет/материали
requirements.txt
```

## Тестове
```
pytest -q
```

## Бележки
- Изборът на θe по климатична зона не е „вграден“ автоматично — подайте го чрез UI/JSON според проектната външна температура (> −8.5°C → 5°C; между −8.5 и −14.5°C → −5°C; < −14.5°C → −10°C).
- Отчетите с графики изискват `matplotlib`; при липса, приложението продължава без изображения.
- Повърхностните съпротивления `Rsi/Rse` настройвайте според експозицията (БДС EN ISO 6946).

---
Short English summary: Python library + Flask UI for Glaser‑method condensation checks per Bulgarian norms (Annex 6). Provides U, temperature and vapor profiles, condensation zones, condensate mass Wk, moisture checks, drying verification, surface risk, and an HTML report. Data tables from `context/` with Magnus fallbacks.
