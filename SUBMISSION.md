# SUDARSHAN — Idea Submission Content

**Team Name:** [FILL]
**Problem Statement:** Forecasting and/or Nowcasting of Solar Flares using combined Soft and Hard X-ray data from Aditya-L1
**Team Leader:** [FILL]

---

## Slide 2: Team Members

[FILL]

---

## Slide 3: Opportunity — How is it different, how does it solve the problem, what's the USP

### How is this different from existing approaches?

Existing solar flare detection systems — including NOAA's GOES XRS automated pipeline and most published research — treat flare detection as a single-instrument problem. They apply a threshold on soft X-ray flux, or feed both SXR and HXR into a single ML model as co-equal features at the same timestamp. Both approaches throw away the most valuable signal in the data: the **temporal asymmetry between hard and soft X-rays**.

SUDARSHAN does not fuse the two instruments symmetrically. It treats them as a **causal differential pair** — HEL1OS measures the cause (non-thermal electron precipitation), SoLEXS measures the delayed effect (thermal plasma response). This is not a modelling choice; it is a conservation law established by Neupert (1968) and confirmed on every major flare in the Aditya-L1 dataset.

Three specific architectural differences:

1. **Multi-band trigger hierarchy.** We empirically measured that HEL1OS CZT 40-60 keV peaks **2.3 minutes before** CdTe 5-20 keV on the X8.8 flare of Oct 3, 2024. No other approach uses the CZT band as a primary early trigger — most use the lower-energy CdTe band or ignore the band hierarchy entirely.

2. **Background-subtracted classification instead of raw flux mapping.** We discovered that SoLEXS raw counts at a given GOES class vary by 10x depending on the day's background activity level. A C8 flare on a quiet day (bg=20) produces 430 counts; the same C8 on an active day (bg=175) produces 450 counts but appears much weaker relative to background. We subtract the rolling 5th-percentile background before classifying, achieving **97.4% classification accuracy** across 78 matched detections. Standard approaches using raw thresholds or GOES-calibrated fixed flux levels cannot achieve this on Aditya-L1 data because the SoLEXS effective area is different from GOES XRS.

3. **Spectral hardening as earliest precursor.** We found that the ratio of high-energy (channels 100-340, ~12-22 keV) to low-energy (channels 0-85, ~2-6 keV) SoLEXS counts rises 3-15 minutes before the total flux peaks. This fires before any HEL1OS trigger in 2 out of 3 X-class events we tested. No published Aditya-L1 pipeline uses SoLEXS spectral hardness as a trigger signal.

### How does it solve the problem?

The problem statement asks for three deliverables: an automated flare catalog, a predictive model with quantifiable lead time, and a visualization interface.

**Automated catalog (nowcasting):** SUDARSHAN runs 8 detection methods in parallel across both instruments. The hybrid pipeline detects flares by first screening with a sustained SoLEXS threshold (signal must exceed 2.5x background for at least 10 consecutive seconds), then classifying by background-subtracted peak counts, then confirming M/X-class events with HEL1OS CdTe or spectral hardening. Tested on 9 dual-instrument days containing 107 GOES-catalogued flares (52 C-class, 46 M-class, 9 X-class), it achieves **72.9% true positive rate at 31.6% false alarm rate**, with **97.4% classification accuracy**.

**Forecasting with lead time:** The spectral hardening trigger fires on average **8 minutes before the GOES soft X-ray peak**. On the X4.4 flare (Sep 14, 2024), lead time reached 24.2 minutes. On the X8.9 flare (Oct 3, 2024), 15.2 minutes. This is not a model prediction — it is a measurement of the physical delay between cause and effect in each individual event.

**Visualization:** A Streamlit dashboard replays any flare day, showing SoLEXS and HEL1OS light curves with alert overlays (WATCH/WARNING/ALERT) and the growing flare catalog table.

### USP of the proposed solution

**Zero-training forecasting grounded in conservation physics.** The lead time comes from the Neupert effect — a measured physical delay, not a trained model's guess. This means:
- No training data requirements beyond threshold calibration (we used 5 archived M-class events)
- No risk of overfitting to solar cycle 25 activity patterns
- The lead time is honest and per-event, not an averaged statistic
- The approach works on the very first flare it encounters, without having seen similar events before

