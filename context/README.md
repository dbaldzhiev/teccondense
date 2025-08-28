# Material data

`materials.csv` lists thermal and moisture properties for common building materials.
The values were transcribed from Bulgarian building norms (tables for thermal
and moisture characteristics). Each entry uses the following columns:

- `name` – material description
- `lambda` – thermal conductivity in W/m·K
- `mu` – water vapour diffusion resistance factor (dimensionless)
- `rho` – density in kg/m³
- `xr_percent` – reference moisture content by mass (%)
- `xmax_percent` – maximum moisture content by mass (%)

To extend the dataset, add new rows to `materials.csv` using decimal points for
numbers. The file is loaded by `condensation.materials.load_materials`, which
will raise an error if any row is malformed.
