# ISRO Aditya-L1 Solar Flare Hackathon — Winning Plan (v2, audited)

> **Problem:** Nowcast + forecast solar flares from combined **SoLEXS** (soft X-ray) + **HEL1OS** (hard X-ray) on Aditya-L1.
> **Judged on:** (1) detection of **low AND high** class flares, (2) **high TPR + low false-alarm**, (3) **lead time** (minutes before flare *peak*).
>
> Built from 3 multi-agent workflows: recon (18 agents) → genius gauntlet (100 agents) → **20-agent correctness audit**. Every fact below is either ✅ verified against a real paper or ⚠️ flagged unverified. Read `UNDERSTANDING.md` for the *why*; this is the *how*. Paired arXiv IDs are real and audit-confirmed — cite them.

---

## 0. Winning Thesis (physics-first)

**Don't predict flares — measure the causal chain between the two payloads.** HEL1OS sees the *cause* (instantaneous electron energy deposition), SoLEXS sees the *effect* (time-integrated thermal plasma). HXR onset precedes the SXR peak by minutes — **that onset-to-peak gap is the lead time.** Build a **bifurcated, strictly-sequential** pipeline (SoLEXS SDD2-spectral for low-class; HEL1OS CZT+CdTe multi-band for high-class), prove it live with a **split-screen counterfactual demo** on real Oct 2024 events, and back every number with **chronologically-validated, per-class metrics**.

The differentiator is **rigor + real dual-payload physics + empirically-calibrated thresholds on actual Aditya-L1 data**, not a model. The multi-band trigger hierarchy (CZT 40+ keV fires ~2.5 min before CdTe 5-20 keV) is a measurable advantage no SXR-only pipeline can match.

> **Revised from data:** Peak-to-peak Neupert delay can be near-zero for impulsive X-class (measured: X6.9=+0.03min, X8.8=-0.7min). Real lead comes from onset-based timing (6-13 min measured) + class prediction via running integral. SDD1 is dead — entire pipeline uses SDD2 only. See `ASSUMPTIONS.md`.

---

## 1. Know Your Judges

- **Format:** 2-stage — ideation PDF gate (~140 teams) → **30 teams, ~30-hour offline Grand Finale**, judged by **active ISRO solar physicists**.
- They reward, in order: (1) **runs on real Aditya-L1 data**, (2) **detects low-class flares GOES misses**, (3) **defensible lead-time numbers + correct methodology**, (4) **you can explain the physics of every choice**.
- They *will* ask: "Which aperture?" "How did you split train/test?" "What's your Neupert conformance rate?" "Is that TSS or TPR−FAR?" Have the answers.

---

## 2. Verified Instrument Facts (corrected — use these exact numbers)

**SoLEXS — soft X-ray (thermal plasma)** ✅ arXiv:2509.26292 (Solar Physics, DOI 10.1007/s11207-025-02494-0):
- Energy **2–22 keV**; resolution **~170 eV @ 5.9 keV** (164.9–171.2).
- **1 s spectra** cadence ✅. (0.1 s temporal light curve ⚠️ unverified — confirm in SoLEXS_Tools manual.)
- **Dual aperture:** SDD1 = **7.1063 mm²** (quiet/A–C), SDD2 = **0.1065 mm²** (M–X). SDD1 saturates **>~1×10⁵ cps**.
- **SDD1 STATUS: DEAD.** Zero GTI intervals, no light curve, no spectra across ALL 14 tested days (Sep 2024 — Jun 2026). **Pipeline must use SDD2 only.** No dual-aperture stitching possible.
- **Two processing chains with different deadtimes** (critical): **timing chain = 1.6 µs** (used for *light curves* — flare detection), **spectral chain = 13.65 µs** (used for *PHA spectra* — T/EM).
- **Coverage:** 2024 data has ~100% coverage. Feb 2026 has systematic ~50% NaN gaps (47-48%). Use 2024 events for primary validation.