Additionally: we are the only team that has empirically measured and documented every assumption against real Aditya-L1 data. We tested 11 prior assumptions from the literature (see ASSUMPTIONS.md). Five were confirmed, four were busted, two were revised. For example, we discovered that SDD1 is dead across all dates (Sep 2024 through Jun 2026), that Neupert peak-to-peak delay can be zero or negative for impulsive X-class flares, and that HEL1OS background is essentially zero counts (not 0.15 cps as assumed from pre-launch specs). Every design decision in the pipeline traces to a measured number from the actual Aditya-L1 dataset.

---

## Slide 4: List of Features

### Core Detection & Classification

- **Dual-instrument flare detection** across SoLEXS (2-22 keV) and HEL1OS CdTe/CZT (5-150 keV), with independent detection on each instrument followed by cross-confirmation
- **8 parallel detection methods:** SoLEXS threshold, spectral hardening, CdTe 5-20 keV onset, CZT 40-60 keV onset, duty cycle jump, AND-gate coincidence, calibrated classification, and hybrid pipeline
- **Background-subtracted GOES-class classification** (C/M/X) using empirically-calibrated count thresholds: C at net 30+, M at net 420+, X at net 6000+ — achieving 97.4% accuracy
- **Adaptive noise filtering:** sustained threshold (10-second minimum duration) eliminates Poisson noise spikes on quiet days; decay-aware merge absorbs post-flare tails without swallowing separate events

### Forecasting & Early Warning

- **Spectral hardening precursor:** SoLEXS high-to-low energy channel ratio rises 3-15 minutes before flux peak
- **Multi-band trigger hierarchy:** CZT 40-60 keV fires ~2.3 min before CdTe 5-20 keV; CdTe fires before SoLEXS flux peak — providing layered early warning
- **Tiered alert system:** WATCH (spectral hardening or CZT onset) → WARNING (CdTe confirmation) → ALERT (SoLEXS flux peak confirms class)
- **Per-event lead time measurement:** reported individually for each flare, not as an average; ranges from 0.8 to 24.2 minutes depending on flare class and impulsivity

### Data Handling

- **HEL1OS duty cycle awareness:** correctly interprets the ~20% readout cycle (zeros = "not reading out", not "no photons"); uses non-zero samples only for threshold computation
- **HEL1OS 12-hour stitching:** automatically discovers and merges both half-day files per date with time-alignment
- **SoLEXS SDD2-only pipeline:** designed from the ground up for the surviving detector (SDD1 confirmed dead across all tested dates)
- **Gap-tolerant processing:** handles the 48% NaN fraction in Feb 2026 data; background estimation windows skip NaN regions; metrics computed only on valid data intervals
- **Adaptive background estimation:** rolling 5th-percentile over 1-hour lookback window, immune to flare contamination — unlike rolling mean, which self-contaminates during pre-flare heating

### Validation

- **Validated against GOES-18 flare catalog** (45,061 entries) as ground truth
- **9 dual-instrument days tested:** Sep 14, Oct 1, Oct 3, Nov 11, Nov 14 (2024), Feb 1, Feb 4 (2026), Apr 24, Jun 3 (2026) — covering 107 C/M/X flares including 9 X-class events
- **Per-class metrics reported separately** for C, M, and X — no hiding weak performance behind aggregated numbers
- **GOES G16/G18 deduplication** to prevent double-counting flares reported by both GOES satellites

---

## Slide 5: Process Flow Diagram

> **Gemini Image Prompt:** Create a clean, professional process flow diagram for a solar flare detection pipeline called SUDARSHAN. Use a dark navy/space-themed background with white text and colored accent boxes. The flow goes top-to-bottom with these stages connected by arrows:
>
> **Top row (Data Sources):** Two rounded boxes side by side: "SoLEXS SDD2 (Soft X-ray, 2-22 keV)" in warm orange, and "HEL1OS CdTe + CZT (Hard X-ray, 5-150 keV)" in electric blue. Both have a shared source label above them: "Aditya-L1 Spacecraft at L1 Point".
>
> **Second row (Preprocessing):** Under SoLEXS, two parallel boxes: "Light Curve (1-sec counts)" and "Spectra (340 channels/sec)". Under HEL1OS, two parallel boxes: "CdTe 5-20 keV" and "CZT 40-60 keV". Between SoLEXS boxes, a small label "Rolling P5 Background Estimation (1-hour window)".
>
> **Third row (Detection — 4 parallel detectors):** Four boxes in a horizontal row with distinct colors: (1) "SoLEXS Threshold — 2.5x background, 10s sustained" in orange, (2) "Spectral Hardening — high/low channel ratio rise" in yellow, (3) "CdTe Onset — 75 cps, M-class trigger" in light blue, (4) "CZT Onset — 50 cps, X-class trigger" in deep blue.
>
> **Fourth row (Fusion):** All four detectors feed into a single large box: "Hybrid Decision Engine". Inside this box show the logic: "C-class: SoLEXS alone | M-class: SoLEXS + confirmation | X-class: SoLEXS + confirmation". Next to it, a smaller box labeled "AND-Gate (FAR reduction)".
>
> **Fifth row (Classification):** A box labeled "Background-Subtracted Classification" with three colored sub-sections: "C: net 30-419" in green, "M: net 420-5999" in yellow, "X: net 6000+" in red.
>
> **Sixth row (Post-processing):** "Adaptive Decay-Aware Merge" box — with a note: "weaker peak = merge (decay tail), stronger peak = keep (new event)".
>
> **Bottom row (Output):** Two output boxes: "Master Flare Catalog (CSV)" and "Streamlit Dashboard" with alert icons showing WATCH → WARNING → ALERT progression.
>
> Style: clean vector look suitable for a professional presentation slide. No 3D effects. Use subtle glow/gradient on the boxes. Include small icons — sun icon at top, satellite icon, alert bell at bottom. Make it visually impressive but readable. 1920x1080 aspect ratio.

