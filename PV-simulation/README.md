# PV Simulation & Cost Analysis

## Overview

This script simulates the energy production of a photovoltaic (PV) system using weather data and evaluates its economic performance over 25 years. It compares a Business-As-Usual (BAU) electricity scenario with two alternatives: PV with net metering and PV combined with battery storage.

## Requirements

Install the required packages before running the simulation. You must also install pvlib and all its dependencies, as it is the core library used for PV modeling:

```bash
pip install pvlib pandas numpy matplotlib openpyxl
