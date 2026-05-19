# astronomical-signs

Catalog of notable astronomical events: total solar/lunar eclipses, naked-eye comets, visible supernovae, and major meteor storms. Compiled to support the "signs in the heavens" branch of the correlation analysis (Mt 24:29 framing).

Parallel to `earthquakes`, `spaceweather`, `famines-tracking`, `flood-data`, `pandemics-tracking`, `volcanic-eruptions`, `tropical-cyclones`.

## Quick findings

- **63 events catalogued**, dominated by 26 comets and 20 total solar eclipses; 8 supernovae and 4 Leonid meteor storms make up the long-tail rarities.
- **Halley's Comet returns** approximate the theoretical 75.3-year period (1066, 1145, 1222, 1301, 1378, 1456, 1531, 1607, 1682, 1759, 1835, 1910, 1986) — orbital mechanics predicts these centuries in advance.
- **Naked-eye galactic supernovae** are vanishingly rare: 8 events in 1,800+ years (SN 185, 393, 1006, 1054 Crab, 1181, 1572 Tycho, 1604 Kepler, 1987A). The **383-year gap between Kepler 1604 and SN 1987A** is the longest in the catalog; we're "overdue" for the next one by ~280 years on a per-galaxy rate.
- **Total solar eclipses occur ~24 times per century globally**, but only a small fraction make it into this catalog (those with major scientific impact or wide population visibility).
- **The 1833 Leonid meteor storm** ("the night the stars fell") deposited an estimated 100,000+ meteors per hour over North America; comparable events in 1866, 1966, 2001.

These events are listed primarily for cross-reference with the terrestrial-correlations work. Celestial mechanics is fully predictable, so any correlation with terrestrial events would have to be the terrestrial side responding to the celestial one, not vice versa.

See `plots/` for the four charts.

## What's in it

`eclipses.csv` — columns:

- `date` — ISO date for date-precise events; year-only for ancient supernovae
- `type` — `total_solar`, `lunar`, `comet`, `supernova`, `meteor_storm`, `solar_storm`
- `region_visible`
- `notes_significance` — historical context

Coverage:
- **Total solar eclipses 1502–2024** — selected high-impact events (totality crossing populated regions, historically significant observations like 1715 Halley, 1860 first photograph, 1919 Eddington, 2017/2024 Great American Eclipses)
- **Bright comets** — all Halley apparitions back to 1066, plus the great comets (1577, 1680, 1811, 1843, 1858, 1861, 1874, 1882, 1910, 1996 Hyakutake, 1997 Hale-Bopp, 2007 McNaught, 2020 NEOWISE)
- **Visible supernovae** — all naked-eye supernovae of recorded history (SN 185, 393, 1006, 1054 Crab, 1181, 1572 Tycho, 1604 Kepler, 1987A)
- **Leonid meteor storms** — historic November showers (1833, 1866, 1966, 2001)
- A few major solar storms (1859 Carrington, 1989 Quebec, 2003 Halloween) for cross-reference

## Plots

`make_plots.py` generates four standalone analytical plots:

### `plots/01_events_timeline.png`
Stacked event timeline by type (solar eclipses, lunar, comets, supernovae, meteor storms, solar storms) — visualizes the temporal density of each event class in the catalog.

### `plots/02_eclipses_per_decade.png`
Total solar eclipses per decade *in this catalog*. NB: this is selection-biased — only historically significant eclipses are listed, so the per-decade count reflects which were noted by chroniclers, not the true rate (~24 per century globally).

### `plots/03_comets_timeline.png`
Halley returns marked separately from "other great comets." Shows the regular Halley clock plus the irregular bright comets. Includes empirical Halley inter-return interval (mean ~75 yr).

### `plots/04_supernovae.png`
The 8 naked-eye supernovae of recorded history with year labels. Visualizes the 383-year SN 1604 → SN 1987A gap.

## Detection-bias notes

| Type | Detection cleanliness |
|---|---|
| Total solar eclipses | Cleanest: computable backwards/forwards for millennia by celestial mechanics |
| Naked-eye comets | Reasonably complete back to ~1500 in Eurasia; pre-1500 fragmentary outside East Asia |
| Visible supernovae | All naked-eye galactic SNe of the past 2000 years are catalogued, but galactic SN rate is so low (~1 per 100 yr) that "absence of more" isn't meaningful |
| Meteor storms | Only Leonid super-outbursts are well-documented; meteor showers in general are seen yearly |

## Reproducing the plots

```bash
python3 -m venv .venv
.venv/bin/pip install pandas numpy matplotlib
.venv/bin/python make_plots.py
```

## Source

- NASA Eclipse catalog — https://eclipse.gsfc.nasa.gov/
- Naked-eye comet list compiled from Kronk, *Cometography* (multi-volume)
- Supernova list from Stephenson & Green, *Historical Supernovae and Their Remnants* (2002)
- Leonid storm dates from McKinley, *Meteor Science and Engineering* (1961)

## Intended use

Data source for "signs in the heavens" correlation tests in [`Biblejustin/correlations`](https://github.com/Biblejustin/correlations). Expected to produce strong null results — the dates are essentially random with respect to terrestrial events.