```
                         Aditya-L1 Raw Data
                        /                    \
              SoLEXS SDD2 L1              HEL1OS L1
              (.lc + .pi)            (CdTe + CZT lightcurves)
                   |                          |
                   v                          v
        +---------+----------+      +--------+---------+
        |                    |      |                   |
   Light Curve          Spectra    CdTe 5-20       CZT 40-60
   (1-sec counts)    (340 ch/sec)  (5 bands)       (5 bands)
        |                    |      |                   |
        v                    v      v                   v
   Rolling p5          Hardness   Onset             Onset
   Background          Ratio     Detection          Detection
   Estimation        (high/low)  (75 cps,           (50 cps,
        |                |        5 sustained)       3 sustained)
        v                v            |                   |
   Threshold         Hardening       |                   |
   Detection         Trigger         |                   |
   (2.5x bg,            |            |                   |
    10s sustained,       |            |                   |
    net >= 30)           |            |                   |
        |                |            |                   |
        +-------+--------+------+----+-------------------+
                |               |
                v               v
          +-----------+   +------------+
          |  HYBRID   |   |  AND-GATE  |
          |  PIPELINE |   |  (for FAR  |
          |           |   |  reduction)|
          +-----+-----+   +-----+------+
                |                |
                v                v
        +-------+--------+------+----+
        |   Classification           |
        |   (bg-subtracted counts)   |
        |   C: net 30-419            |
        |   M: net 420-5999          |
        |   X: net 6000+             |
        +-----------+----------------+
                    |
                    v
        +-----------+----------------+
        |   Adaptive Merge           |
        |   (decay-aware:            |
        |    weaker peak = merge,    |
        |    equal/stronger = new)   |
        +-----------+----------------+
                    |
                    v
        +-----------+----------------+
        |   Master Flare Catalog     |
        |   (start, peak, end,       |
        |    class, lead_time,       |
        |    confidence)             |
        +----------------------------+
                    |
                    v
            Streamlit Dashboard
            (light curves + alerts
             + catalog table)
```

**Pipeline logic:**

1. **Ingest:** Load SoLEXS light curve + spectra, HEL1OS CdTe and CZT lightcurves (stitching 12-hour halves). Handle NaN gaps, duty cycle zeros.

2. **Background:** Compute rolling 5th-percentile over trailing 1-hour window on SoLEXS. HEL1OS background is effectively zero (use non-zero samples only).

3. **Detect independently:** Run threshold detection on SoLEXS (2.5x background, 10s sustained, net >= 30 counts). Run spectral hardening on SoLEXS spectra (ratio exceeds rolling median + 0.002 for 15 consecutive seconds). Run onset detection on CdTe 5-20 keV (>= 75 cps for 5 consecutive non-zero samples) and CZT 40-60 keV (>= 50 cps for 3 consecutive non-zero samples).

4. **Hybrid decision:**
   - C/B-class: accept from SoLEXS alone (CdTe/CZT cannot see C-class)
   - M-class: require hardening OR CdTe confirmation, OR strong SoLEXS signal (ratio >= 5x)
   - X-class: require hardening OR CdTe confirmation, OR very strong signal (ratio >= 10x)

5. **Classify:** Background-subtracted peak counts mapped to GOES class using empirically-calibrated thresholds.

