# ISRO Aditya-L1 Solar Flare Hackathon — Winning Plan (v2, audited)

> **Problem:** Nowcast + forecast solar flares from combined **SoLEXS** (soft X-ray) + **HEL1OS** (hard X-ray) on Aditya-L1.
> **Judged on:** (1) detection of **low AND high** class flares, (2) **high TPR + low false-alarm**, (3) **lead time** (minutes before flare *peak*).
>
> Built from 3 multi-agent workflows: recon (18 agents) → genius gauntlet (100 agents) → **20-agent correctness audit**. Every fact below is either ✅ verified against a real paper or ⚠️ flagged unverified. Read `UNDERSTANDING.md` for the *why*; this is the *how*. Paired arXiv IDs are real and audit-confirmed — cite them.

---

## 0. Winning Thesis (physics-first)

**Don't predict flares — measure the Neupert delay between the two payloads.** HEL1OS sees the *cause* (instantaneous electron energy deposition), SoLEXS sees the *effect* (time-integrated thermal plasma). In the flares where the Neupert relation holds, HXR onset precedes the SXR peak by minutes — **that delay is the lead time, a measurement, not a model output.** Build a **bifurcated, strictly-sequential** pipeline (SoLEXS-spectral for low-class; HEL1OS-Neupert for high-class), prove it live with a **split-screen counterfactual demo**, and back every number with **chronologically-validated, per-class metrics** an ISRO physicist can audit on the spot.

The differentiator is **rigor + real dual-payload physics**, not a model. Most teams will concatenate HXR+SXR into one LSTM — which collapses the causal lag that *is* the lead time. Zero-training physics beats them on all three criteria.

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
- **Two processing chains with different deadtimes** (critical): **timing chain = 1.6 µs** (used for *light curves* — flare detection), **spectral chain = 13.65 µs** (used for *PHA spectra* — T/EM). **CSPA ~364 cps background applies to the timing chain only.**
- Caught X2.9 within 33 h of commissioning (SOL2023-12-14; **SDD2 was operative, SDD1 saturated** — the dual-aperture design working as intended). **100% duty cycle** at L1 since 2024-01-06.
- ⚠️ SDD1 full characterization was still pending as of the paper (Sep 2025) — **verify SDD1 is in nominal operation in the Jul–Dec 2024 window** (Day-1 check).

**HEL1OS — hard X-ray (non-thermal electrons)** ✅ arXiv:2512.12679 (Solar Physics, DOI 10.1007/s11207-025-02543-8):
- **CdTe 8–70 keV / 0.5 cm²**; **CZT 20–150 keV / 32 cm²** (CZT has **64× the area** — use it for the hard band).
- Statistically-significant spectra **C6–X3**; benign particle background at L1. **1 s light curves** ✅.
- ⚠️ 10 ms event-list + 20 s PHA cadence: behind paywall — **verify before citing**. ⚠️ URSC page lists CdTe as 10–40 keV vs paper's 8–70 keV; cite the paper, be ready to reconcile.

**Combined 2–150 keV continuously — no prior Indian solar instrument did this. That span is the core novelty.**

---

## 3. Problem Reframed

### The Neupert mechanism (honestly)
`dSXR/dt ∝ HXR(t)` → the HXR peak precedes the SXR peak. ✅ arXiv:2404.02653 (ASO-S, 149 flares): 82.5% show corr ≥0.95.
**⚠️ NOT "physics-guaranteed":** the timing relation holds in **~50–80% of M/X flares** (Veronig 2002 finds ~50%; ~25% inconsistent). **Flag each event `neupert_conformant` (|corr(∫HXR, SXR)|>0.90) and report the conformance fraction as a result.** Gradual/conduction-dominated flares deviate.

### Flare timeline (two distinct lead-time mechanisms — do not conflate)
| Stage | Observable | Instrument | Lead vs SXR peak |
|---|---|---|---|
| **HOPE** thermal precursor | T rises to **10–15 MK**, EM rising, no HXR | SoLEXS spectral fit | **C5–M1: 3.46±2.26 / M1–X1: 5.39±3.86 / X1+: 9.38±4.49 min** ✅ arXiv:2509.05234; or **13.4±6.0 min (range 6–27)** for C1.2–M3.8 ✅ arXiv:2407.04567 — *two different studies, cite separately* |
| **HXR peak** (Neupert timing gap) | Non-thermal bremsstrahlung | HEL1OS | **~1–3 min (M); ~3–5 min (X)** |
| **SXR peak** | Thermal max → defines GOES class | SoLEXS | t = 0 (scored endpoint) |

