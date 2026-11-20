# fciwatch

**An independent, open check of MTG-FCI infrared calibration stability, using Meteosat SEVIRI as the reference.**

> Status: **v0.1 alpha**. The maths, drift detection and report are tested with synthetic data.
> The download and file-reading parts (EUMETSAT Data Store, Satpy) are written but **not yet tested
> on real data**. See [Status and honesty](#status-and-honesty) below.

fciwatch is not an official EUMETSAT tool and is not affiliated with EUMETSAT.

---

## The problem, in simple words

The Flexible Combined Imager (FCI) on Meteosat Third Generation (MTG-I1) is the new European
weather imager. In January 2024 EUMETSAT reported that FCI lost its on-board calibration sources.
EUMETSAT corrects for this with its own methods (for example, by comparing FCI with the IASI
sounder). That work is good, but it happens inside EUMETSAT. Outside users cannot easily repeat
it or check it for themselves.

This matters for anyone who uses FCI brightness temperatures over time: climate data records,
cloud and surface products, nowcasting, machine-learning models. A slow drift of a few tenths of
a kelvin can be a big problem for a climate record.

Meteosat SEVIRI (the older imager) has a stable on-board calibration and a very long record. For
a while both instruments fly side by side. So we can ask a simple question:

> **Does FCI minus SEVIRI stay constant over time, or does it slowly change?**

If it changes, then most likely FCI is drifting. fciwatch answers this question in a way that
anybody can run and repeat, and it writes a simple HTML report.

## What it does

1. **fetch**: downloads matching FCI and SEVIRI full-disk scans from the EUMETSAT Data Store.
2. **compare**: puts both on the same lat/lon grid, averages into boxes, keeps only "quiet"
   boxes (no cloud edges), and measures `FCI - SEVIRI` for each scan.
3. **report**: turns many scans into a daily drift chart and a summary table (`OK` / `CHECK`).

```
 Data Store ──fetch──▶ data/fci/<time>/   data/seviri/<time>/
                              │                    │
                              └──────compare───────┘
                                       │
                                  results.csv  ──report──▶  report.html
```

## Install

```bash
git clone https://github.com/mixstam1821/fciwatch.git
cd fciwatch
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # core only: numpy + pandas (enough for the demo and reports)
pip install -e ".[fetch,read]"   # add downloading (eumdac) and file reading (satpy)
```

Python 3.10 or newer.

## Try it in one minute (no account, no downloads)

```bash
fciwatch demo --out demo.html
```

This builds a report from **synthetic** data. One channel is healthy, one has a slow drift, one has
a sudden step. The report says clearly that the data is fake.

## Use it on real data

1. Get free Data Store credentials at <https://api.eumetsat.int> and set:

   ```bash
   export EUMETSAT_CONSUMER_KEY=...
   export EUMETSAT_CONSUMER_SECRET=...
   ```

2. Look at what would be downloaded first. **FCI scans are big** (about a gigabyte or more each),
   so start small:

   ```bash
   fciwatch fetch --start 2026-03-01 --end 2026-03-03 --out data --dry-run
   fciwatch fetch --start 2026-03-01 --end 2026-03-03 --out data
   ```

3. Compare, then make the report:

   ```bash
   fciwatch compare --data data --out results.csv
   fciwatch report results.csv --out report.html
   ```

   `compare` can be run again after you download more. It skips scans that are already in the CSV.

4. Open `report.html` in a browser.

### How to read the report

* **Drift** is `(bias today) - (bias in the baseline period)`. The baseline is the first 14 days by
  default (`--baseline-days`, or `--baseline-start/--baseline-end`).
* Drift near zero means "FCI relative to SEVIRI is the same as in the baseline period".
  It does **not** mean "perfectly calibrated".
* The dashed lines are your alert level (`--threshold`, default 0.3 K). It is a number you choose.
  It is **not** an official EUMETSAT requirement.
* Channel pairs differ a little in wavelength (for example 10.5 um vs 10.8 um), so
  `FCI - SEVIRI` is not expected to be zero. Only the change over time matters.

## Status and honesty

| Part | State |
|---|---|
| Box averaging, quiet-box filter, bias maths, drift, summary, report | Written and covered by unit tests (synthetic data) |
| EUMETSAT Data Store download (`fetch`) | Written, **not tested on the live service**. Collection ids may need a check |
| Reading files with Satpy and regridding (`compare`) | Written, **not tested on real FCI/SEVIRI files** |
| Science validation (does it reproduce known FCI behaviour?) | **Not done yet** |

If you try it on real data and something breaks, please open an issue. That is the most useful
contribution right now.

Known limits (details in [docs/METHOD.md](docs/METHOD.md)):

* It measures **relative drift**, not absolute accuracy.
* SEVIRI is the reference, so SEVIRI's own small changes would show up as FCI drift.
* Different spectral bands, viewing angles and scan times add scatter and scene-dependent
  differences. fciwatch reduces this with box averaging, a quiet-box filter and a fixed reference
  scene temperature, but it cannot remove it fully.
* SEVIRI 0-degree service is planned to continue at least to the end of 2026 according to EUMETSAT
  material. Check the current status and what the Data Store archive holds before you plan a study.

## Roadmap

* Test on real data and publish a worked example with a real period.
* Add **IASI** (Metop) as a second, independent reference.
* Optional spectral correction (GSICS-style) instead of only a fixed reference temperature.
* Use the EUMETSAT Data Tailor to cut a small region, so downloads become much smaller.
* Cache the boxed results in a compact format.
* Daily automatic run with a published report.

## Project layout

```
src/fciwatch/
  channels.py   which FCI channel pairs with which SEVIRI channel
  pairing.py    match FCI and SEVIRI scans in time
  boxes.py      box averaging and the quiet-box filter
  stats.py      bias, slope, spread for one scan
  drift.py      daily drift, baseline, summary
  report.py     self-contained HTML report (Apache ECharts)
  fetch.py      Data Store download (eumdac)
  pipeline.py   Satpy reading + regridding + the loop over scans
  synthetic.py  fake data for demo and tests
  cli.py        the `fciwatch` command
tests/          pytest tests
docs/METHOD.md  the method and its limits
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Data and credits

* FCI and SEVIRI data come from EUMETSAT. Read the EUMETSAT data policy for the rules on use and
  attribution before you publish results.
* Built on [Satpy](https://satpy.org), [pyresample](https://pyresample.readthedocs.io),
  [eumdac](https://gitlab.eumetsat.int/eumetlab/data-services/eumdac), numpy, pandas and
  [Apache ECharts](https://echarts.apache.org).

## Licence

MIT. See [LICENSE](LICENSE).
