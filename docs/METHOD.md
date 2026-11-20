# Method

This file explains what fciwatch computes, why, and where it can go wrong.

## 1. Idea

SEVIRI has an on-board calibration that works. FCI (on MTG-I1) has lost its on-board calibration
sources, so its calibration is kept in line by other methods. If we compare the two instruments
over the same scenes, again and again, any slow change of `FCI - SEVIRI` is a sign that one of
them is drifting. SEVIRI is the reference, so we blame FCI.

The quantity we track is, in kelvin:

```
bias = BT_FCI - BT_SEVIRI
```

## 2. Channel pairs (`channels.py`)

| Pair name | FCI | SEVIRI | Spectral shift |
|---|---|---|---|
| ir105_ir108 | ir_105 (10.5 um) | IR_108 (10.8 um) | -0.3 um |
| ir123_ir120 | ir_123 (12.3 um) | IR_120 (12.0 um) | +0.3 um |
| ir133_ir134 | ir_133 (13.3 um) | IR_134 (13.4 um) | -0.1 um |
| ir87_ir87, ir97_ir97 | ir_87, ir_97 | IR_087, IR_097 | about 0 |
| wv63_wv62, wv73_wv73 | wv_63, wv_73 | WV_062, WV_073 | small |

Wavelengths are rounded nominal centres. The 3.8 um channel is not used, because in the daytime
it contains reflected sunlight.

Because the spectral bands differ, `bias` is not zero even for two perfect instruments, and its
size depends on the scene (for example, humidity and temperature profile). This is the main reason
we study the **change** of the bias, not its absolute value.

## 3. Steps for one scan pair

1. **Time matching** (`pairing.py`). FCI scans every 10 min, SEVIRI every 15 min. Common times are
   :00 and :30. A pair is accepted when the nominal times differ by at most 5 min (default).
2. **Common grid** (`pipeline.py`). Both scans are read with Satpy as brightness temperature and
   resampled (nearest neighbour) to a regular lat/lon grid of 0.02 degrees.
3. **Boxes** (`boxes.py`). The grid is cut into boxes of 10 x 10 cells (about 22 km). Each box
   becomes one mean value per instrument. This removes most of the noise from pixel size,
   navigation and viewing angle differences.
4. **Quiet boxes only** (`boxes.py`). A box is kept only if at least 90 % of its cells are valid
   and the standard deviation inside the box is at most 1 K in both images. This removes cloud
   edges, where small geometry differences create big differences in the mean.
5. **Statistics** (`stats.py`).
   * `diff = FCI_box - SEVIRI_box` for every kept box.
   * Remove boxes more than 3 robust sigmas from the median (robust sigma = 1.4826 x MAD).
   * Fit `diff = a + b * (SEVIRI_BT - T_ref)`. We report `a` as **`bias_ref`**, the bias at a fixed
     reference scene temperature `T_ref`, and `b` as the **slope**.
   * If the scene temperature range (5th to 95th percentile) is smaller than 10 K, there is
     no fit, and `bias_ref` is the median.

   Why the fit? A winter night and a summer afternoon contain different scene temperatures. If
   the bias depends on scene temperature, the plain median would move with the season even
   with a perfect instrument. `bias_ref` compares all scenes at the same temperature.

## 4. From scans to drift (`drift.py`)

* Take the daily median of `bias_ref` per channel pair.
* The **baseline** is the median of the daily values in a chosen period (default: the first
  14 days).
* `drift = daily value - baseline`.
* A pair is marked `CHECK` when the median drift of the last 7 days is larger than the alert level
  (default 0.3 K, chosen by the user).

## 5. Limits you should know

* **Relative only.** If FCI was already off in the baseline period, this method does not see it.
* **SEVIRI is assumed stable.** Its own changes would appear as FCI drift. Using IASI as a second
  reference (roadmap) is the way to separate the two.
* **Spectral differences** remain. A fixed reference temperature handles the first-order effect
  only. A proper spectral correction is on the roadmap.
* **Parallax and geometry.** If the two satellites are at different longitudes, high clouds look
  shifted. The quiet-box filter reduces this, but a region near the sub-satellite point is safer.
  Check the orbital slots of the two satellites for your period.
* **Scan time.** The two instruments scan the disk in different ways, so the same location is
  seen at slightly different moments. Quiet boxes reduce the effect.
* **Sampling.** Only boxes that pass the quiet filter are used. This favours clear sky and
  uniform cloud decks.
* **Not validated yet.** The method has been tested on synthetic data only. Running it on real data
  and comparing with known FCI behaviour is the next step.
