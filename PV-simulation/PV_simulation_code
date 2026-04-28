import matplotlib
matplotlib.use('Agg')

import pvlib
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# -------------------------
# 1. Plats
# -------------------------
latitude = -17.3895
longitude = -66.1568
tz = "America/La_Paz"

location = pvlib.location.Location(latitude, longitude, tz=tz)

# -------------------------
# 2. Systemstorlek
# -------------------------
n_panels = 475
panel_power = 400  # W
system_size_kwp = (n_panels * panel_power) / 1000

# -------------------------
# 3. Väderdata
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
# 4. Temperaturmodell
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

# -------------------------
# 6. ModelChain
# -------------------------
mc = pvlib.modelchain.ModelChain(
    system,
    location,
    aoi_model="physical",
    spectral_model="no_loss"
)

mc.run_model(weather)

# -------------------------
# 7. Resultat PV
# -------------------------
ac_power = mc.results.ac.fillna(0)

annual_energy = ac_power.sum() / 1000  # kWh

print("Veckoproduktion:", round(annual_energy/52, 1), "kWh")
print("Årsproduktion:", round(annual_energy, 1), "kWh")
print("Specifik produktion:", round(annual_energy/system_size_kwp, 1), "kWh/kWp")

# -------------------------
# 7b. BAU (endast el)
# -------------------------
annual_load_kwh = annual_energy  # Ändra om du har riktig data

# konstant lastprofil (kW)
load_kw = annual_load_kwh / 8760
load_profile = pd.Series(load_kw, index=ac_power.index)

# elpris
electricity_price = 0.190  # $/kWh
electricity_price_series = pd.Series(electricity_price, index=ac_power.index)

# BAU kostnad per timme
bau_hourly_cost = load_profile * electricity_price_series

# spara i results
mc.results.bau_load = load_profile
mc.results.bau_cost = bau_hourly_cost
mc.results.bau_energy = load_profile  # kWh per timme

# -------------------------
# 8. Justera år till 2025
# -------------------------
ac_power = ac_power.copy()
ac_power.index = ac_power.index.tz_convert(None)
ac_power.index = ac_power.index.map(lambda dt: dt.replace(year=2025))
ac_power = ac_power.sort_index()

# Uppdatera BAU-serier också
load_profile.index = ac_power.index
bau_hourly_cost.index = ac_power.index

# Månatliga summeringar
monthly_energy = ac_power.resample("MS").sum() / 1000

# -------------------------
# 9. Kostnadsparametrar
# -------------------------
simulation_years = 25

# CAPEX PV
capex_per_w = 1.78  # $/Wdc
pv_investment = system_size_kwp * 1000 * capex_per_w

# O&M PV
om_per_kw_year = 30  # $/kW/year
annual_om_cost = system_size_kwp * om_per_kw_year

# Batteri
battery_cost_per_kwh = 362
DoD = 0.8

daily_load_kwh = annual_load_kwh / 365
battery_capacity_kwh = daily_load_kwh / DoD

battery_investment = battery_capacity_kwh * battery_cost_per_kwh

# -------------------------
# 10. BAU kostnadsmodell
# -------------------------
years = np.arange(1, simulation_years + 1)

costs = pd.DataFrame(index=years)

price_growth = 0.05

bau_costs = []
yearly_bau_costs = []

current_price = electricity_price
cumulative_cost = 0

for year in years:
    yearly_cost = annual_load_kwh * current_price
    
    yearly_bau_costs.append(yearly_cost)
    
    cumulative_cost += yearly_cost
    bau_costs.append(cumulative_cost)

    current_price *= (1 + price_growth)

costs["BAU"] = bau_costs
costs["BAU_yearly"] = yearly_bau_costs

# -------------------------
# 11. PV scenarier
# -------------------------
costs["PV_NetMetering"] = pv_investment + (annual_om_cost * years)

costs["PV_Battery"] = (
    pv_investment +
    battery_investment +
    (annual_om_cost * years)
)

# -------------------------
# 12. Export data
# -------------------------
results_df = pd.DataFrame({
    "PV_AC_kW": ac_power,
    "Load_kW": load_profile,
    "BAU_cost_$": bau_hourly_cost
})

results_df.to_csv("timeseries_with_bau.csv")

# -------------------------
# 13. Spara till Excel
# -------------------------
with pd.ExcelWriter("pv_simulation.xlsx") as writer:
    ac_power.to_frame("AC_Power").to_excel(writer, sheet_name="Hourly_PV")
    monthly_energy.to_frame("Monthly_Energy").to_excel(writer, sheet_name="Monthly_PV")
    costs.to_excel(writer, sheet_name="Cost_Simulation")
    results_df.to_excel(writer, sheet_name="TimeSeries")

print("Excel-fil 'pv_simulation.xlsx' skapad med tim-, månadsdata och kostnader")