### Honest per-class lead-time caveat (say this — it builds credibility)
- **X/M-class:** HOPE 5–10 min + Neupert 1–5 min → real, defensible multi-minute lead.
- **C5:** HOPE lead 3.46±2.26 min ✅. **C1–C4:** HOPE may be below SoLEXS fit threshold → seconds–2 min. **<C1:** undetectable precursor → lead ≈ 0, it's a *nowcast*.
- **Anchor correctly:** alarm = HXR/HOPE onset; target = **GOES SXR peak**, *not* GOES catalogue onset (which lags true onset 2–10 min). This definitional fix alone buys minutes of *real* lead.

### Three physically-separate sub-problems (the bifurcation is the game)
1. **Detect A/B/C GOES misses** → SoLEXS T(t)/EM(t) spectral fit (HEL1OS photon-starved below ~C6; fusing it adds noise).
2. **Forecast M/X with max lead** → HEL1OS-triggered Neupert residual + `∫HXR dt` class forecast.
3. **Suppress false alarms** → physics AND-gate coincidence.
**Handoff at ~C6.** Any unified model on a blended metric sacrifices #1 — what every competitor does.

---

## 4. System Architecture — 4-Layer Sequential Pipeline (never symmetric fusion)

```
ingest.py        SoLEXS+HEL1OS FITS readers; dual-aperture selector; deadtime (1.6µs timing / 13.65µs spectral);
                 CSPA 364cps (timing only); UTC align (+5s on Aditya ts to match GOES)
lightcurve.py    SoLEXS Band A 2–6 keV, Band B 6–12 keV; HEL1OS CdTe 8–20/20–70, CZT 20–70;
                 background = rolling 5th–10th percentile (≥60min) — NOT rolling mean (self-contaminates)
nowcast_soft.py  EMG/FRED peak fit (Edge 1); single-band 2–6 keV for sub-A/A, dual-band only C+
nowcast_hard.py  CZT/CdTe threshold + SEP veto (CZT 70–150/20–70 ratio)
catalogue_merge.py  master catalogue + AND-gate FAR suppression (Edge 3); source_channel ∈ {soft,hard,both}
hope_precursor.py   CHIANTI isothermal T/EM on 10–30s co-added spectra → WATCH (Edge 2)
neupert_residual.py r(t)=HEL1OS_CdTe_8-70 − α·dSXR/dt; CUSUM → Stage-0 trigger; ∫HXR dt → class (Edge 1-physics)
evaluate.py      TSS=TPR−FPR (define it!), per-class, bootstrap 95% CI, per-class survival curves
ui/app.py        split-screen counterfactual replay + live Neupert cross-correlation (Edge 2-demo)
```

**Layer 0 — Neupert residual streaming (zero training):** fit `α` once on 3–5 archived M flares (regress HEL1OS_CdTe_8-70keV vs forward-diff of SoLEXS Band A). Then `r(t)=HEL1OS(t)−α·(SoLEXS(t)−SoLEXS(t−1))`; CUSUM `k=0.5σ_quiet`, `h=3σ`, 5 consecutive samples. `∫HXR dt` from alarm → calibrated C/M/X thresholds.
**Layer 1 — HOPE (SoLEXS only):** CHIANTI isothermal fit on **10–30 s co-added** spectra (1 s is noise-dominated: O(10–50) net cts/s → ±3–5 MK). WATCH when T>8 MK while EM at background, ≥3 bins.
**Layer 2 — bifurcated nowcast:** low-class → EMG bank on SDD1; high-class (C6+) → HEL1OS CUSUM + integrator + SDD2.
**Layer 3 — AND-gate + tiered alerts:** WATCH→WARNING(+HEL1OS ±30s ≥2σ)→ALERT(+SoLEXS dual-band concordance); K-of-N vote + 30-min refractory.

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

**Demo events:** ⚠️ **NOT X6.3 2024-02-22 — it's in the non-public PV phase (Jan–Jun 2024).** Pick **2–3 confirmed M/X events from Jul–Dec 2024**, verify they download+parse before the event. PV data (incl. 2024-02-22 X6.3, 2024-05-10 X5.8) available on request to **sarwade@ursc.gov.in**.

