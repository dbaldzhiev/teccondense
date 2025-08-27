from dataclasses import dataclass
from typing import List

@dataclass
class Layer:
    name: str
    d: float  # thickness [m]
    lambda_: float  # thermal conductivity [W/mK]
    mu: float  # vapor diffusion resistance [-]
    rho: float  # density [kg/m3]
    xr_percent: float  # reference moisture [%]
    xmax_percent: float  # max moisture [%]

@dataclass
class Assembly:
    layers: List[Layer]
    Rsi: float  # internal surface resistance [m2K/W]
    Rse: float  # external surface resistance [m2K/W]

@dataclass
class Climate:
    theta_i: float  # indoor temperature [°C]
    phi_i: float    # indoor relative humidity [%]
    theta_e: float  # outdoor temperature [°C]
    phi_e: float    # outdoor relative humidity [%]
