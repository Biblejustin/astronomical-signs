"""Astronomical events analysis plots.

These events differ from terrestrial catalogs: detection floor is set by
celestial mechanics + global astronomical attention rather than instrument
networks. Total eclipses in particular are predictable indefinitely from
orbital mechanics, so the "catalog" question is really "which were noted by
chroniclers."

Conventions:
- Pre-1500 events kept as research index; modern (1500+) for stats
- Power-law fit isn't meaningful for these qualitatively-different categories;
  use count-per-decade and inter-event intervals instead
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)

CATALOG_START = 1500
PARTIAL_DECADE_START = 2020

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "--",
})


def load_events() -> pd.DataFrame:
    df = pd.read_csv(HERE / "eclipses.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = df["date"].dt.year
    return df


def plot_01_events_timeline(df: pd.DataFrame):
    """Stacked event timeline by type."""
    fig, ax = plt.subplots(figsize=(13, 5))
    colors = {"total_solar": "#cc3322", "lunar": "#ffaa22", "comet": "#3377aa",
                "supernova": "#883388", "meteor_storm": "#229966",
                "solar_storm": "#dd66aa", "solar_event": "#cc99cc"}
    y_offsets = {t: i for i, t in enumerate(colors)}
    for t, color in colors.items():
        sub = df[df["type"] == t]
        ax.eventplot(sub["year"].dropna().values,
                       lineoffsets=y_offsets[t], linelengths=0.7,
                       color=color, label=t)
    ax.set_yticks(list(y_offsets.values()))
    ax.set_yticklabels(list(y_offsets.keys()))
    ax.set_xlabel("Year")
    ax.set_title("Astronomical events by type (this catalog's coverage)")
    ax.set_xlim(-500, 2030)
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    plt.tight_layout()
    plt.savefig(PLOTS / "01_events_timeline.png")
    plt.close()


def plot_02_eclipses_per_decade(df: pd.DataFrame):
    """Total solar eclipses per decade in this catalog (selection-biased: not
    all total eclipses are listed, only the historically significant ones)."""
    eclipses = df[df["type"] == "total_solar"].copy()
    eclipses["decade"] = (eclipses["year"] // 10) * 10
    decades = np.arange(CATALOG_START, 2030, 10)
    counts = [(eclipses["decade"] == d).sum() for d in decades]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(decades, counts, width=8, color="#cc3322", edgecolor="black", linewidth=0.4)
    ax.axvspan(PARTIAL_DECADE_START, PARTIAL_DECADE_START + 10,
                color="grey", alpha=0.18)
    ax.set_xlabel("Decade")
    ax.set_ylabel("Total solar eclipses in catalog")
    ax.set_title("Total solar eclipses per decade (selection-biased catalog — not all listed)")
    ax.text(0.02, 0.95,
              f"Real rate: ~24 total solar eclipses globally per century;\nthis catalog lists "
              f"only historically/scientifically significant ones.",
              transform=ax.transAxes, fontsize=9, va="top", alpha=0.8)
    # Multi-era trends — NB: all reflect catalog inclusion bias, not physical rate
    counts_arr = np.array(counts, dtype=float)
    eras = [
        (CATALOG_START, "Full catalog (1500+)", "#222222", "--"),
        (1800, "Modern astronomy (1800+)", "#33aa66", ":"),
        (1900, "Photographic era (1900+)", "#3366cc", "-."),
    ]
    fits = []
    rng = np.random.default_rng(42)
    for era_start, label, color, ls in eras:
        mask = (decades >= era_start) & (decades < PARTIAL_DECADE_START)
        if mask.sum() < 3:
            fits.append((label, np.nan, np.nan, np.nan)); continue
        x_fit = decades[mask].astype(float); y_fit = counts_arr[mask]
        if (y_fit > 0).sum() < 2:
            fits.append((label, np.nan, np.nan, np.nan)); continue
        slope, intercept = np.polyfit(x_fit, y_fit, 1)
        boots = []
        for _ in range(2000):
            idx = rng.integers(0, len(x_fit), len(x_fit))
            s, _ = np.polyfit(x_fit[idx], y_fit[idx], 1)
            boots.append(s)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        line_x = np.linspace(era_start, decades.max(), 50)
        ax.plot(line_x, slope * line_x + intercept, ls, color=color,
                  linewidth=1.6,
                  label=f"{label}: {slope:+.3f}/dec [CI {lo:+.3f}, {hi:+.3f}]")
        fits.append((label, slope, lo, hi))
    ax.legend(loc="upper right", fontsize=8)
    plt.tight_layout()
    plt.savefig(PLOTS / "02_eclipses_per_decade.png")
    plt.close()
    return fits


def plot_03_comets_timeline(df: pd.DataFrame):
    """Halley returns + great comets."""
    comets = df[df["type"] == "comet"].dropna(subset=["date"]).copy()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    is_halley = comets["notes_significance"].str.contains("Halley", case=False, na=False)
    halley = comets[is_halley]
    great = comets[~is_halley]
    ax.scatter(halley["year"], np.full(len(halley), 0.7), s=200,
                marker="*", color="#3377aa", edgecolor="black", linewidth=0.6,
                label=f"Halley's ({len(halley)} apparitions)")
    ax.scatter(great["year"], np.full(len(great), 0.3), s=120,
                marker="o", color="#ee9933", edgecolor="black", linewidth=0.5,
                label=f"Other great comets ({len(great)})")
    ax.set_yticks([0.3, 0.7])
    ax.set_yticklabels(["Other", "Halley"])
    ax.set_xlabel("Year")
    ax.set_title("Naked-eye comets (Halley returns + great comets)")
    ax.set_ylim(0, 1)
    ax.set_xlim(comets["year"].min() - 20, 2030)
    # Inter-Halley intervals
    halley_years = sorted(halley["year"].values)
    intervals = np.diff(halley_years)
    if len(intervals) > 0:
        ax.text(0.02, 0.05,
                  f"Halley inter-return: mean {intervals.mean():.1f} yr "
                  f"(theoretical: 75.3)",
                  transform=ax.transAxes, fontsize=9, alpha=0.85)
    ax.legend(loc="upper left", fontsize=9)
    plt.tight_layout()
    plt.savefig(PLOTS / "03_comets_timeline.png")
    plt.close()


def plot_04_supernovae(df: pd.DataFrame):
    """Visible supernovae over recorded history."""
    sne = df[df["type"] == "supernova"].dropna(subset=["date"]).copy().sort_values("year")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.scatter(sne["year"], np.zeros(len(sne)), s=300, marker="*",
                color="#883388", edgecolor="black", linewidth=0.6)
    for _, row in sne.iterrows():
        ax.annotate(row["notes_significance"].split(";")[0][:22],
                    (row["year"], 0), xytext=(0, 12), textcoords="offset points",
                    ha="center", fontsize=8, rotation=30, alpha=0.85)
    ax.set_yticks([])
    ax.set_xlabel("Year")
    ax.set_title(f"Naked-eye supernovae ({len(sne)} total in {sne['year'].max() - sne['year'].min()} years; expected galactic rate ~1/100yr)")
    ax.set_xlim(0, 2050)
    ax.set_ylim(-0.5, 0.5)
    # Inter-supernova intervals
    intervals = np.diff(sne["year"].values)
    if len(intervals) > 0:
        ax.text(0.02, 0.05,
                  f"Mean inter-event: {intervals.mean():.0f} yr; "
                  f"383-year gap 1604→1987 since Kepler's nova",
                  transform=ax.transAxes, fontsize=9, alpha=0.85)
    plt.tight_layout()
    plt.savefig(PLOTS / "04_supernovae.png")
    plt.close()


def main():
    df = load_events()
    print(f"Loaded {len(df)} astronomical events")
    print(f"Types: {df['type'].value_counts().to_dict()}")
    plot_01_events_timeline(df)
    fits = plot_02_eclipses_per_decade(df)
    print("Decadal eclipse-catalog trends (selection-bias-dominated, not real eclipse rate):")
    for label, slope, lo, hi in fits:
        print(f"  {label:<40} {slope:+.3f}/dec  [CI {lo:+.3f}, {hi:+.3f}]")
    plot_03_comets_timeline(df)
    plot_04_supernovae(df)
    print(f"Wrote 4 plots to {PLOTS}/")


if __name__ == "__main__":
    main()