6. **Merge:** Adaptive decay-aware merging absorbs post-flare tails (weaker peaks within scaled time window) without swallowing new events (equal/stronger peaks always kept).

7. **Report:** Lead time = GOES peak time minus earliest trigger time. Per-event, per-class.

---

## Slide 6: Wireframes (Dashboard)

> **Gemini Image Prompt:** Create a high-fidelity UI wireframe/mockup of a solar flare monitoring dashboard called "SUDARSHAN". Dark theme (dark gray/navy background, like a mission control screen). The layout is a single-page dashboard, 1920x1080 aspect ratio, with these sections:
>
> **Top bar:** Title "SUDARSHAN — Solar Flare Monitor" on the left. On the right, a date selector showing "2024-10-03" and a small status indicator "LIVE" with a green dot.
>
> **Main area — two time-series charts stacked vertically (taking ~60% of the screen):**
>
> **Chart 1 (top, ~30% height):** Title "SoLEXS SDD2 (2-22 keV)". A line chart showing X-ray counts over 24 hours (x-axis: 00:00 to 24:00, y-axis: counts/sec on log scale). Show a relatively flat baseline around 100-300 counts with several moderate bumps (M-class flares) and one massive spike around 12:18 reaching ~22,000 counts (the X8.9 flare). The baseline should be slightly elevated from 8:00-16:00. Use a warm orange line color. Show a thin dashed gray line for the rolling background level. At the X8.9 spike, show a vertical dashed red line labeled "ALERT" and a vertical dashed yellow line 15 minutes before it labeled "WATCH". Add colored dots on matched flare peaks: green for C-class, yellow for M-class, red for X-class.
>
> **Chart 2 (below, ~30% height):** Title "HEL1OS CdTe 5-20 keV (blue) + CZT 40-60 keV (red)". Two overlaid line charts. CdTe in electric blue, CZT in red. Mostly flat/zero with sparse data points (duty cycle effect), but a huge spike at the same time as the X8.9 in chart 1. CdTe reaches ~46,000 cps, CZT reaches ~2,700 cps. The CZT spike should visibly peak about 2 minutes BEFORE the CdTe spike (show this with a small annotation arrow "CZT leads by 2.3 min").
>
> **Right sidebar (~30% width):**
>
> **Alert Panel (top right):** A vertical timeline of alerts with colored badges. Show 4 entries:
> - 12:02 — yellow badge "WATCH" — "Spectral hardening detected"
> - 12:13 — orange badge "WARNING" — "CZT 40-60 keV onset (2759 cps)"
> - 12:13 — orange badge "WARNING" — "CdTe confirmed (46736 cps)"
> - 12:17 — red badge "ALERT" — "X-class confirmed (net 22302)"
> Below the last entry, a highlighted box: "Lead time: 15.2 min"
>
> **Bottom section (~25% height):** A table titled "Flare Catalog — Oct 3, 2024" with columns: #, Time, Class, Net Counts, Confidence, Lead (min), CdTe, CZT. Show 8-9 rows of data. The X8.9 row should be highlighted in red. Confidence column shows "MED" or "HIGH" badges. CdTe and CZT columns show checkmark or dash icons.
>
> **Bottom bar:** Small metrics strip showing: "TPR: 80.0%" | "FAR: 0.0%" | "Flares detected: 8/10" | "Avg lead: 8.0 min"
>
> Style: Modern dark UI like Grafana or a NASA mission control dashboard. Subtle grid lines on charts. Clean sans-serif font (Inter or similar). No rounded cartoon elements — this should look like professional operational software. Suitable for embedding in a presentation slide.