**HEL1OS — hard X-ray (non-thermal electrons)** ✅ arXiv:2512.12679 (Solar Physics, DOI 10.1007/s11207-025-02543-8):
- **CdTe 8–70 keV / 0.5 cm²**; **CZT 20–150 keV / 32 cm²** (CZT has **64× the area** — use it for the hard band).
- Statistically-significant spectra **C6–X3**; benign particle background at L1. **1 s light curves** ✅. **10 ms event-list + 20 s PHA cadence confirmed** from user manual.
- **5 energy bands per CdTe detector:** 5-20, 20-30, 30-40, 40-60, 1.8-90 keV. **5 bands per CZT:** 20-40, 40-60, 60-80, 80-150, 18-160 keV.
- **DATA FINDING: Higher energy bands peak EARLIER.** On X8.8: CZT 40-60 keV peaked at 12:15:25, CdTe 5-20 keV peaked at 12:17:43 — **2.3 min advantage from harder bands.** Use CZT 40+ keV as primary trigger.
- **DATA FINDING: Quiet-sun background is ~0 cps** (not 0.15 cps as theorized). Even a few sustained counts are statistically significant.
- **DATA FINDING: 12-hour data chunks**, not daily. Must stitch halves. File size correlates with activity (40 MB quiet, 200-500 MB flare).
- Columns: `MJD`, `ISOT`, `CTR` (count rate), `STAT_ERR`.

**Combined 2–150 keV continuously — no prior Indian solar instrument did this. That span is the core novelty.**

---

## 3. Problem Reframed

### The Neupert mechanism (honestly)
`dSXR/dt ∝ HXR(t)` → the HXR peak precedes the SXR peak. ✅ arXiv:2404.02653 (ASO-S, 149 flares): 82.5% show corr ≥0.95.
**⚠️ NOT "physics-guaranteed":** the timing relation holds in **~50–80% of M/X flares** (Veronig 2002 finds ~50%; ~25% inconsistent). **Flag each event `neupert_conformant` (|corr(∫HXR, SXR)|>0.90) and report the conformance fraction as a result.** Gradual/conduction-dominated flares deviate.

### Flare timeline (three distinct lead-time mechanisms)
| Stage | Observable | Instrument | Lead vs SXR peak |
|---|---|---|---|
| **HOPE** thermal precursor | T rises to **10–15 MK**, EM rising, no HXR | SoLEXS spectral fit | **C5–M1: 3.46±2.26 / M1–X1: 5.39±3.86 / X1+: 9.38±4.49 min** ✅ arXiv:2509.05234 |
| **CZT 40+ keV onset** | Non-thermal hard X-rays | HEL1OS CZT | **~2.5 min before CdTe 5-20 keV peak** (measured on X8.8) |
| **HXR onset** (5σ above baseline) | Non-thermal bremsstrahlung | HEL1OS CdTe | **6–13 min before GOES SXR peak** (measured onset-to-peak) |
| **HXR peak** (Neupert timing gap) | Peak non-thermal emission | HEL1OS | **~0–3 min before SXR peak** (REVISED: can be near-zero for impulsive X-class) |
| **SXR peak** | Thermal max → defines GOES class | SoLEXS | t = 0 (scored endpoint) |

> **DATA REVISION:** Prior assumption of "~1-3 min (M), ~3-5 min (X)" peak-to-peak delay is WRONG for impulsive events. Measured: X6.9=+0.03min, X8.8=-0.7min. Real lead comes from onset-to-peak timing + CZT multi-band advantage.

### Honest per-class lead-time caveat (say this — it builds credibility)
- **X/M-class:** HOPE 5–10 min + Neupert 1–5 min → real, defensible multi-minute lead.
- **C5:** HOPE lead 3.46±2.26 min ✅. **C1–C4:** HOPE may be below SoLEXS fit threshold → seconds–2 min. **<C1:** undetectable precursor → lead ≈ 0, it's a *nowcast*.
- **Anchor correctly:** alarm = HXR/HOPE onset; target = **GOES SXR peak**, *not* GOES catalogue onset (which lags true onset 2–10 min). This definitional fix alone buys minutes of *real* lead.

