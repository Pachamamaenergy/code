# PV Simulation & Cost Analysis
# Overview

This script simulates the energy production of a photovoltaic (PV) system using weather data and evaluates its economic performance over 25 years. It compares a Business-As-Usual (BAU) electricity scenario with two alternatives: PV with net metering and PV combined with battery storage.

# Requirements

Install the required packages:

pip install pvlib pandas numpy matplotlib openpyxl

What the script does

The script downloads weather data, runs a PV simulation using pvlib, and calculates hourly, monthly, and annual energy production.
It then compares the energy production to a BAU case where the assumption that every kwH produced is either used, stored in the battery or stored in the grid via net metering.

# Output

The results are saved as:

pv_simulation.xlsx (energy and cost data)
timeseries_with_bau.csv (hourly time series)
