"""Turn one FCI scan folder + one SEVIRI scan folder into result records.

Steps for each scan pair:
  1. Read both scans with Satpy (brightness temperature for the thermal channels).
  2. Resample both onto the SAME regular lat/lon grid (nearest neighbour).
  3. Average into boxes and keep the quiet boxes (see boxes.py).
  4. Compute the statistics (see stats.py).

STATUS: step 1 and 2 need real data and have not been tested end-to-end yet. Steps 3 and
4 are pure numpy and are covered by unit tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .boxes import select_matching_boxes
from .channels import DEFAULT_PAIRS, ChannelPair, get_pairs
from .pairing import pair_scans, parse_scan_time
from .stats import compute_scan_stats

log = logging.getLogger(__name__)


@dataclass
class CompareConfig:
    # Region used for the comparison (degrees). The default covers the Mediterranean,
    # North Africa and southern/central Europe. Choose a region that both satellites
    # see at a similar angle.
    lat_min: float = 10.0
    lat_max: float = 50.0
    lon_min: float = -15.0
    lon_max: float = 25.0
    grid_deg: float = 0.02  # fine common grid, about 2 km
    box_factor: int = 10  # 10 x 10 grid cells per box, about 22 km
    max_std_k: float = 1.0  # a box is 'quiet' if its std is at most this
    min_valid_frac: float = 0.9
    tolerance_min: float = 5.0  # max time gap between FCI and SEVIRI scan
    pairs: tuple[str, ...] = field(default_factory=lambda: DEFAULT_PAIRS)


def _target_area(cfg: CompareConfig):
    from pyresample.geometry import AreaDefinition

    width = round((cfg.lon_max - cfg.lon_min) / cfg.grid_deg)
    height = round((cfg.lat_max - cfg.lat_min) / cfg.grid_deg)
    return AreaDefinition(
        "fciwatch_latlon",
        "fciwatch lat/lon grid",
        "fciwatch",
        {"proj": "longlat", "datum": "WGS84"},
        width,
        height,
        (cfg.lon_min, cfg.lat_min, cfg.lon_max, cfg.lat_max),
    )


def _load_on_grid(files: list[str], reader: str, names: list[str], area) -> dict[str, np.ndarray]:
    """Read the named channels and put them on `area`. Missing data becomes NaN."""
    from satpy import Scene

    scn = Scene(filenames=files, reader=reader)
    scn.load(names)  # thermal channels default to brightness temperature in kelvin
    on_grid = scn.resample(area, resampler="nearest", radius_of_influence=8000)
    return {n: np.asarray(on_grid[n].values, dtype=float) for n in names}


def process_scan_pair(fci_dir: Path, seviri_dir: Path, when, cfg: CompareConfig) -> list[dict]:
    """Return one record (a dict) per channel pair that gave a usable result."""
    pairs: list[ChannelPair] = get_pairs(cfg.pairs)
    area = _target_area(cfg)

    fci_files = sorted(str(p) for p in Path(fci_dir).rglob("*.nc"))
    sev_files = sorted(str(p) for p in Path(seviri_dir).rglob("*.nat"))
    if not fci_files or not sev_files:
        log.warning("No input files in %s or %s", fci_dir, seviri_dir)
        return []

    fci = _load_on_grid(fci_files, "fci_l1c_nc", [p.fci for p in pairs], area)
    sev = _load_on_grid(sev_files, "seviri_l1b_native", [p.seviri for p in pairs], area)

    records = []
    for p in pairs:
        f_box, s_box = select_matching_boxes(
            fci[p.fci], sev[p.seviri], cfg.box_factor, cfg.max_std_k, cfg.min_valid_frac
        )
        st = compute_scan_stats(f_box, s_box, ref_bt=p.ref_bt)
        if st is None:
            log.info("%s %s: too few good boxes, skipped", when, p.name)
            continue
        records.append(
            {
                "time": pd.Timestamp(when),
                "pair": p.name,
                "n": st.n,
                "bias_median": st.bias_median,
                "bias_ref": st.bias_ref,
                "slope": st.slope,
                "robust_sigma": st.robust_sigma,
                "bt_mean": st.bt_mean,
            }
        )
    return records


def _list_scans(root: Path):
    """Map scan time -> folder, for all folders named like 20260301T120000."""
    out = {}
    if not root.exists():
        return out
    for d in root.iterdir():
        if d.is_dir() and not d.name.endswith(".partial"):
            try:
                out[parse_scan_time(d.name)] = d
            except ValueError:
                log.debug("ignoring folder %s", d)
    return out


def compare_directory(data_dir: Path, results_csv: Path, cfg: CompareConfig) -> int:
    """Process every matching scan pair under `data_dir` and write/extend `results_csv`.

    If the CSV already exists, scan times that are already in it are skipped, so you
    can run this again after downloading more data. Returns the number of new records.
    """
    fci_scans = _list_scans(Path(data_dir) / "fci")
    sev_scans = _list_scans(Path(data_dir) / "seviri")
    matched = pair_scans(list(fci_scans), list(sev_scans), cfg.tolerance_min)
    log.info(
        "%d FCI scans, %d SEVIRI scans, %d matched", len(fci_scans), len(sev_scans), len(matched)
    )

    results_csv = Path(results_csv)
    existing = pd.read_csv(results_csv, parse_dates=["time"]) if results_csv.exists() else None
    done = set(existing["time"]) if existing is not None else set()

    new_rows: list[dict] = []
    for ft, st in matched:
        if pd.Timestamp(ft) in done:
            continue
        try:
            new_rows += process_scan_pair(fci_scans[ft], sev_scans[st], ft, cfg)
        except Exception:  # one broken scan should not stop a long run
            log.exception("failed for scan %s", ft)

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        out = new_df if existing is None else pd.concat([existing, new_df], ignore_index=True)
        out.sort_values(["pair", "time"]).to_csv(results_csv, index=False)
    return len(new_rows)
