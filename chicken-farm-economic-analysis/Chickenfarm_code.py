import matplotlib
matplotlib.use('Agg')

import pvlib
import pandas as pd
import numpy as np

# -------------------------
# 1. Location
# -------------------------
latitude = -17.3895
longitude = -66.1568
tz = "America/La_Paz"

location = pvlib.location.Location(latitude, longitude, tz=tz)

# -------------------------
# 2. Systemsize
# -------------------------
n_panels = 475
panel_power = 400  # W
system_size_kwp = (n_panels * panel_power) / 1000  # kWp

# -------------------------
# 3. Weather data
# -------------------------
weather, meta = pvlib.iotools.get_pvgis_tmy(
    latitude,
    longitude,
    outputformat="json"
)

weather["temp_air"] = weather.get("temp_air", 25)
weather["wind_speed"] = weather.get("wind_speed", 1)

weather.index = pd.to_datetime(weather.index)

if weather.index.tz is None:
    weather = weather.tz_localize(tz)
else:
    weather = weather.tz_convert(tz)

# -------------------------
# 4. Temperaturemodel
# -------------------------
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS[
    "sapm"
]["open_rack_glass_polymer"]

# -------------------------
# 5. PV system
# -------------------------
system = pvlib.pvsystem.PVSystem(
    surface_tilt=20,
    surface_azimuth=0,
    module_parameters={
        "pdc0": system_size_kwp * 1000,
        "gamma_pdc": -0.0035
    },
    inverter_parameters={
        "pdc0": system_size_kwp * 1000
    },
    temperature_model_parameters=temperature_model_parameters
)

mc = pvlib.modelchain.ModelChain(
    system,
    location,
    aoi_model="physical",
    spectral_model="no_loss"
)

mc.run_model(weather)

# -------------------------
# 6. PV results
# -------------------------
ac_power = mc.results.ac.fillna(0)
annual_pv_generation = ac_power.sum() / 1000  # kWh

print("PV yearly production:", round(annual_pv_generation, 1), "kWh")

# -------------------------
# 7. Time adjustment
# -------------------------
ac_power = ac_power.copy()
ac_power.index = ac_power.index.tz_convert(None)
ac_power.index = ac_power.index.map(lambda dt: dt.replace(year=2025))
ac_power = ac_power.sort_index()

monthly_energy = ac_power.resample("MS").sum() / 1000

# -------------------------
# 8. demand
# -------------------------
bau_energy_kwh = 121000  # demand for chicken farm
pv_energy_kwh = annual_pv_generation  # 475 paneler (matches the most demanding day))

# -------------------------
# 9. cost parameters
# -------------------------
simulation_years = 25
price_growth = 0.05

# Fossil fuels
gas_price_subsidized = 0.0418
gas_price_unsubsidized = 0.138
diesel_price = 0.145

diesel_share = 0.014
gas_share = 1 - diesel_share

# PV system
capex_per_w = 1.78
pv_investment = system_size_kwp * 1000 * capex_per_w

om_per_kw_year = 19
annual_om_cost = system_size_kwp * om_per_kw_year

battery_cost_per_kwh = 362
DoD = 0.8

battery_capacity_kwh = pv_energy_kwh / 365 / DoD
battery_investment = battery_capacity_kwh * battery_cost_per_kwh

# -------------------------
# 10. economy model
# -------------------------
years = np.arange(1, simulation_years + 1)

costs = pd.DataFrame(index=years)

BAU = []
BAU_unsub = []

for year in years:
    factor = (1 + price_growth) ** (year - 1)

    blended_sub = (
        gas_share * gas_price_subsidized +
        diesel_share * diesel_price
    )

    blended_unsub = (
        gas_share * gas_price_unsubsidized +
        diesel_share * diesel_price
    )

    BAU.append(bau_energy_kwh * blended_sub * factor)
    BAU_unsub.append(bau_energy_kwh * blended_unsub * factor)

costs["BAU"] = BAU
costs["BAU_unsubsidized"] = BAU_unsub

# -------------------------
# PV (CAPEX + O&M only)
# -------------------------
PV_Battery = []

for year in years:
    if year == 1:
        total = pv_investment + battery_investment + annual_om_cost
    else:
        total = annual_om_cost
    PV_Battery.append(total)

costs["PV_Battery"] = PV_Battery

# -------------------------
# 11. cumulative costs
# -------------------------
costs["BAU_cum"] = costs["BAU"].cumsum()
costs["BAU_unsubsidized_cum"] = costs["BAU_unsubsidized"].cumsum()
costs["PV_Battery_cum"] = costs["PV_Battery"].cumsum()

# -------------------------
# 12. Export
# -------------------------
with pd.ExcelWriter("Chickenfarm_analysis.xlsx") as writer:
    ac_power.to_frame("AC_Power").to_excel(writer, sheet_name="Hourly_PV")
    monthly_energy.to_frame("Monthly_Energy").to_excel(writer, sheet_name="Monthly_PV")
    costs.to_excel(writer, sheet_name="Cost_Simulation")

print("Excel-fil skapad: Chickenfarm_analysis.xlsx")