### Three physically-separate sub-problems (the bifurcation is the game)
1. **Detect A/B/C GOES misses** → SoLEXS SDD2 T(t)/EM(t) spectral fit (SDD1 dead; HEL1OS photon-starved below ~C6).
2. **Forecast M/X with max lead** → HEL1OS CZT 40+ keV primary trigger (fires ~2.5 min before CdTe) + CdTe confirmation + Neupert residual + `∫HXR dt` class forecast.
3. **Suppress false alarms** → physics AND-gate coincidence.
**Handoff at ~C6.** HEL1OS background is ~0 cps; C-class gives ~300 cps, M-class 4000+ cps.

---

## 4. System Architecture — 4-Layer Sequential Pipeline (never symmetric fusion)

```
ingest.py        SoLEXS SDD2 + HEL1OS FITS readers; 12-hour HEL1OS stitching;
                 deadtime (1.6µs timing / 13.65µs spectral); NaN/gap handling;
                 UTC align; MJD→datetime for HEL1OS, unix→datetime for SoLEXS
lightcurve.py    SoLEXS SDD2 total counts; HEL1OS CdTe 5 bands + CZT 5 bands;
                 background = rolling 5th–10th percentile (≥60min, skip NaN) — NOT rolling mean
nowcast_soft.py  EMG/FRED peak fit on SDD2; single-band for sub-A/A, dual-band only C+
nowcast_hard.py  Multi-band trigger: CZT 40+ keV primary (earliest), CdTe 5-20 keV secondary;
                 SEP veto (CZT 80-150/20-40 ratio)
catalogue_merge.py  master catalogue + AND-gate FAR suppression; source_channel ∈ {soft,hard,both}
hope_precursor.py   CHIANTI isothermal T/EM on 10–30s co-added SDD2 spectra (340 ch) → WATCH
neupert_residual.py r(t)=HEL1OS_CdTe − α·dSXR/dt; CUSUM → trigger; ∫HXR dt → class forecast
evaluate.py      TSS=TPR−FPR, per-class, bootstrap 95% CI, per-class survival curves
ui/app.py        split-screen counterfactual replay on Oct 2024 events
```

**Layer 0 — Multi-band trigger + Neupert residual (zero training):**
- **Primary: CZT 40+ keV CUSUM** — fires ~2.5 min before CdTe 5-20 keV (measured). Zero background = any sustained counts significant.
- **Secondary: CdTe 5-20 keV CUSUM** — higher count rate, confirms CZT, handles weaker flares.
- Neupert residual: fit `α` on archived M flares. `r(t)=HEL1OS(t)−α·(SoLEXS(t)−SoLEXS(t−1))`; CUSUM `k=0.5σ_quiet`, `h=3σ`, 5 consecutive. `∫HXR dt` → calibrated C/M/X class thresholds.
**Layer 1 — HOPE (SoLEXS SDD2 only):** CHIANTI isothermal fit on **10–30 s co-added** SDD2 spectra (340 channels, quiet=~470 total counts/s, flare=17000+). WATCH when T>8 MK while EM at background, ≥3 bins.
**Layer 2 — bifurcated nowcast:** low-class → EMG bank on **SDD2** (SDD1 dead); high-class (C6+) → HEL1OS multi-band CUSUM + integrator + SDD2.
**Layer 3 — AND-gate + tiered alerts:** WATCH→WARNING(+HEL1OS ±30s ≥2σ)→ALERT(+SoLEXS concordance); K-of-N vote + 30-min refractory.

---

## 5. Data Strategy & De-risking

**Primary:** PRADAN `pradan1.issdc.gov.in/al1/` — SoLEXS L1 + HEL1OS L1, **FITS**, **public from July 2024** (releases Jan 6 + Feb 14 2025).
- ⚠️ **Registration is a mandatory 2-step process for ALL users: signup+email-verify THEN manual admin approval** (not instant). **Register ≥48 h before**; email **issdc@istrac.gov.in** right after verifying. **Do not assume access until confirmed** — build on analogs meanwhile.
- SoLEXS_Tools calibration package: `/al1/protected/downloadFile/solexs/solexs_tools-1.1.tar.gz` (free login). **Don't roll your own SoLEXS calibration.**