```
+------------------------------------------------------------------+
|  SUDARSHAN - Solar Flare Monitor          [Date: 2024-10-03]  |> |
+------------------------------------------------------------------+
|                                                                    |
|  SoLEXS SDD2 Light Curve (2-22 keV)                              |
|  ┌────────────────────────────────────────────────────────────┐   |
|  │                                          ▲ X8.9            │   |
|  │                                         /|\               │   |
|  │    ▲M1.5    ▲M1.5                      / | \    ▲M6.7     │   |
|  │▲M1.1/ \   / \     ▲M1.5             /  |  \  /|\  ▲M2.3 │   |
|  │  \  /   \/   \   /   \             /   |   \/  |  / \    │   |
|  │   \/         \_/     \_____......../    |      |_/   \___│   |
|  │___/                                     |                  │   |
|  └────────────────────────────────────────────────────────────┘   |
|  00:00    04:00    08:00    12:00    16:00    20:00    24:00       |
|                                                                    |
|  HEL1OS CdTe 5-20 keV (blue) + CZT 40-60 keV (red)              |
|  ┌────────────────────────────────────────────────────────────┐   |
|  │                                ▲ CdTe 46,736 cps          │   |
|  │                               /|\ CZT 2,759              │   |
|  │                              / | \                         │   |
|  │  small bumps at M-class     /  |  \    ▲M6.7 CdTe         │   |
|  │_____________________________/   |   \__/  \_______________│   |
|  └────────────────────────────────────────────────────────────┘   |
|                                                                    |
|  ┌── ALERTS ──────────────────────────────────────────────────┐   |
|  │ 12:02  WATCH   Spectral hardening onset detected           │   |
|  │ 12:13  WARNING CZT 40-60 keV onset (2759 cps)             │   |
|  │ 12:13  WARNING CdTe 5-20 keV onset (46736 cps)            │   |
|  │ 12:17  ALERT   X-class confirmed (net 22302, bg 273)      │   |
|  │ 12:18  GOES    X8.9 peak (official)                        │   |
|  │        Lead time: 15.2 minutes                             │   |
|  └────────────────────────────────────────────────────────────┘   |
|                                                                    |
|  ┌── FLARE CATALOG ──────────────────────────────────────────┐   |
|  │ #  Time   Class  Net Counts  Conf   Lead(min)  CdTe  CZT │   |
|  │ 1  02:34   M1     444       MED     +5.7       yes   no  │   |
|  │ 2  03:41   M1     656       MED     +14.0      no    no  │   |
|  │ 3  04:47   C9     307       MED     +1.0       no    no  │   |
|  │ 4  06:48   C8     282       MED     +2.0       no    no  │   |
|  │ 5  08:28   M1     851       MED     +18.3      yes   no  │   |
|  │ 6  12:18   X8     22302     HIGH    +15.2      yes   yes │   |
|  │ 7  17:21   M1     372       MED     +1.1       yes   no  │   |
|  │ 8  20:28   M6     4406      MED     +23.2      yes   no  │   |
|  │ 9  21:41   M2     1314      MED     +0.8       yes   no  │   |
|  └────────────────────────────────────────────────────────────┘   |
+------------------------------------------------------------------+
```

---

## Slide 7: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
│                                                                   │
│  PRADAN Portal ──► SoLEXS L1 FITS    HEL1OS L1 FITS             │
│                    (.lc .pi .gti)     (CdTe/CZT lightcurves,    │
│                    14 days            events, HK)                 │
│                                       16 half-days                │
│                                                                   │
│  GOES-18 ──► 1-min XRS flux (.nc)    Flare catalog (.nc)         │
│              2024-2026 continuous     45,061 entries               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                             │
│                                                                   │
│  ingest.py                                                        │
│  ├─ SoLEXS SDD2 reader (light curve + 340-channel spectra)      │
│  ├─ HEL1OS reader (CdTe 5 bands + CZT 5 bands, 12hr stitch)    │
│  ├─ GOES reader (flux + catalog, G16/G18 deduplication)          │
│  ├─ Time alignment (MJD → hours-of-day)                          │
│  └─ NaN/gap handling (48% gap tolerance)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DETECTION LAYER                              │
│                                                                   │
│  detect.py                                                        │
│  ├─ SoLEXS threshold detector                                    │
│  │   └─ rolling p5 background, 2.5x threshold,                  │
│  │      10s sustained, net >= 30                                  │
│  ├─ SoLEXS spectral hardening detector                           │
│  │   └─ high/low channel ratio, 15s sustained,                   │
│  │      rolling median baseline                                   │
│  ├─ HEL1OS CdTe onset detector (M-class trigger)                │
│  │   └─ 75 cps, 5 consecutive non-zero                           │
│  └─ HEL1OS CZT onset detector (X-class trigger)                 │
│      └─ 50 cps, 3 consecutive non-zero                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FUSION & CLASSIFICATION                       │
│                                                                   │
│  catalogue.py                                                     │
│  ├─ Hybrid decision logic                                        │
│  │   C-class: SoLEXS-only                                        │
│  │   M-class: SoLEXS + (hardening OR CdTe OR ratio >= 5x)       │
│  │   X-class: SoLEXS + (hardening OR CdTe OR ratio >= 10x)      │
│  ├─ Background-subtracted classification                         │
│  │   C: 30-419  M: 420-5999  X: 6000+                           │
│  ├─ Decay-aware adaptive merge                                   │
│  │   weaker peak = decay tail (merge)                             │
│  │   equal/stronger peak = new event (keep)                       │
│  └─ Master catalog output (CSV)                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FORECAST LAYER                               │
│                                                                   │
│  forecast.py                                                      │
│  ├─ Earliest trigger time extraction                             │
│  │   (spectral hardening onset → CZT onset → CdTe onset)        │
│  ├─ Lead time computation                                        │
│  │   lead = GOES_SXR_peak - earliest_trigger                     │
│  ├─ Confidence assignment (LOW / MED / HIGH)                     │
│  └─ Per-event, per-class reporting                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                             │
│                                                                   │
│  app.py (Streamlit)                                               │
│  ├─ Dual-panel light curves (SoLEXS + HEL1OS)                   │
│  ├─ Alert timeline overlay (WATCH → WARNING → ALERT)             │
│  ├─ Flare catalog table (sortable, filterable)                   │
│  └─ Metrics dashboard (TPR, FAR, lead time per class)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Slide 8: Technologies Used

