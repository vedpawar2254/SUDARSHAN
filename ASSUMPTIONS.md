# Revised Assumptions — Based on Actual Aditya-L1 Data Analysis

> Analyzed 14 SoLEXS days + 16 HEL1OS half-days + GOES flare catalogs (45k+ flares).
> Every assumption below is either CONFIRMED, BUSTED, or REVISED with the actual numbers.

---

## A1. SDD1 is operational
- **PRIOR:** "SDD1 = 7.1 mm² large aperture for quiet/A-C class. Verify if operating."
- **STATUS: BUSTED**
- **EVIDENCE:** Zero GTI intervals, no light curve, no spectra across ALL 14 days tested (Sep 2024 — Jun 2026). SDD1 is dead or permanently off.
- **IMPACT:** Entire low-class detection pipeline must use SDD2 only. No dual-aperture stitching. SDD2 has 0.1065 mm² — 67x smaller collecting area than SDD1. Sub-A detection is harder. EMG/FRED matched filter on SDD1 is impossible — redesign around SDD2.

## A2. Neupert delay gives 2-10 min guaranteed lead time
- **PRIOR:** "HXR onset physically precedes SXR peak by ~1-10 min. Lead time is a measurement, not a model output."
- **STATUS: REVISED — overoptimistic for impulsive X-class**
- **EVIDENCE (peak-to-peak delays):**

| Flare | HXR peak | SXR peak | Delay |
|---|---|---|---|
| X4.4 (Sep 14) | 15:26:26 | 15:29:37 | **+3.2 min** (clean Neupert) |
| X6.9 (Oct 1) | 22:17:22 | 22:17:24 | **+0.03 min** (near-simultaneous) |
| X8.8 (Oct 3) | 12:17:43 | 12:17:03 | **-0.7 min** (SXR peaked first) |
| X1.0 (Jun 3) | 11:25:55 | 11:28:03 | **+2.1 min** |

- **REALITY:** Peak-to-peak Neupert delay ranges from **negative to +3 min** for X-class. Very impulsive flares can have near-zero or inverted delays. The "2-10 min guaranteed" claim is wrong for the strongest events.
- **IMPACT:** Don't sell lead time based on peak-to-peak Neupert delay alone. The real lead comes from **onset-to-peak** (HXR onset fires 6-13 min before GOES SXR peak) and from **class prediction via running integral** (you know it's going to be big before SXR finishes rising). Frame lead time as onset-based, not peak-based.

## A3. CdTe 5-20 keV is the best HXR trigger band
- **PRIOR:** "Use HEL1OS CdTe 8-70 keV as primary trigger."
- **STATUS: REVISED — higher energies are faster**
- **EVIDENCE (X8.8 flare, Oct 3 2024):**

| Band | Peak time | Peak cps |
|---|---|---|
| CZT 80-150 keV | **12:15:27** | 513 |
| CZT 40-60 keV | **12:15:25** | 2,759 |
| CdTe 40-60 keV | **12:15:21** | 86 |
| CdTe 20-30 keV | 12:17:43 | 2,077 |
| CdTe 5-20 keV | 12:17:43 | 46,736 |

- **REALITY:** The 40-150 keV bands peak **~2.5 minutes before** the 5-20 keV band. CZT (20-150 keV, 32 cm² area) gives earlier alerts than CdTe (8-70 keV, 0.5 cm²). The non-thermal emission at higher energies is genuinely faster.
- **IMPACT:** Use CZT 40+ keV as the **primary early trigger**, fall back to CdTe 5-20 keV for confirmation and for weaker flares where CZT counts are too low. This gives ~2 extra minutes of lead on top of whatever Neupert delay exists.

## A4. Symmetric HXR+SXR fusion is the "root error everyone else will make"
- **PRIOR:** "Most teams will fuse HXR+SXR symmetrically. This erases the causal lag."
- **STATUS: REVISED — overstated**
- **REALITY:** Any team that reads the problem statement and understands HXR precedes SXR will naturally preserve the lag. This is not a hidden trap — it's basic physics. The real competitive edges are elsewhere: data quality handling, threshold tuning, and honest evaluation.
- **IMPACT:** Don't frame the pitch around "everyone else will make this mistake." Focus on what we actually do better: multi-band trigger hierarchy, empirically-calibrated thresholds, honest per-class reporting.

## A5. HEL1OS is photon-starved below C6
- **PRIOR:** "HEL1OS CdTe SNR threshold is ~C6. Below that, HXR is useless."
- **STATUS: PARTIALLY CONFIRMED — but CdTe median is 0 even on active days**
- **EVIDENCE:** HEL1OS CdTe1 5-20 keV has median=0 cps on ALL days including active ones. The quiet-sun background is essentially zero. Even C-class events barely register (peak ~300 cps on quiet days like Nov 11). M-class events clearly visible (4000-5000 cps). X-class events produce 15,000-49,000 cps.
- **IMPACT:** The handoff threshold works, but it's not about "photon-starved" — it's about signal-to-noise. With zero background, even a few counts are significant. Consider using a count threshold rather than GOES-class threshold for the handoff.