**Parallel analog track (start minute 1, never blocked):**
- **GOES XRS** via SunPy Fido — zero-friction, 1 s, soft-X-ray proxy **+ ground-truth labels**. Build the whole pipeline here first.
- **Chandrayaan-2 XSM** ✅ arXiv:2312.09191 — 6,266-flare catalogue, same SDD tech, primary soft-X-ray training set (XSMDAS; ⚠️ verify Python version, likely separate env).
- **Fermi GBM / Solar Orbiter STIX** — HEL1OS hard-X-ray analog during dev.
- **AL1SC** `al1ssc.aries.res.in` — fast inspection; **Kaggle SoLEXS samples** + ISRO-ESA-Heliophysics-Workshop notebooks — offline bootstrap.

**Demo events (confirmed, data downloaded and verified):**
- **X8.8 (Oct 3, 2024)** — best event. Both instruments, full coverage, 46,736 cps CdTe peak. HXR peak at 12:17:43, SXR peak at 12:17:03.
- **X6.9 (Oct 1, 2024)** — clean data, 40,069 cps CdTe peak. Near-simultaneous HXR/SXR peaks (demonstrates impulsive case).
- **X4.4 (Sep 14, 2024)** — cleanest Neupert delay: HXR peak 3.2 min before SXR peak (demonstrates the physics best).
- **X2.4 (Apr 24, 2026)** — recent event, good coverage.
- ⚠️ **X8.1 (Feb 1, 2026) is NOT usable** — flare at 23:57 UTC but we only have HEL1OS 00:00-12:00 half. SoLEXS has 48% NaN.

**Ground-truth & cross-cal:** GOES/SWPC event list = labels. ⚠️ SoLEXS→GOES linear cross-cal valid only **2×10⁻⁶–1×10⁻⁴ W/m² (~C2–X1)** and is against **GOES XRS-A (0.5–4 Å)**, while class is defined in **XRS-B (1–8 Å)** — convert XRS-A→XRS-B via the CHIANTI fit. **Below C2, report SoLEXS native flux; class is extrapolated** (use XSM sub-C convention). ⚠️ GOES-8/15 underestimate flux 1.43× pre-2016 (not GOES-R 2017+) — SoLEXS spectral fits are *more accurate* labels at the tails (a provable claim).

---

## 6. Nowcasting Detail

- **Background:** rolling **5th–10th percentile** quantile (≥60 min) — immune to pre-flare contamination; rolling *mean* raises the threshold exactly when it should be lowest.
- **XSM-actual detection method** ✅ arXiv:2312.09191 (cite it correctly): 120 s mean-binning → Gaussian smoothing (σ_G=2) → dynamic threshold τ_FG=0.3·σ_BG → `scipy.signal.find_peaks` topographic prominence → **EMG (Elementary Flare Profile)** fit for start/peak/end → decompose overlaps. Analysis band 1.55–12.4 keV. **89.64% completeness for B1.0+ vs GOES.**
- ⚠️ **Sub-A/A: single-band (2–6 keV)** detection — 5–8 MK plasma emits negligibly >6 keV, so dual-band would reject them. **Dual-band concordance only for C-class+.**
- **No dual-aperture stitching:** SDD1 is dead. SDD2-only pipeline. SDD2 quiet-day baseline: median=15-25 cps. Active-day baseline: median=100-1000 cps. Dynamic range 8x (quiet) to 280x (flare day).
- **Catalogue merge:** ±2 min association, `source_channel` flag.

**The honest XSM claim (corrected):** XSM found **213 sub-A events genuinely below GOES sensitivity** (real new detections) + 1,330 A-class in its catalogue. ⚠️ Do **NOT** say "GOES missed 1,330 A-class" — with the same algorithm GOES-17 finds 1,851 A-class (*more*). Only the **213 sub-A** is a defensible "GOES can't see this" claim.

---

## 7. Forecasting Detail

