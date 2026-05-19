# astronomical-signs

Catalog of notable astronomical events: total solar/lunar eclipses, naked-eye comets, visible supernovae, and major meteor storms. Compiled to support the "signs in the heavens" branch of the correlation analysis (Mt 24:29 framing).

Parallel to `earthquakes`, `spaceweather`, `famines-tracking`, `flood-data`, `pandemics-tracking`, `volcanic-eruptions`, `tropical-cyclones`.

## What's in it

`eclipses.csv` — columns:

- `date` — ISO date for date-precise events; year-only for ancient supernovae
- `type` — `total_solar`, `lunar`, `comet`, `supernova`, `meteor_storm`, `solar_storm`
- `region_visible`
- `notes_significance` — historical context

Coverage:
- **Total solar eclipses 1500–present** — selected high-impact events (totality crossing populated regions, historically significant observations like 1715 Halley, 1860 first photograph, 1919 Eddington, 2017/2024 Great American Eclipses)
- **Bright comets** — all Halley apparitions back to 1066, plus the great comets (1577, 1680, 1811, 1843, 1858, 1861, 1874, 1882, 1910, 1996 Hyakutake, 1997 Hale-Bopp, 2007 McNaught, 2020 NEOWISE)
- **Visible supernovae** — all naked-eye supernovae of recorded history (SN 185, 393, 1006, 1054 Crab, 1181, 1572 Tycho, 1604 Kepler, 1987A)
- **Leonid meteor storms** — historic November showers (1833, 1866, 1966, 2001)
- A few major solar storms (1859 Carrington, 1989 Quebec, 2003 Halloween) for cross-reference

## Detection-bias notes

| Type | Detection cleanliness |
|---|---|
| Total solar eclipses | Cleanest: computable backwards/forwards for millennia by celestial mechanics |
| Naked-eye comets | Reasonably complete back to ~1500 in Eurasia; pre-1500 fragmentary outside East Asia |
| Visible supernovae | All naked-eye galactic SNe of the past 2000 years are catalogued, but galactic SN rate is so low (~1 per 100 yr) that "absence of more" isn't meaningful |
| Meteor storms | Only Leonid super-outbursts are well-documented; meteor showers in general are seen yearly |

## Source

- NASA Eclipse catalog — https://eclipse.gsfc.nasa.gov/
- Naked-eye comet list compiled from Kronk, *Cometography* (multi-volume)
- Supernova list from Stephenson & Green, *Historical Supernovae and Their Remnants* (2002)
- Leonid storm dates from McKinley, *Meteor Science and Engineering* (1961)

## Intended use

Data source for "signs in the heavens" correlation tests in [`Biblejustin/correlations`](https://github.com/Biblejustin/correlations). Expected to produce strong null results — the dates are essentially random with respect to terrestrial events.