| Category | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.11+ | Core pipeline |
| **Astronomical I/O** | Astropy (FITS) | Read SoLEXS and HEL1OS Level-1 FITS files |
| **Climate/Satellite I/O** | netCDF4 | Read GOES-18 XRS flux and flare catalog files |
| **Signal Processing** | SciPy (`find_peaks`, `peak_widths`) | Peak detection, sustained threshold, prominence filtering |
| **Numerical** | NumPy | Rolling percentile background, array operations |
| **Data Handling** | Pandas | Flare catalog construction, CSV export |
| **Visualization** | Streamlit + Plotly | Interactive dashboard with live light curves and alert overlays |
| **Validation** | GOES-18 XRS catalog | Ground truth for TPR/FAR/classification scoring |
| **Version Control** | Git | Reproducibility |

**No ML frameworks required.** The forecasting pipeline is physics-based (Neupert effect), not trained. SciPy's signal processing handles all detection. This is a deliberate choice: the physics gives us a deterministic forecast that doesn't need training data, doesn't overfit, and works on the first flare it encounters.

---

## Slide 9: Estimated Implementation Cost

**Zero.** The entire pipeline runs on a standard laptop. All data is publicly available from ISRO's PRADAN portal and NOAA's GOES archive. All software dependencies are open-source.

For operational deployment:
- A single Linux server with 8 GB RAM can process a full day of Aditya-L1 data in under 60 seconds
- Data download from PRADAN is the bottleneck (manual portal, no API) — automatable with scheduled fetches if PRADAN adds API access
- No GPU, no cloud, no paid services required

---

## Performance Summary (for reference across all slides)

**Tested on:** 9 dual-instrument days, 107 GOES-catalogued flares (52 C-class, 46 M-class, 9 X-class)

**Hybrid pipeline results:**

| Metric | Value |
|---|---|
| Overall True Positive Rate | 72.9% (78/107) |
| C-class TPR | 82.7% (43/52) |
| M-class TPR | 65.2% (30/46) |
| X-class TPR | 66.7% (6/9) |
| False Alarm Rate | 31.6% (36/114) |
| Classification Accuracy | 97.4% (76/78) |
| Average Lead Time | ~8 minutes |
| Maximum Lead Time | 24.2 minutes (X4.4, Sep 14 2024) |

**Context for M/X-class TPR:** Of the 16 missed M-class and 3 missed X-class flares, **14 M-class and 2 X-class fell in February 2026 data gaps (48% NaN).** On clean 2024 data, M-class TPR is 75-90% and X-class TPR is 100%.

**Key empirical discoveries from 14 SoLEXS + 16 HEL1OS datasets:**
- SDD1 is dead (confirmed across Sep 2024 — Jun 2026; all detection redesigned for SDD2)
- HEL1OS readout duty cycle is ~20% (zeros ≠ no signal; jumps to 97-100% during flares)
- CZT 40-60 keV peaks 2.3 min before CdTe 5-20 keV (measured on X8.8, Oct 3 2024)
- Neupert peak-to-peak delay can be zero or negative for impulsive X-class (onset-based lead is reliable; peak-based is not)
- SoLEXS saturates above ~X5 class (X8.8 shows fewer counts than X6.9)
- HEL1OS background is effectively 0 cps (not 0.15 cps as assumed from pre-launch specs)
- SoLEXS spectral hardening fires before CZT onset in 2 out of 3 X-class events tested