## A6. Background estimation: rolling mean self-contaminates
- **PRIOR:** "Use 5th-10th percentile rolling quantile (60 min window). Rolling mean raises threshold during pre-flare."
- **STATUS: CONFIRMED**
- **EVIDENCE:** Oct 3 (X8.8 day) has p5=119, p50=348 — baseline is 10x higher than quiet days (p5~10-15) due to sustained active-region emission. Rolling mean would be pulled up by this persistent activity.
- **ADDITIONALLY:** The dynamic range varies enormously: quiet days = 8x, active days = 9-90x, extreme days = 45x. A fixed threshold is useless. Per-day adaptive baseline is mandatory.

## A7. 2026 SoLEXS has full coverage
- **PRIOR:** "100% duty cycle at L1."
- **STATUS: BUSTED for Feb 2026**
- **EVIDENCE:**

| Date | NaN fraction | GTI coverage |
|---|---|---|
| 2024 dates | 0-0.1% | ~100% |
| 2026-02-01 | **47.8%** | 51.3% |
| 2026-02-02 | **48.0%** | 51.1% |
| 2026-02-04 | **47.5%** | 50.2% |
| 2026-02-24 | 0% | 100% |
| 2026-04-24+ | 0% | 100% |

- **REALITY:** Feb 2026 has systematic ~50% data gaps. Likely an operational issue or SAA passage pattern. 2024 data is clean.
- **IMPACT:** Must handle gaps gracefully. Background estimation windows must skip NaN regions. Feb 2026 events are partial — rely more on 2024 events for validation. The X8.1 on Feb 1 at 23:57 UTC — we only have the 00:00-12:00 HEL1OS half, so the actual flare is **not in our HEL1OS data**.

## A8. The X8.1 (Feb 1, 2026) is our best demo event
- **PRIOR:** Not explicitly assumed, but we downloaded it as "highest priority."
- **STATUS: BUSTED**
- **EVIDENCE:** X8.1 peaked at 23:57 UTC. We have HEL1OS 00:00-12:00 only (the 12:00-23:59 half was not downloaded). SoLEXS has 48% NaN that day.
- **IMPACT:** Best demo events are the 2024 ones with clean data:
  - **X8.8 (Oct 3, 2024)** — both instruments, full coverage, spectacular signal
  - **X6.9 (Oct 1, 2024)** — both instruments, clean data
  - **X4.4 (Sep 14, 2024)** — cleanest Neupert delay (+3.2 min)

## A9. SoLEXS spectral data enables CHIANTI temperature fitting
- **PRIOR:** "CHIANTI isothermal fit on co-added PHA spectra for temperature-transition detection."
- **STATUS: CONFIRMED — spectra are rich**
- **EVIDENCE:** 340 energy channels per second. During flare, total spectral counts go from ~470 (quiet) to ~17,000-21,000 (peak/post-peak). High-energy channels (ch 83-139) show 5000-7000x enhancement — clear spectral hardening.
- **IMPACT:** Spectral analysis is viable. Co-adding 10-30 seconds should give enough counts for temperature fitting even at C-class.

## A10. HEL1OS data is daily like SoLEXS
- **PRIOR:** Implicitly assumed single daily files.
- **STATUS: BUSTED**
- **EVIDENCE:** HEL1OS L1 is delivered in **12-hour chunks**, not daily. Each half-day has separate zip files. File sizes vary enormously: quiet = ~40 MB, active = 200-540 MB.
- **IMPACT:** Must stitch 2 HEL1OS halves per day. Time alignment between halves needs care. File size is a quick proxy for activity level.

## A11. CZT/CdTe ratio is stable
- **PRIOR:** "CZT/CdTe ratio ~0.2-0.6 for typical flares."
- **STATUS: CONFIRMED with variation**
- **EVIDENCE:**

| Flare | CZT/CdTe ratio |
|---|---|
| X4.4 | 0.54 |
| X6.9 | 0.20 |
| X8.8 | 0.34 |
| X2.4 | 0.60 |
| X1.0 | 1.09 |

- **REALITY:** Ratio varies 0.20-1.09. Higher ratio = harder spectrum. This is physically meaningful (more non-thermal emission). But it's NOT stable enough for a fixed threshold — must be used as a relative indicator.

---

## Summary of Revised Pipeline Design

Based on these findings:

1. **SDD2-only pipeline** — no SDD1, no dual-aperture stitching
2. **CZT 40+ keV as primary trigger** — peaks 2-2.5 min before CdTe 5-20 keV
3. **CdTe 5-20 keV as secondary trigger** — higher count rate, confirms CZT
4. **Onset-to-GOES-peak lead time** — not peak-to-peak Neupert delay (which can be ~0)
5. **Running integral for class prediction** — the real forecasting value
6. **Adaptive per-day baseline** — rolling quantile, not fixed threshold
7. **Best demo events: Oct 3 (X8.8), Oct 1 (X6.9), Sep 14 (X4.4)** — all 2024, clean data
8. **Handle 50% data gaps** in 2026 gracefully
9. **Spectral hardening** as additional early indicator (high channels light up first)
10. **HEL1OS 12-hour stitching** required

---

*Generated from analysis of 14 SoLEXS + 16 HEL1OS datasets, cross-referenced with GOES-18 flare catalog (45,061 entries, 91 X-class). Date: 2026-06-30.*
