# analyze_farm_profile.py

"""
Deterministic chicken farm load model based on the 40-day production cycle.

This script:
- avoids double counting of heating stages
- maps each calendar day to exactly one day in the 40-day cycle
- applies a monthly weather correction to heating demand
- creates one combined figure with:
    1) one day
    2) one week
    3) one month
    4) monthly energy
- calculates annual and monthly energy consumption

It uses the configuration from users.py and does not rely on loads.py.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from users import farm_config, GAS_ALLOCATION

# =========================
# MODEL SETTINGS
# =========================

YEAR = 2025
MINUTES_PER_DAY = 24 * 60
CYCLE_DAYS = farm_config["cycle_days"]

# Gas distribution across the day
# These fractions must sum to 1.0
GAS_DISTRIBUTION = {
    "night": 0.35,    # 00:00-06:00
    "morning": 0.20,  # 06:00-10:00
    "day": 0.10,      # 10:00-16:00
    "evening": 0.35,  # 16:00-24:00
}

# Monthly average night temperatures (°C) for Cochabamba area
# These are used as a first-order approximation for heating correction.
MONTHLY_NIGHT_TEMPERATURE = {
    1: 14,  # January
    2: 13,  # February
    3: 13,  # March
    4: 11,  # April
    5: 7,   # May
    6: 5,   # June
    7: 5,   # July
    8: 7,   # August
    9: 10,  # September
    10: 12, # October
    11: 14, # November
    12: 14, # December
}

# Weather correction bounds
# Coldest months -> higher factor
# Warmest months -> lower factor
WEATHER_FACTOR_COLD = 1.40
WEATHER_FACTOR_WARM = 0.60

# Diesel use assumptions
WATER_KWH_PER_DAY = farm_config["diesel_water_kwh_per_cycle"] / farm_config["cycle_days"]
HYGIENE_DAILY_KWH_PER_DAY = farm_config["diesel_hygiene_daily_kwh_per_cycle"] / farm_config["cycle_days"]

# Intensive cleaning is modeled as two event days per 40-day cycle
# Half of the cycle event energy is assigned to day 20, half to day 40
INTENSIVE_EVENT_KWH_PER_EVENT = farm_config["diesel_hygiene_event_kwh_per_cycle"] / 2.0

# =========================
# HELPER FUNCTIONS
# =========================

def get_cycle_day(date_value):
    """
    Return the day in the 40-day production cycle (1 to 40).
    January 1 is treated as cycle day 1.
    """
    day_of_year_index = (date_value - pd.Timestamp(f"{YEAR}-01-01")).days
    return (day_of_year_index % CYCLE_DAYS) + 1

def get_gas_kwh_for_cycle_day(cycle_day, gas_allocation):
    """
    Return the base daily gas demand (kWh/day) for the current cycle day.

    gas_allocation entries are:
    (start_day, end_day, weight, allocated_kwh, kwh_per_day)
    """
    for start_day, end_day, weight, allocated_kwh, kwh_per_day in gas_allocation:
        if start_day <= cycle_day <= end_day:
            return kwh_per_day
    return 0.0

def get_weather_factor(month):
    """
    Return a monthly heating correction factor based on average night temperature.

    Colder months -> higher factor
    Warmer months -> lower factor

    The factor is scaled linearly between:
    - WEATHER_FACTOR_COLD at the coldest observed temperature
    - WEATHER_FACTOR_WARM at the warmest observed temperature
    """
    t_out = MONTHLY_NIGHT_TEMPERATURE[month]

    t_min = min(MONTHLY_NIGHT_TEMPERATURE.values())  # coldest month temperature
    t_max = max(MONTHLY_NIGHT_TEMPERATURE.values())  # warmest month temperature

    # Avoid division by zero if all temperatures were identical
    if t_max == t_min:
        return 1.0

    # Normalize: warmest -> 1, coldest -> 0
    norm = (t_out - t_min) / (t_max - t_min)

    # Invert so colder months get higher heating demand
    factor = WEATHER_FACTOR_COLD - norm * (WEATHER_FACTOR_COLD - WEATHER_FACTOR_WARM)

    return factor

def build_daily_profile(cycle_day, gas_kwh_day):
    """
    Create a 1-minute power profile for one day in kW.

    Inputs
    ------
    cycle_day : int
        Day in the 40-day production cycle
    gas_kwh_day : float
        Total gas heating energy for this specific day (already weather-corrected)

    Returns
    -------
    numpy.ndarray
        Array of length 1440 with power values in kW
    """
    profile = np.zeros(MINUTES_PER_DAY)

    # -------------------------
    # GAS PROFILE
    # -------------------------
    # Constant power inside each time block

    gas_blocks = [
        ("night",    0,      6 * 60, 6),  # 00:00-06:00
        ("morning",  6 * 60, 10 * 60, 4), # 06:00-10:00
        ("day",     10 * 60, 16 * 60, 6), # 10:00-16:00
        ("evening", 16 * 60, 24 * 60, 8), # 16:00-24:00
    ]

    for block_name, start_min, end_min, hours in gas_blocks:
        block_energy_kwh = gas_kwh_day * GAS_DISTRIBUTION[block_name]
        block_power_kw = block_energy_kwh / hours
        profile[start_min:end_min] += block_power_kw

    # -------------------------
    # DIESEL - WATER PUMPING
    # -------------------------
    # 4 hours/day total:
    # 06:00-08:00 and 11:00-13:00

    water_power_kw = WATER_KWH_PER_DAY / 4.0
    profile[6 * 60:8 * 60] += water_power_kw
    profile[11 * 60:13 * 60] += water_power_kw

    # -------------------------
    # DIESEL - DAILY HYGIENE
    # -------------------------
    # 2 hours/day: 08:00-10:00

    hygiene_power_kw = HYGIENE_DAILY_KWH_PER_DAY / 2.0
    profile[8 * 60:10 * 60] += hygiene_power_kw

    # -------------------------
    # DIESEL - INTENSIVE CLEANING EVENTS
    # -------------------------
    # Event days only: cycle day 20 and 40
    # 2 hours: 10:00-12:00

    if cycle_day in [20, 40]:
        intensive_power_kw = INTENSIVE_EVENT_KWH_PER_EVENT / 2.0
        profile[10 * 60:12 * 60] += intensive_power_kw

    return profile

# =========================
# BUILD FULL-YEAR PROFILE
# =========================

date_index = pd.date_range(
    start=f"{YEAR}-01-01 00:00:00",
    end=f"{YEAR}-12-31 23:59:00",
    freq="min"
)

results_df = pd.DataFrame(index=date_index)
results_df["power_kW"] = 0.0

daily_dates = pd.date_range(
    start=f"{YEAR}-01-01",
    end=f"{YEAR}-12-31",
    freq="D"
)

for current_date in daily_dates:
    cycle_day = get_cycle_day(current_date)

    # Base gas demand from bird age / cycle stage
    base_gas_kwh_day = get_gas_kwh_for_cycle_day(cycle_day, GAS_ALLOCATION)

    # Weather correction from monthly night temperature
    weather_factor = get_weather_factor(current_date.month)

    # Final gas demand for this calendar day
    gas_kwh_day = base_gas_kwh_day * weather_factor

    # Build the full daily power profile
    daily_profile = build_daily_profile(cycle_day, gas_kwh_day)

    day_start = pd.Timestamp(current_date)
    day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)

    results_df.loc[day_start:day_end, "power_kW"] = daily_profile

# Energy per minute-step
results_df["energy_kWh"] = results_df["power_kW"] / 60.0

# Keep datetime as a column as well
results_df = results_df.reset_index().rename(columns={"index": "datetime"})

# =========================
# ENERGY RESULTS
# =========================

annual_energy_kWh = results_df["energy_kWh"].sum()

monthly_energy = (
    results_df
    .set_index("datetime")
    .resample("ME")["energy_kWh"]
    .sum()
    .reset_index()
)

monthly_energy["month"] = monthly_energy["datetime"].dt.strftime("%Y-%m")
monthly_energy = monthly_energy[["month", "energy_kWh"]]

print(f"\nAnnual energy consumption: {annual_energy_kWh:,.2f} kWh\n")
print("Monthly energy consumption:")
print(monthly_energy.to_string(index=False))

# =========================
# SAVE OUTPUT FILES
# =========================

results_df.to_csv("farm_load_profile.csv", index=False)
monthly_energy.to_csv("farm_monthly_energy.csv", index=False)

summary_df = pd.DataFrame({
    "metric": ["annual_energy_kWh"],
    "value": [annual_energy_kWh]
})
summary_df.to_csv("farm_summary.csv", index=False)

print("\nSaved files:")
print("- farm_load_profile.csv")
print("- farm_monthly_energy.csv")
print("- farm_summary.csv")

# =========================
# PLOT DATA SELECTION
# =========================

day_df = results_df[
    (results_df["datetime"] >= f"{YEAR}-01-01 00:00:00") &
    (results_df["datetime"] <  f"{YEAR}-01-02 00:00:00")
]

week_df = results_df[
    (results_df["datetime"] >= f"{YEAR}-01-01 00:00:00") &
    (results_df["datetime"] <  f"{YEAR}-01-08 00:00:00")
]

month_df = results_df[
    (results_df["datetime"] >= f"{YEAR}-01-01 00:00:00") &
    (results_df["datetime"] <  f"{YEAR}-02-01 00:00:00")
]


# =========================
# ONE FIGURE WITH 3 SUBPLOTS
# =========================

import matplotlib.dates as mdates

# Prepare cleaner month labels
monthly_energy_plot = monthly_energy.copy()
monthly_energy_plot["month_dt"] = pd.to_datetime(monthly_energy_plot["month"])
monthly_energy_plot["month_label"] = monthly_energy_plot["month_dt"].dt.strftime("%b")

# Create daily energy for full year (for clean yearly plot)
year_daily_energy = (
    results_df
    .set_index("datetime")
    .resample("D")["energy_kWh"]
    .sum()
    .reset_index()
)

# Global style
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
})

fig, axes = plt.subplots(
    3, 1,
    figsize=(14, 12),
    constrained_layout=True
)

# -------------------------
# 1) One day
# -------------------------
axes[0].plot(
    day_df["datetime"],
    day_df["power_kW"],
    linewidth=2.0
)
axes[0].set_title("Chicken Farm Load Profile — One Day", pad=12)
axes[0].set_xlabel("Time")
axes[0].set_ylabel("Power (kW)")
axes[0].grid(True, alpha=0.3)

axes[0].xaxis.set_major_locator(mdates.HourLocator(interval=3))
axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
axes[0].margins(x=0.01)

# -------------------------
# 2) One month
# -------------------------
axes[1].plot(
    month_df["datetime"],
    month_df["power_kW"],
    linewidth=1.8
)
axes[1].set_title("Chicken Farm Load Profile — One Month", pad=12)
axes[1].set_xlabel("Date")
axes[1].set_ylabel("Power (kW)")
axes[1].grid(True, alpha=0.3)

axes[1].xaxis.set_major_locator(mdates.DayLocator(interval=4))
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
axes[1].margins(x=0.01)

# -------------------------
# 3) One year (daily energy)
# -------------------------
axes[2].plot(
    year_daily_energy["datetime"],
    year_daily_energy["energy_kWh"],
    linewidth=1.8
)
axes[2].set_title("Daily Energy Consumption — One Year", pad=12)
axes[2].set_xlabel("Month")
axes[2].set_ylabel("Energy (kWh)")
axes[2].grid(True, alpha=0.3)

axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=1))
axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
axes[2].margins(x=0.01)

# Clean look
for ax in axes:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

# Save
plt.savefig("farm_combined_plots.png", dpi=300, bbox_inches="tight")
plt.show()
