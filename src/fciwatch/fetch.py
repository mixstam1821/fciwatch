"""Download FCI and SEVIRI scans from the EUMETSAT Data Store with `eumdac`.

You need free Data Store credentials. Get them at https://api.eumetsat.int (the
"API key" page after you log in), then set two environment variables:

    EUMETSAT_CONSUMER_KEY
    EUMETSAT_CONSUMER_SECRET

Disk layout written by this module:

    <out>/fci/20260301T120000/   <- the unzipped NetCDF segment files of one FCI scan
    <out>/seviri/20260301T120000/ <- the unzipped .nat file of one SEVIRI scan

STATUS: this module has not been tested against the live Data Store yet.
The helper functions (snap_time / select_products) are covered by unit tests.
Collection ids can change, so check them in the Data Store catalogue and override
them with --fci-collection / --seviri-collection if needed.

DATA SIZE WARNING: one full-disk FCI scan is large (around a gigabyte or more).
Start with a short time window and a large --every-min.
"""

from __future__ import annotations

import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .pairing import format_scan_time, snap_time

log = logging.getLogger(__name__)

# FCI Level 1c, full disk, normal spatial resolution (the id used in EUMETSAT docs).
FCI_COLLECTION = "EO:EUM:DAT:0662"
# SEVIRI Level 1.5, 0 degree service, high-rate image data.
SEVIRI_COLLECTION = "EO:EUM:DAT:MSG:HRSEVIRI"


def get_datastore():
    """Log in to the Data Store using the two environment variables."""
    try:
        import eumdac
    except ImportError as err:  # pragma: no cover
        raise SystemExit("Missing dependency. Run:  pip install 'fciwatch[fetch]'") from err

    try:
        key = os.environ["EUMETSAT_CONSUMER_KEY"]
        secret = os.environ["EUMETSAT_CONSUMER_SECRET"]
    except KeyError as err:
        raise SystemExit(
            "Set EUMETSAT_CONSUMER_KEY and EUMETSAT_CONSUMER_SECRET (see fetch.py docstring)."
        ) from err
    return eumdac.DataStore(eumdac.AccessToken((key, secret)))


def select_products(products, every_min: int = 30):
    """Keep only products whose (rounded) start time is a multiple of `every_min` minutes.

    FCI and SEVIRI both have scans at :00 and :30, so the default of 30 gives matching
    pairs and keeps the download small.

    Returns a list of (nominal_time, product), sorted by time. Works with any object that
    has a `sensing_start` datetime attribute, which makes it easy to test.
    """
    chosen = []
    for p in products:
        nominal = snap_time(p.sensing_start, step_min=5)
        if (nominal.hour * 60 + nominal.minute) % every_min == 0:
            chosen.append((nominal, p))
    return sorted(chosen, key=lambda item: item[0])


def _download_one(product, scan_dir: Path) -> None:
    """Download one product, unzip it, and only then give the folder its final name."""
    tmp = scan_dir.with_name(scan_dir.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        with product.open() as src:
            target = tmp / Path(src.name).name
            with open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        if zipfile.is_zipfile(target):
            with zipfile.ZipFile(target) as zf:
                zf.extractall(tmp)
            target.unlink()
        tmp.rename(scan_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def fetch_collection(
    collection_id: str,
    kind: str,
    start: datetime,
    end: datetime,
    out_dir: Path,
    every_min: int = 30,
    dry_run: bool = False,
) -> int:
    """Download all matching scans of one collection. Returns the number of scans handled."""
    store = get_datastore()
    collection = store.get_collection(collection_id)
    products = list(collection.search(dtstart=start, dtend=end))
    chosen = select_products(products, every_min=every_min)
    log.info("%s: %d products found, %d selected", kind, len(products), len(chosen))

    count = 0
    for nominal, product in chosen:
        scan_dir = Path(out_dir) / kind / format_scan_time(nominal)
        if scan_dir.exists():
            log.info("skip (already there): %s", scan_dir)
            continue
        if dry_run:
            print(f"[dry run] would download {product} -> {scan_dir}")
        else:
            log.info("downloading %s -> %s", product, scan_dir)
            _download_one(product, scan_dir)
        count += 1
    return count