**Ground-truth & cross-cal:** GOES/SWPC event list = labels. ⚠️ SoLEXS→GOES linear cross-cal valid only **2×10⁻⁶–1×10⁻⁴ W/m² (~C2–X1)** and is against **GOES XRS-A (0.5–4 Å)**, while class is defined in **XRS-B (1–8 Å)** — convert XRS-A→XRS-B via the CHIANTI fit. **Below C2, report SoLEXS native flux; class is extrapolated** (use XSM sub-C convention). ⚠️ GOES-8/15 underestimate flux 1.43× pre-2016 (not GOES-R 2017+) — SoLEXS spectral fits are *more accurate* labels at the tails (a provable claim).

---

## 6. Nowcasting Detail

- **Background:** rolling **5th–10th percentile** quantile (≥60 min) — immune to pre-flare contamination; rolling *mean* raises the threshold exactly when it should be lowest.
- **XSM-actual detection method** ✅ arXiv:2312.09191 (cite it correctly): 120 s mean-binning → Gaussian smoothing (σ_G=2) → dynamic threshold τ_FG=0.3·σ_BG → `scipy.signal.find_peaks` topographic prominence → **EMG (Elementary Flare Profile)** fit for start/peak/end → decompose overlaps. Analysis band 1.55–12.4 keV. **89.64% completeness for B1.0+ vs GOES.**
- ⚠️ **Sub-A/A: single-band (2–6 keV)** detection — 5–8 MK plasma emits negligibly >6 keV, so dual-band would reject them. **Dual-band concordance only for C-class+.**
- **Dual-aperture stitching:** SDD1 below ~1e5 cps, SDD2 above. ⚠️ SDD2 offset is **flux-dependent & bidirectional** (reads ~15% low at quiescence, high at peaks) — interpolate a calibration polynomial across the crossover, **not** a fixed +15%. The CHIANTI T/EM fit is the most robust GOES-flux proxy.
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
| 2 | SDD1 actually operating Jul–Dec 2024? | quiet-Sun SDD1 LC, expect 50–200 cps | minimal-op → low-class shifts to SDD2 at degraded SNR; state honestly |
| 3 | HEL1OS CdTe detect B-class? | analytic 8–20 keV cps for B1 (CHIANTI T~8 MK) vs 0.15 cps bg | below bg → push AND-gate handoff to C2–C3 |
| 4 | CHIANTI fit fast enough? | benchmark one spectrum | >100 ms → pre-compute emissivity tables; else 10–30 s co-add |
| 5 | Neupert conformance in SC25? | plot HEL1OS vs SoLEXS, first 10–15 M events | <60% → more events to HOPE-only path; report fraction |
| 6 | SoLEXS SDD2 efficiency >15 keV? | ARF from arXiv:2509.26292 / SoLEXS_Tools | <5% @20 keV → overlap band restricted to 8–15 keV |
| 7 | ASPEX/STEPS on PRADAN? | browse portal | available → primary SEP flag (same bus) |
| 8 | Training-set size | count M/X in window | small → bootstrap CI on all metrics |

---

## 14. Risk Register & Audit-Caught Gotchas (do not trip on these)

| Wrong assumption | Reality | Fix |
|---|---|---|
| "GOES missed 1,330 A-class" | Inverted — GOES finds *more* (1,851) with same algo | Claim only the **213 sub-A** as genuine GOES-misses |
| 5th-pct floor / dual-band>60s = "XSM method" | Fabricated; XSM uses 120s mean-bin + Gaussian σ=2 + τ=0.3σ_BG | Cite XSM's real method; single-band for sub-A |
| Deadtime 13.65 µs on light curves | That's the spectral chain; **timing chain = 1.6 µs** | 1.6 µs for LCs, 13.65 µs for spectra |
| Neupert "physics-guaranteed" | Holds ~50–80% of M/X | Report conformance fraction; flag per event |
| TSS = TPR − FAR | **TSS = TPR − FPR** | Define formula in code |
| One blended lead-time number | Class-dependent; <C1 ≈ 0 | Per-class survival curves |
| Cross-instrument raw count ratio | Physically invalid; wrong detector | Flux-convert via ARF/RMF, use CZT, or intra-HEL1OS ratio |
| GOES class for A-class SoLEXS | Cross-cal floor is C2; cal is vs XRS-A not XRS-B | Native flux <C2; convert XRS-A→B via CHIANTI |
| 1 s CHIANTI fit | Noise-dominated at A/B/C | 10–30 s co-add |
| PRADAN instant access | Mandatory admin approval | Register ≥48 h early; build on analogs |
| filtfilt for smoothing | Zero-phase = future leakage | Use lfilter; document it |
| CNN+LSTM as core edge | Scored 2.9/10; physics wins without it | Stretch goal only |
| Demo event 2024-02-22 | PV phase, not public | Use Jul–Dec 2024 events |

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