- **Two forecasters, cross-validating:** (a) physics — Neupert residual CUSUM + `∫HXR dt`; (b) HOPE thermal precursor. Report both.
- **HOPE thresholds:** start from ΔT>5 MK, **ΔEM > 5×10⁻³ × 10⁴⁹ cm⁻³ (= 5×10⁴⁶ cm⁻³)** — ⚠️ these are GOES-broadband-ratio-specific; **recalibrate empirically on SoLEXS spectral-fit outputs (this is mandatory, in the core timeline, not stretch).**
- **Stage-2 hardness trigger:** ⚠️ **use CZT 20–70 keV** (32 cm²), **flux-convert both instruments via ARF/RMF before dividing** (raw cross-instrument count ratios are physically meaningless). **More defensible primary Stage-2 = intra-HEL1OS CdTe 40–70/8–20 keV** (single detector, self-calibrating, Soft-Hard-Soft). **Activates C6+ only**; A/B/C1–5 run Stage-1 (HOPE) only, `source_channel=soft`.
- **Three-state labels:** Quiet (>60 min from any peak) / Pre-Flare ([peak−30min, HXR_onset−30s)) / Flare. **HXR_onset from HEL1OS CUSUM, target = GOES SXR peak.** Expanding-window normalization. **Replace `filtfilt`→`lfilter`** (zero-phase = future leakage). **CV split by Active Region + 27-day embargo.**
- **SEP veto:** mask windows where CZT 70–150/20–70 keV ratio >0.4 sustained >30 s before any Neupert/AND-gate computation. If ASPEX/STEPS L1 on PRADAN, use it (same spacecraft, zero offset).

---

## 8. Metrics & Evaluation (get this exactly right — judges know it cold)

- **TSS = TPR − FPR**, where **TPR = TP/(TP+FN)**, **FPR = FP/(FP+TN)**. ⚠️ **NOT TPR − FAR.** FAR = FP/(TP+FP) is a *different* metric (TP in denominator). Put the formula in `evaluate.py`'s docstring.
- Report **per-class tier [A/B, C, M/X]**: TPR, FPR, FAR, TSS, PR-AUC, confusion matrix.
- **Operational FAR = "alerts/day on confirmed quiet-Sun windows"** (the metric no other team computes).
- **Per-class lead-time survival curves `P(lead > T)`** for C/M/X, with published HOPE values overlaid (C: 3.5, M: 5.4, X: 9.4 min at P=0.5).
- ⚠️ Small samples (M≈150–400, X≈30–60 in window) → **report bootstrap 95% CI on every TSS and survival curve.**
- ⚠️ "Random splits inflate TSS" is qualitative in arXiv:2511.20465 — say "random CV causes documented AR-correlation leakage; we use strict chronological splits." Drop the specific "0.1–0.3" number.

---

## 9. The Killer Demo

Streamlit, **split-screen counterfactual replay** on a real Jul–Dec 2024 M/X event:
- **Left = SXR-only pipeline; Right = combined SoLEXS+HEL1OS.** Same event. Annotate "SXR-only alert: T=0" vs "Combined alert: T=−N.N min", shaded "Lead-time gain from HEL1OS."
- **Live Neupert cross-correlation panel:** `scipy.signal.correlate(HEL1OS, np.gradient(SoLEXS))` vs lag — the peak materializes in real time, annotated "Neupert lag τ = X.X min."
- **T–EM trajectory animation:** the (log EM, log T) dot tracing quiescent → HOPE corridor (10–15 MK) → impulsive → peak — the diagram ISRO physicists read daily.
- Alert badge with **T-minus countdown**; tiered WATCH/WARNING/ALERT; master catalogue table.

---

## 10. Deliverables

