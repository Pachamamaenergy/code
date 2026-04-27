import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

LOG_CSV = "tuya_log_long.csv"
TZ = "Europe/Stockholm"


def load_log():
    df = pd.read_csv(LOG_CSV)

    df["sample_time_utc"] = pd.to_datetime(
        df["sample_time_utc"], utc=True, errors="coerce"
    )
    df = df.dropna(subset=["sample_time_utc"])

    df["dt"] = df["sample_time_utc"].dt.tz_convert(TZ)
    df["scaled_value"] = pd.to_numeric(df["scaled_value"], errors="coerce")
    df = df.dropna(subset=["scaled_value"])

    return df


def format_time_axis(ax):
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
    )
    ax.grid(True)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(20)
        lbl.set_ha("right")


def plot_signal(df, code, title, ylabel):
    d = df[df["code"] == code].sort_values("dt")
    if d.empty:
        print(f"⚠️ Ingen data för {code}")
        return

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(d["dt"], d["scaled_value"])
    ax.set_title(title)
    ax.set_xlabel("Tid")
    ax.set_ylabel(ylabel)
    format_time_axis(ax)


def main():
    df = load_log()

    # -------- Channel A --------
    plot_signal(df, "power_a", "Channel A – Effekt över tid", "Effekt (W)")
    plot_signal(df, "current_a", "Channel A – Ström över tid", "Ström (A)")
    plot_signal(df, "energy_forword_a", "Channel A – Energi forward (counter)", "Energi (kWh)")
    plot_signal(df, "energy_reverse_a", "Channel A – Energi reverse (counter)", "Energi (kWh)")

    # -------- Channel B --------
    plot_signal(df, "power_b", "Channel B – Effekt över tid", "Effekt (W)")
    plot_signal(df, "current_b", "Channel B – Ström över tid", "Ström (A)")
    plot_signal(df, "energy_forword_b", "Channel B – Energi forward (counter)", "Energi (kWh)")
    plot_signal(df, "energy_reserse_b", "Channel B – Energi reverse (counter)", "Energi (kWh)")

    # -------- Total --------
    plot_signal(df, "total_power", "Total – Effekt över tid", "Effekt (W)")
    plot_signal(df, "forward_energy_total", "Total – Energi forward (counter)", "Energi (kWh)")
    plot_signal(df, "reverse_energy_total", "Total – Energi reverse (counter)", "Energi (kWh)")

    # 🔑 EN ENDA show → alla fönster visas samtidigt
    plt.show()


if __name__ == "__main__":
    main()
