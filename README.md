# SUDARSHAN 🌞🔥

**S**oft-and-hard X-ray **U**nified **D**etection, **A**nticipation & **R**eal-time **S**olar-flare **H**ardness-**A**ware **N**owcasting

> *An Aditya-L1 dual-payload pipeline that detects, classifies, and forecasts solar flares by measuring the natural cause→effect delay between hard and soft X-rays.*

Built for the ISRO hackathon problem: *"Forecasting and/or Nowcasting of Solar Flares using combined Soft and Hard X-ray data from Aditya-L1."*

---

## What it is

Solar flares are sudden bursts of energy from the Sun that disrupt satellites, GPS, radio, and power grids. ISRO's **Aditya-L1** spacecraft watches the Sun continuously from 1.5 million km away with two X-ray instruments:

- **SoLEXS** — *soft* (lower-energy) X-rays, 2–22 keV
- **HEL1OS** — *hard* (higher-energy) X-rays, 8–150 keV

**SUDARSHAN** uses both, together, to do two jobs:

1. **Nowcast** — detect flares in real time, size them (class A→X), and log them into a master catalogue.
2. **Forecast** — warn that a flare is coming *before it peaks*, with a measured lead time in minutes.

…plus a live dashboard that shows the X-ray light curves and fires visual alerts.

---

## The core idea (our edge)

In a flare, the **hard** X-rays arrive a few minutes *before* the **soft** X-rays reach their peak — **lightning before thunder.** The soft X-ray peak is what defines the flare's official size; the hard X-rays are the early "cause."

So we don't *guess* the future — we **measure** the delay between cause (HEL1OS) and effect (SoLEXS). That delay *is* the lead time, set by physics (the **Neupert effect**), not by a trained model. Most teams will mash both signals into one AI and accidentally destroy that delay; we keep them in causal order and win for free.

For the faint, low-class flares that the hard sensor can't even see, we instead watch the **plasma temperature** rise in the soft sensor's spectrum — catching flares the standard GOES catalogue misses.

**One sequential pipeline, three problems solved separately:**

```
Layer 0  Hard X-ray jump (Neupert residual) ──► earliest early-warning   [zero training]
Layer 1  Soft X-ray temperature rise (HOPE) ──► catches faint flares
Layer 2  Bifurcated nowcast: soft→small flares, hard→big flares + class
Layer 3  Both-sensors-agree gate ──► kills false alarms, tiered alerts
```

---

## What the judges score (and how we target each)

| Criterion | Our answer |
|---|---|
| Detect **low AND high** class flares | soft-sensor temperature path catches sub-A/A/B/C; hard path handles M/X |
| **High true-positive, low false-alarm** | both-sensors-must-agree coincidence gate |
| **Lead time** before flare peak | the measured hard→soft (Neupert) delay, reported honestly per flare class |

---

## Repository contents

| File | What it is |
|---|---|
| `ps.md` | The original ISRO problem statement |
| `UNDERSTANDING.md` | **The "why"** — the core idea and winning angle, revised with real data findings |
| `PLAN.md` | **The "how"** — the build plan, updated with empirical corrections |
| `ASSUMPTIONS.md` | **The "what changed"** — every prior assumption tested against real Aditya-L1 data |
| `README.md` | This file |

> Originally produced by multi-agent research (139 agents, 24 errors caught). Then **revised against 14 days of real Aditya-L1 data** (14 SoLEXS + 16 HEL1OS datasets + GOES-18 catalog of 45,061 flares). Key corrections: SDD1 is dead, Neupert peak delay can be ~0 for impulsive X-class, CZT 40+ keV peaks 2.5 min before CdTe 5-20 keV.

---

## Status

- ✅ Problem deeply understood
- ✅ Winning angle defined
- ✅ Detailed, fact-checked plan
- ✅ Real Aditya-L1 data downloaded and analyzed (14 SoLEXS + 16 HEL1OS days)
- ✅ GOES ground-truth data downloaded (2024-2026, 1-min flux + 45k flare catalog)
- ✅ Assumptions revised against empirical evidence (see ASSUMPTIONS.md)
- ⬜ Implementation — not started yet

---

## Planned stack

Python · SunPy · Astropy · sunkit-spex + CHIANTI · SciPy · NumPy/Pandas · Streamlit

**Data:** Aditya-L1 SoLEXS + HEL1OS Level-1 (ISSDC PRADAN portal); GOES XRS, Chandrayaan-2 XSM, and Fermi/GBM as ground-truth and fallback datasets.

---

*Problem source: ISRO hackathon. See `ps.md`.*