- **Master flare catalogue** CSV: `start, peak, end, goes_class, solexs_peak_flux, hel1os_peak_counts, lead_time_min, hope_triggered, neupert_conformant, sep_contaminated, source_channel`.
- **Per-class metrics table** (TSS/TPR/FPR/FAR + bootstrap CI) vs GOES.
- **Per-class lead-time survival-curve figure** with HOPE literature overlay.
- **Reproducible repo** — pinned env, one-command pipeline, model card, short methods writeup (document the 4 leakage guards explicitly — it implicitly invalidates competitors' inflated numbers).

---

## 11. Pre-Hackathon Setup (stage these BEFORE the event — they have real friction)

- `pip install sunpy astropy sunkit-spex sherpa pybaselines scipy numpy pandas streamlit matplotlib bokeh` — ⚠️ `sherpa` is a sunkit-spex dependency; `pybaselines` for SNIP background.
- ⚠️ **CHIANTI v10 database is NOT pip-installable:** download the tarball (~100–500 MB) from chiantidatabase.org, extract, set `XUVTOP=/path`. 20–40 min.
- ⚠️ `sunkit-spex` needs **Python ≥3.12**; XSMDAS may need 3.9 → **separate conda envs.**
- **Benchmark CHIANTI fit latency** on one 340-channel spectrum; if >100 ms, pre-compute emissivity tables (T∈[6,30] MK, 0.1 MK).
- **Identify 2–3 specific Jul–Dec 2024 M/X demo events**; verify FITS download+parse.
- **Register PRADAN ≥48 h before** + email issdc@istrac.gov.in.

---

## 12. Execution Roadmap (~30 h)

| Block | Activity | Output |
|---|---|---|
| **0–2 h (bootstrap)** | Env up; GOES XRS via Fido; sample SoLEXS/HEL1OS FITS; inspect HDUs; `ingest.py` skeleton (correct deadtimes); confirm PRADAN access status | running ingest on samples, GOES labels pulled |
| **2–8 h** | Full pipeline on GOES/XSM analogs: percentile background, EMG detection (single-band sub-A), HOPE T/EM proxy, catalogue merge | validated detector + nowcast catalogue on analog data |
| **8–14 h** | Port to real PRADAN SoLEXS+HEL1OS FITS; dual-aperture stitching tested on a known M-class event; UTC/+5s alignment | pipeline running on real Aditya-L1 data |
| **14–20 h** | Neupert residual CUSUM + HOPE lead-time on 3+ real events; Stage-2 (intra-HEL1OS ratio); AND-gate; SEP veto; GOES cross-check | per-event lead times, master catalogue, conformance fraction |
| **20–26 h** | `evaluate.py` (TSS=TPR−FPR, per-class, bootstrap CI, survival curves); HOPE threshold recalibration sweep; calibrated probabilities | defensible metrics table + figures |
| **26–30 h** | Split-screen demo + Neupert cross-corr + T–EM animation; dry-run; backup slides if PRADAN unavailable | rehearsed demo + screenshots |
| *stretch* | GOES-22yr CNN+LSTM pretrain → SoLEXS fine-tune (calibration layer only, **not** the forecaster) | optional ML overlay |

---

## 13. Day-1 Empirical Checklist (resolve before locking architecture)

| # | Unknown | Check | If bad → |
|---|---|---|---|
| 1 | PRADAN L1 delivery latency | newest SoLEXS L1 `TSTART` vs UTC | >5 min → reframe as replay/"near-real-time" |
| 2 | ~~SDD1 operating?~~ | **RESOLVED: DEAD.** SDD2-only pipeline. | Done |
| 3 | ~~HEL1OS detect B-class?~~ | **RESOLVED: bg=0 cps.** C-class=300 cps, M=4000+, X=15k-49k. | Count threshold works |
| 4 | CHIANTI fit fast enough? | benchmark one 340-ch SDD2 spectrum | >100 ms → pre-compute emissivity tables |
| 5 | ~~Neupert conformance?~~ | **PARTIALLY RESOLVED:** peak-to-peak delays 0-3 min, can be negative for impulsive. Onset-based = 6-13 min. | Use onset, report conformance |
| 6 | SoLEXS SDD2 efficiency >15 keV? | check ARF | May restrict overlap band |
| 7 | ASPEX/STEPS available? | On PRADAN, not downloaded | Use if time permits |
| 8 | ~~Training-set size~~ | **RESOLVED: 49 X-class + 958 M-class in Aditya-L1 window** (GOES-18 catalog) | Bootstrap CI on all metrics |

---

## 14. Risk Register & Audit-Caught Gotchas (do not trip on these)

| Wrong assumption | Reality | Fix |
|---|---|---|
| SDD1 is operational | **DEAD across all 14 tested days** (Sep 2024 — Jun 2026). Zero GTI, no data. | SDD2-only pipeline. No dual-aperture stitching. |
| Neupert delay = 2-10 min guaranteed | **Peak-to-peak can be ~0 or negative** for impulsive X-class (X6.9=+0.03min, X8.8=-0.7min) | Use onset-to-peak lead (6-13 min measured). Class prediction via integral. |
| CdTe 5-20 keV is best trigger | **CZT 40+ keV peaks ~2.5 min earlier** than CdTe 5-20 keV (confirmed on X8.8) | CZT primary trigger, CdTe secondary. |
| HEL1OS background is 0.15 cps | **Background is ~0 cps.** Median is 0 on all days. | Even a few sustained counts are significant. Count threshold, not class threshold. |
| 100% duty cycle always | **Feb 2026 has 47-48% NaN gaps.** 2024 data is clean. | Handle gaps. Use 2024 events for primary validation. |
| HEL1OS data is daily | **12-hour chunks.** Must stitch halves. | Time alignment between halves needed. |
| X8.1 (Feb 1, 2026) is best demo | **Flare at 23:57 UTC, only have 00:00-12:00 HEL1OS half.** SoLEXS 48% NaN. | Use Oct 2024 events (X8.8, X6.9, X4.4) — clean, both instruments. |
| "Most teams will fuse symmetrically" | This is obvious, not a hidden trap | Focus on real edges: multi-band trigger, empirical calibration, honest eval |
| "GOES missed 1,330 A-class" | Inverted — GOES finds *more* (1,851) with same algo | Claim only the **213 sub-A** as genuine GOES-misses |
| Neupert "physics-guaranteed" | Holds ~50–80% of M/X | Report conformance fraction; flag per event |
| TSS = TPR − FAR | **TSS = TPR − FPR** | Define formula in code |
| One blended lead-time number | Class-dependent; <C1 ≈ 0 | Per-class survival curves |
| 1 s CHIANTI fit | Noise-dominated at A/B/C | 10–30 s co-add |
| filtfilt for smoothing | Zero-phase = future leakage | Use lfilter; document it |
| CNN+LSTM as core edge | Scored 2.9/10; physics wins without it | Stretch goal only |

---

## 15. What To Skip

- **Symmetric ML fusion of HXR+SXR** — the root error; collapses the causal lag that *is* the lead time.
- **CNN+LSTM / transformers / foundation models as the forecaster** — physics satisfies all 3 criteria with zero training; ML is calibration-only, stretch.
- **Hawkes process, STEREO-A, Type-III radio, HEL1OS QPP event-mode, heavy web infra** — marginal benefit, high sprint cost.
- CME/SEP *arrival* prediction (out of scope) and imaging approaches (we have none).

---

## 16. Verified Citations (all real, audit-confirmed — cite freely)

- **SoLEXS:** arXiv:2509.26292 (Solar Physics 2025) · **HEL1OS:** arXiv:2512.12679 (Solar Physics 2025)
- **Neupert/ASO-S:** arXiv:2404.02653 · **HOPE/FAI:** arXiv:2407.04567 (Hudson, 13.4±6.0 min) + arXiv:2509.05234 (Telikicherla, per-class)
- **XSM catalogue:** arXiv:2312.09191 (Valluvan 2024) · **Leakage review:** arXiv:2511.20465 (Shao 2025)
- **ML baselines:** 1D-CNN ApJS 257 (Ahmadzadeh 2021, DOI 10.3847/1538-4365/ac37bc); BiLSTM TSS 0.924 (Hassani 2026, DOI 10.1007/s11227-026-08493-7)

---

*v2 reconciles: recon `w907nrydf` + genius gauntlet `wj87gkdcp` + 20-agent audit `w1okh5vgu`. 21 core facts independently re-verified; 24 fixes applied. Companion: `UNDERSTANDING.md`.*
