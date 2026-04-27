# analyze_drone_profile.py

"""
Deterministic drone charging load model based on one repeated night-shift pattern.

This script:
- imports the configuration from users.py
- builds a 1-minute load profile for every day of the year
- models one night shift with 40 charging events
- applies a mild monthly temperature correction
- calculates daily, monthly, and annual energy use
- estimates fuel consumption from generator-specific fuel use
- creates one combined figure with:
    1) one day power profile
    2) one month daily energy
    3) one year daily energy
    4) monthly fuel use
- saves CSV outputs and one PNG figure
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from users import (
    DATE_START,
    DATE_END,
    CHARGES_PER_NIGHT,
    CHARGE_TIME_MIN,
    GENERATOR_FUEL_L_PER_KWH,
    get_generator_energy_per_charge_kwh,
    get_temperature_factor,
    get_average_charge_power_kw,
    validate_model,
)

# =========================
# SETTINGS
# =========================

MINUTES_PER_DAY = 24 * 60
SHIFT_START_HOUR = 18  # 18:00
SHIFT_END_HOUR = 3     # 03:00 next morning

# =========================
# HELPER FUNCTIONS
# =========================

def build_daily_profile(month):
    """
    Create a 1-minute power profile for one full day in kW.

    The model assumes:
    - one night shift starts at 18:00
    - 40 charging events occur during the shift
    - each charge lasts CHARGE_TIME_MIN
    - each charge has constant average power
    - temperature affects the required electrical energy mildly

    Parameters
    ----------
    month : int
        Calendar month (1-12)

    Returns
    -------
    numpy.ndarray
        Array of length 1440 with power values in kW
    """
    profile = np.zeros(MINUTES_PER_DAY)

    avg_charge_power_kw = get_average_charge_power_kw()
    temp_factor = get_temperature_factor(month)

    # Shift is from 18:00 to 03:00 next day = 9 hours = 540 min
    shift_start_min = SHIFT_START_HOUR * 60
    shift_duration_min = 9 * 60

    # Place charges evenly across the shift
    charge_spacing_min = shift_duration_min / CHARGES_PER_NIGHT

    for charge_index in range(CHARGES_PER_NIGHT):
        start_minute = int(round(shift_start_min + charge_index * charge_spacing_min))
        end_minute = start_minute + CHARGE_TIME_MIN

        # Temperature-corrected charging power
        charge_power_kw = avg_charge_power_kw * temp_factor

        for minute in range(start_minute, end_minute):
            wrapped_minute = minute % MINUTES_PER_DAY
            profile[wrapped_minute] += charge_power_kw

    return profile


def create_time_windows(results_df):
    """
    Select useful plotting windows:
    - one day
    - one month
    - full year
    """
    start_ts = pd.Timestamp(DATE_START)

    one_day_df = results_df[
        (results_df["datetime"] >= start_ts) &
        (results_df["datetime"] < start_ts + pd.Timedelta(days=1))
    ]

    one_month_df = results_df[
        (results_df["datetime"] >= start_ts) &
        (results_df["datetime"] < start_ts + pd.Timedelta(days=31))
    ]

    one_year_df = results_df.copy()

    return one_day_df, one_month_df, one_year_df


# =========================
# VALIDATE MODEL
# =========================

warnings = validate_model()

if warnings:
    print("\nModel warnings:")
    for warning in warnings:
        print(f"- {warning}")
else:
    print("\nModel validation passed with no warnings.")

# =========================
# BUILD FULL-YEAR PROFILE
# =========================

date_index = pd.date_range(
    start=f"{DATE_START} 00:00:00",
    end=f"{DATE_END} 23:59:00",
    freq="min"
)

results_df = pd.DataFrame(index=date_index)
results_df["power_kW"] = 0.0

daily_dates = pd.date_range(
    start=DATE_START,
    end=DATE_END,
    freq="D"
)

for current_date in daily_dates:
    month = current_date.month
    daily_profile = build_daily_profile(month)

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
annual_fuel_liters = annual_energy_kWh * GENERATOR_FUEL_L_PER_KWH

daily_energy = (
    results_df
    .set_index("datetime")
    .resample("D")["energy_kWh"]
    .sum()
    .reset_index()
)

daily_energy["fuel_liters"] = daily_energy["energy_kWh"] * GENERATOR_FUEL_L_PER_KWH

monthly_energy = (
    results_df
    .set_index("datetime")
    .resample("ME")["energy_kWh"]
    .sum()
    .reset_index()
)

monthly_energy["month"] = monthly_energy["datetime"].dt.strftime("%Y-%m")
monthly_energy["fuel_liters"] = monthly_energy["energy_kWh"] * GENERATOR_FUEL_L_PER_KWH
monthly_energy = monthly_energy[["month", "energy_kWh", "fuel_liters"]]

summary_df = pd.DataFrame({
    "metric": [
        "energy_per_charge_kWh",
        "annual_energy_kWh",
        "annual_fuel_liters",
    ],
    "value": [
        get_generator_energy_per_charge_kwh(),
        annual_energy_kWh,
        annual_fuel_liters,
    ]
})

print(f"\nEnergy per charge: {get_generator_energy_per_charge_kwh():.3f} kWh")
print(f"Annual energy consumption: {annual_energy_kWh:,.2f} kWh")
print(f"Annual fuel consumption: {annual_fuel_liters:,.2f} L\n")

print("Monthly energy and fuel consumption:")
print(monthly_energy.to_string(index=False))

# =========================
# SAVE OUTPUT FILES
# =========================

results_df.to_csv("drone_load_profile.csv", index=False)
daily_energy.to_csv("drone_daily_energy.csv", index=False)
monthly_energy.to_csv("drone_monthly_energy.csv", index=False)
summary_df.to_csv("drone_summary.csv", index=False)

print("\nSaved files:")
print("- drone_load_profile.csv")
print("- drone_daily_energy.csv")
print("- drone_monthly_energy.csv")
print("- drone_summary.csv")

# =========================
# PLOT DATA SELECTION
# =========================

one_day_df, _, one_year_df = create_time_windows(results_df)

one_year_daily_energy = (
    one_year_df
    .set_index("datetime")
    .resample("D")["energy_kWh"]
    .sum()
    .reset_index()
)

monthly_fuel_plot = monthly_energy.copy()

# =========================
# ONE FIGURE WITH 3 SUBPLOTS
# =========================

import matplotlib.dates as mdates

# Prepare cleaner month labels
monthly_fuel_plot = monthly_energy.copy()
monthly_fuel_plot["month_dt"] = pd.to_datetime(monthly_fuel_plot["month"])
monthly_fuel_plot["month_label"] = monthly_fuel_plot["month_dt"].dt.strftime("%b")

# Prepare full-year daily energy
one_year_daily_energy = (
    one_year_df
    .set_index("datetime")
    .resample("D")["energy_kWh"]
    .sum()
    .reset_index()
)

# Global style adjustments
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
})

fig, axes = plt.subplots(
    3, 1,
    figsize=(14, 12),
    constrained_layout=True
)

# -------------------------
# 1) One day power profile
# -------------------------
axes[0].plot(
    one_day_df["datetime"],
    one_day_df["power_kW"],
    linewidth=2.0
)
axes[0].set_title("Drone Charging Load Profile — One Day", pad=12)
axes[0].set_xlabel("Time")
axes[0].set_ylabel("Power (kW)")
axes[0].grid(True, alpha=0.3)

# Cleaner hour formatting
axes[0].xaxis.set_major_locator(mdates.HourLocator(interval=3))
axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
axes[0].tick_params(axis="x", rotation=0)

# Remove extra margins on x-axis
axes[0].margins(x=0.01)

# -------------------------
# 2) One year daily energy
# -------------------------
# Line plot is cleaner and more professional than 365 bars
axes[1].plot(
    one_year_daily_energy["datetime"],
    one_year_daily_energy["energy_kWh"],
    linewidth=1.8
)
axes[1].set_title("Daily Charging Energy — One Year", pad=12)
axes[1].set_xlabel("Month")
axes[1].set_ylabel("Energy (kWh)")
axes[1].grid(True, alpha=0.3)

# Show month abbreviations only
axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=1))
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
axes[1].tick_params(axis="x", rotation=0)
axes[1].margins(x=0.01)

# -------------------------
# 3) Monthly fuel consumption
# -------------------------
axes[2].bar(
    monthly_fuel_plot["month_label"],
    monthly_fuel_plot["fuel_liters"],
    width=0.8
)
axes[2].set_title("Monthly Fuel Consumption", pad=12)
axes[2].set_xlabel("Month")
axes[2].set_ylabel("Fuel (L)")
axes[2].grid(True, axis="y", alpha=0.3)
axes[2].tick_params(axis="x", rotation=0)

# Optional: reduce top/right border clutter
for ax in axes:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

# Save figure with clean margins for report use
plt.savefig("drone_combined_plots.png", dpi=300, bbox_inches="tight")
plt.show()