# PV Chicken Farm Analysis

This project evaluates the economic impact of installing a photovoltaic (PV) system for a chicken farm and compares it to fossil fuel-based electricity generation over a 25-year period.

The model simulates PV energy production using historical weather data and estimates how much of the farm’s electricity demand can be covered by solar power. It then compares the long-term costs of the different scenarios: continued fossil fuel usage (BAU), BAU with unsubsidized propane prices and PV combined with battery storage.

## Requirements
Install the required Python packages before running the simulation. The model relies on pvlib for PV system simulation and several standard scientific Python libraries for data handling and analysis:

```bash
pip install pvlib pandas numpy matplotlib openpyxl
