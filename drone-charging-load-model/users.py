# users.py

"""
This file defines the core structure of the drone battery charging model.

It includes:
- Site configuration
- Technical assumptions from the specifications
- One single charging scenario based on the DJI reference window
- Monthly night-temperature data for Cochabamba
- Creation of the RAMP UseCase and User objects

This file is intended to be imported by other modules, such as
an analysis script that builds load profiles and plots results.
"""

from ramp import UseCase, User

# =========================
# SITE CONFIGURATION
# =========================

SITE_NAME = "DroneOperation_Cochabamba"

DATE_START = "2025-01-01"
DATE_END = "2025-12-31"

NUM_DRONES = 1
NUM_BATTERIES = 3

# =========================
# OPERATIONAL ASSUMPTIONS
# =========================

# User assumption:
# one night shift completes 40 charging events
CHARGES_PER_NIGHT = 40

# Optional operational timing assumptions
FLIGHT_TIME_MIN = 12
COOLING_TIME_MIN = 10
SWAP_TIME_MIN = 1

# =========================
# BATTERY DATA
# =========================

# DJI DB2160 battery
BATTERY_NOMINAL_VOLTAGE_V = 52.0
BATTERY_CAPACITY_AH = 41.0

# Nominal battery energy
BATTERY_NOMINAL_ENERGY_KWH = (
    BATTERY_NOMINAL_VOLTAGE_V * BATTERY_CAPACITY_AH
) / 1000.0

# =========================
# CHARGING SCENARIO
# =========================

# Specification-based reference charging window
START_SOC = 0.30
END_SOC = 0.95

# Charge duration from specification
CHARGE_TIME_MIN = 9

# Practical extra losses in charging system
# Keep this modest for now
SYSTEM_LOSS_FRACTION = 0.05

# =========================
# GENERATOR DATA
# =========================

GENERATOR_NAME = "D14000iE"
GENERATOR_MAX_CHARGE_OUTPUT_KW = 11.5
GENERATOR_FUEL_L_PER_KWH = 0.50
GENERATOR_TANK_L = 30.0

# =========================
# WEATHER DATA
# =========================

"""
Monthly average night temperature for Cochabamba.

This is included as a contextual weather input and can later be used
to adjust charging behavior, cooling time, or operating conditions.
"""

MONTHLY_NIGHT_TEMPERATURE_C = {
    1: 14.0,
    2: 13.0,
    3: 13.0,
    4: 11.0,
    5: 7.0,
    6: 5.0,
    7: 5.0,
    8: 7.0,
    9: 10.0,
    10: 12.0,
    11: 14.0,
    12: 14.0,
}

TEMPERATURE_REFERENCE_C = 10.0
TEMPERATURE_ENERGY_SENSITIVITY_PER_DEG_C = 0.005

# =========================
# HELPER FUNCTIONS
# =========================

def get_night_temperature_c(month):
    """Return monthly average night temperature for the given month."""
    return MONTHLY_NIGHT_TEMPERATURE_C[month]


def get_temperature_factor(month):
    """
    Return a mild correction factor for electrical energy demand.

    Warmer nights are assumed to slightly increase practical energy demand.
    Cooler nights are assumed to slightly improve conditions.
    """
    temp_c = get_night_temperature_c(month)
    delta_c = temp_c - TEMPERATURE_REFERENCE_C
    factor = 1.0 + delta_c * TEMPERATURE_ENERGY_SENSITIVITY_PER_DEG_C
    return max(0.90, min(1.10, factor))


def get_battery_energy_per_charge_kwh():
    """
    Battery-side energy added during one charge
    for the specification-based SOC window.
    """
    soc_window = END_SOC - START_SOC
    return BATTERY_NOMINAL_ENERGY_KWH * soc_window


def get_generator_energy_per_charge_kwh():
    """
    Generator-side electrical energy required for one charge,
    including practical system losses.
    """
    return get_battery_energy_per_charge_kwh() * (1.0 + SYSTEM_LOSS_FRACTION)


def get_average_charge_power_kw():
    """
    Average charging power over the charge window.
    """
    hours = CHARGE_TIME_MIN / 60.0
    if hours <= 0:
        raise ValueError("CHARGE_TIME_MIN must be greater than zero.")
    return get_generator_energy_per_charge_kwh() / hours


def get_total_night_energy_kwh(month=None):
    """
    Total generator-side electrical energy for one night.

    If month is provided, a mild temperature factor is applied.
    """
    energy = get_generator_energy_per_charge_kwh() * CHARGES_PER_NIGHT
    if month is not None:
        energy *= get_temperature_factor(month)
    return energy


def get_total_night_fuel_liters(month=None):
    """
    Total fuel use for one night.
    """
    return get_total_night_energy_kwh(month) * GENERATOR_FUEL_L_PER_KWH


def validate_model():
    """
    Return warning messages if assumptions conflict with the specifications.
    """
    warnings = []

    avg_power_kw = get_average_charge_power_kw()
    if avg_power_kw > GENERATOR_MAX_CHARGE_OUTPUT_KW:
        warnings.append(
            f"Average charge power ({avg_power_kw:.2f} kW) exceeds charger limit "
            f"({GENERATOR_MAX_CHARGE_OUTPUT_KW:.2f} kW)."
        )

    if not (0.0 <= START_SOC < END_SOC <= 1.0):
        warnings.append("SOC window must satisfy 0 <= START_SOC < END_SOC <= 1.")

    if CHARGE_TIME_MIN <= 0:
        warnings.append("CHARGE_TIME_MIN must be greater than zero.")

    if CHARGES_PER_NIGHT <= 0:
        warnings.append("CHARGES_PER_NIGHT must be greater than zero.")

    return warnings

# =========================
# CREATE RAMP MODEL
# =========================

use_case = UseCase(
    date_start=DATE_START,
    date_end=DATE_END,
    peak_enlarge=0.10,
)

drone_operation = User(
    user_name=SITE_NAME,
    num_users=1,
)

use_case.add_user(drone_operation)

# =========================
# SHARED CONFIGURATION
# =========================

drone_config = {
    "site_name": SITE_NAME,
    "date_start": DATE_START,
    "date_end": DATE_END,
    "num_drones": NUM_DRONES,
    "num_batteries": NUM_BATTERIES,
    "charges_per_night": CHARGES_PER_NIGHT,
    "flight_time_min": FLIGHT_TIME_MIN,
    "cooling_time_min": COOLING_TIME_MIN,
    "swap_time_min": SWAP_TIME_MIN,
    "battery_nominal_voltage_v": BATTERY_NOMINAL_VOLTAGE_V,
    "battery_capacity_ah": BATTERY_CAPACITY_AH,
    "battery_nominal_energy_kwh": BATTERY_NOMINAL_ENERGY_KWH,
    "start_soc": START_SOC,
    "end_soc": END_SOC,
    "charge_time_min": CHARGE_TIME_MIN,
    "system_loss_fraction": SYSTEM_LOSS_FRACTION,
    "generator_name": GENERATOR_NAME,
    "generator_max_charge_output_kw": GENERATOR_MAX_CHARGE_OUTPUT_KW,
    "generator_fuel_l_per_kwh": GENERATOR_FUEL_L_PER_KWH,
    "generator_tank_l": GENERATOR_TANK_L,
    "monthly_night_temperature_c": MONTHLY_NIGHT_TEMPERATURE_C,
}