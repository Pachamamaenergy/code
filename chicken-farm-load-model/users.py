# users.py

"""
This file defines the core structure of the chicken farm energy model.

It includes:
- Farm configuration
- Production cycle assumptions
- Energy assumptions per 40-day cycle
- A decreasing heating profile across the broiler growth period
- Creation of the RAMP UseCase and User objects

This file is intended to be imported by other modules, such as loads.py.
"""

from ramp import UseCase, User

# =========================
# FARM CONFIGURATION
# =========================

FARM_NAME = "ChickenFarm_Bolivia"
NUM_CHICKENS = 20000

# Production cycle
CYCLE_DAYS = 40
DATE_START = "2025-01-01"
DATE_END = "2025-12-31"

# Continuous production: no downtime between cycles
CYCLES_PER_YEAR = 365 / CYCLE_DAYS

# =========================
# ENERGY DATA
# =========================

"""
Energy input per 40-day production cycle based on farm-reported fuel consumption.

The farm reported the following fuel use per production cycle:
- 60 liters of diesel
- 100 LPG cylinders of 11 kg each

These reported quantities are converted into energy units (kWh) and used
as fixed model inputs. The gas component represents brooding and heating
demand, while diesel represents water pumping and hygiene-related activities.
"""

GAS_KWH_PER_CYCLE = 14000.0
DIESEL_KWH_PER_CYCLE = 600.0

# Diesel breakdown into sub-loads
DIESEL_WATER_SHARE = 0.60
DIESEL_HYGIENE_DAILY_SHARE = 0.25
DIESEL_HYGIENE_EVENT_SHARE = 0.15

DIESEL_WATER_KWH_PER_CYCLE = DIESEL_KWH_PER_CYCLE * DIESEL_WATER_SHARE
DIESEL_HYGIENE_DAILY_KWH_PER_CYCLE = DIESEL_KWH_PER_CYCLE * DIESEL_HYGIENE_DAILY_SHARE
DIESEL_HYGIENE_EVENT_KWH_PER_CYCLE = DIESEL_KWH_PER_CYCLE * DIESEL_HYGIENE_EVENT_SHARE

# =========================
# HEATING PROFILE
# =========================

"""
Broiler chicks require high temperatures at the beginning of the cycle,
and lower temperatures as they grow.

Instead of assuming gas is used only during the first 20 days,
this model assumes gas is used throughout the 40-day cycle,
but with decreasing intensity.

The tuples follow the format:
(start_day, end_day, relative_weight)

These weights do not represent absolute energy values directly.
They define the relative distribution of gas use over the cycle.
"""

HEATING_PROFILE = [
    (1, 3, 1.00),   # Highest heating demand
    (4, 7, 0.90),
    (8, 14, 0.75),
    (15, 21, 0.55),
    (22, 28, 0.35),
    (29, 35, 0.18),
    (36, 40, 0.08), # Low but not zero
]

def calculate_weighted_gas_allocation(total_gas_kwh, heating_profile):
    """
    Converts the relative heating profile into absolute gas energy values.

    Parameters
    ----------
    total_gas_kwh : float
        Total gas energy used per 40-day cycle.
    heating_profile : list of tuples
        Each tuple is (start_day, end_day, relative_weight).

    Returns
    -------
    list of tuples
        Each tuple is:
        (start_day, end_day, relative_weight, allocated_kwh, kwh_per_day)
    """
    weighted_days = []
    total_weighted_sum = 0.0

    for start_day, end_day, weight in heating_profile:
        num_days = end_day - start_day + 1
        weighted_value = num_days * weight
        weighted_days.append((start_day, end_day, weight, num_days, weighted_value))
        total_weighted_sum += weighted_value

    allocation = []
    for start_day, end_day, weight, num_days, weighted_value in weighted_days:
        allocated_kwh = total_gas_kwh * (weighted_value / total_weighted_sum)
        kwh_per_day = allocated_kwh / num_days
        allocation.append((start_day, end_day, weight, allocated_kwh, kwh_per_day))

    return allocation

GAS_ALLOCATION = calculate_weighted_gas_allocation(
    total_gas_kwh=GAS_KWH_PER_CYCLE,
    heating_profile=HEATING_PROFILE,
)

# =========================
# DIESEL QUALITY FACTOR
# =========================

"""
This optional factor can later be used if the effective energy content
of diesel is lower than expected due to fuel quality issues.

For now, keep it at 1.00 unless you intentionally want to apply
a correction.
"""

DIESEL_QUALITY_FACTOR = 1.00

# =========================
# CREATE RAMP MODEL
# =========================

"""
UseCase defines the simulation period.
peak_enlarge adds stochastic variation to demand peaks.
"""

use_case = UseCase(
    date_start=DATE_START,
    date_end=DATE_END,
    peak_enlarge=0.15,
)

"""
User represents one farm.
"""

farm = User(
    user_name=FARM_NAME,
    num_users=1,
)

use_case.add_user(farm)

# =========================
# SHARED CONFIGURATION
# =========================

"""
This dictionary centralizes all model parameters so they can be reused
in other files, especially loads.py.
"""

farm_config = {
    "farm_name": FARM_NAME,
    "num_chickens": NUM_CHICKENS,
    "cycle_days": CYCLE_DAYS,
    "cycles_per_year": CYCLES_PER_YEAR,
    "gas_kwh_per_cycle": GAS_KWH_PER_CYCLE,
    "diesel_kwh_per_cycle": DIESEL_KWH_PER_CYCLE,
    "diesel_water_kwh_per_cycle": DIESEL_WATER_KWH_PER_CYCLE,
    "diesel_hygiene_daily_kwh_per_cycle": DIESEL_HYGIENE_DAILY_KWH_PER_CYCLE,
    "diesel_hygiene_event_kwh_per_cycle": DIESEL_HYGIENE_EVENT_KWH_PER_CYCLE,
    "heating_profile": HEATING_PROFILE,
    "gas_allocation": GAS_ALLOCATION,
    "diesel_quality_factor": DIESEL_QUALITY_FACTOR,
}