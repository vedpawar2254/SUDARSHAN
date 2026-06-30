"""
Detection prototype v3 — Multi-day test
Runs detection pipeline on ALL dual-instrument days and reports aggregate metrics.
"""

import numpy as np
from astropy.io import fits
import netCDF4 as nc
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import glob, os

# ============================================================
# 0. UTILITY
# ============================================================

def merge_nearby(detections, merge_window_min=12, time_key='time_hrs', peak_key='peak_counts',
                 adaptive=False):
    """Merge detections within merge_window_min. Keep highest peak.
    If adaptive=True, scale merge window by peak amplitude:
      net < 420 (C-class) → 12 min
      net 420-6000 (M-class) → 30 min
      net > 6000 (X-class) → 55 min
    """
    if not detections:
        return []
    sorted_dets = sorted(detections, key=lambda d: d.get(time_key) or d.get('onset_hrs', 0))
    merged = [sorted_dets[0].copy()]
    for d in sorted_dets[1:]:
        d_time = d.get(time_key) or d.get('onset_hrs', 0)
        m_time = merged[-1].get(time_key) or merged[-1].get('onset_hrs', 0)

        if adaptive:
            m_peak = merged[-1].get(peak_key, merged[-1].get('peak_ctr', 0))
            m_bg = merged[-1].get('background', 0)
            m_net = m_peak - m_bg if m_bg else m_peak
            d_peak = d.get(peak_key, d.get('peak_ctr', d.get('peak_hardness', 0)))

            # Only merge if the new detection is WEAKER than the current one
            # (= decay tail). If it's stronger or comparable, it's likely a new event.
            if d_peak >= m_peak * 0.8:
                # New peak is nearly as strong or stronger — treat as new event
                window = merge_window_min
            elif m_net > 6000:
                window = 55
            elif m_net > 300:
                window = 30
            elif m_net > 100:
                window = 18
            else:
                window = merge_window_min
        else:
            window = merge_window_min

        if abs(d_time - m_time) * 60 < window:
            d_peak = d.get(peak_key, d.get('peak_ctr', d.get('peak_hardness', 0)))
            m_peak = merged[-1].get(peak_key, merged[-1].get('peak_ctr', merged[-1].get('peak_hardness', 0)))
            if d_peak > m_peak:
                merged[-1] = d.copy()
        else:
            merged.append(d.copy())
    return merged

# Background-subtracted thresholds (from empirical analysis):
# C1-C9 peak-bg: 36-409.  M1+ peak-bg: 444+.  X1+ peak-bg: 7181+
# Gap: C9 max peak-bg=409, M1 min peak-bg=444 → boundary at 420
# Gap: M6 max peak-bg=5417, X1 min peak-bg=7181 → boundary at 6000
CLASS_THRESHOLDS_BG_SUB = {'C': 30, 'M': 420, 'X': 6000}

def classify_by_counts(peak_counts, background=0):
    """Classify using background-subtracted counts."""
    net = peak_counts - background
    if net >= CLASS_THRESHOLDS_BG_SUB['X']:
        return 'X'
    elif net >= CLASS_THRESHOLDS_BG_SUB['M']:
        return 'M'
    elif net >= CLASS_THRESHOLDS_BG_SUB['C']:
        return 'C'
    else:
        return 'B'

# ============================================================
# 1. GENERIC LOADERS
# ============================================================

def load_goes_flares(date):
    """Load GOES flare catalog for a given date. Dedup G16/G18."""
    base = datetime(2000, 1, 1, 12, 0, 0)
    day_start = (datetime(date.year, date.month, date.day, 0, 0) - base).total_seconds()
    day_end = (datetime(date.year, date.month, date.day, 0, 0) + timedelta(days=1) - base).total_seconds()

    flares = []
    for catalog in glob.glob("data/goes_flares/sci_xrsf-l2-flsum_*.nc"):
        ds = nc.Dataset(catalog)
        time_data = ds.variables['time'][:]
        flare_class = ds.variables['flare_class'][:]
        xrsb = ds.variables['xrsb_flux'][:]

        mask = (time_data >= day_start) & (time_data < day_end)
        for i in np.where(mask)[0]:
            fc = str(flare_class[i]).strip()
            if not fc or fc == '--':
                continue
            if fc[0] in ('A', 'B', 'C', 'M', 'X'):
                t = base + timedelta(seconds=float(time_data[i]))
                flares.append({
                    'time': t,
                    'utc_hours': t.hour + t.minute / 60 + t.second / 3600,
                    'class': fc,
                    'peak_flux': float(xrsb[i]),
                })
        ds.close()

    flares.sort(key=lambda x: x['utc_hours'])
    deduped = []
    for f in flares:
        if deduped and abs(f['utc_hours'] - deduped[-1]['utc_hours']) * 60 < 3:
            if f['peak_flux'] > deduped[-1]['peak_flux']:
                deduped[-1] = f
        else:
            deduped.append(f)
    return deduped


def load_solexs(date):
    """Load SoLEXS SDD2 light curve + spectra for a date."""
    datestr = date.strftime('%Y%m%d')
    lc_pattern = f"data/AL1_SLX_L1_{datestr}_*/SDD2/*.lc"
    lc_files = glob.glob(lc_pattern)
    if not lc_files:
        return None

    with fits.open(lc_files[0]) as f:
        time_unix = f[1].data['TIME']
        counts = f[1].data['COUNTS']

    t0 = time_unix[0]
    t_hrs = (time_unix - t0) / 3600

    pi_pattern = f"data/AL1_SLX_L1_{datestr}_*/SDD2/*.pi"
    pi_files = glob.glob(pi_pattern)

    hardness = None
    high_counts = None
    spec_t_hrs = None

    if pi_files:
        with fits.open(pi_files[0]) as f:
            d = f[1].data
            spec_time = d['TSTART']
            spec_t_hrs = (spec_time - t0) / 3600

            n = len(d)
            hardness = np.full(n, np.nan)
            high_counts = np.full(n, np.nan)
            for i in range(n):
                low = np.sum(d['COUNTS'][i][0:85])
                high = np.sum(d['COUNTS'][i][100:340])
                if low > 0:
                    hardness[i] = high / low
                high_counts[i] = high

    return {
        't_hrs': t_hrs,
        'counts': counts,
        'spec_t_hrs': spec_t_hrs,
        'hardness': hardness,
        'high_counts': high_counts,
        't0': t0,
    }


def load_helios(date):
    """Load HEL1OS CdTe + CZT for a date, stitching halves."""
    datestr = f"{date.year}/{date.month:02d}/{date.day:02d}"
    halves = sorted(glob.glob(f"data/helios/{datestr}/HLS_*"))
    if not halves:
        return None

    result = {}
    for band_name, detector, hdu_idx in [
        ('cdte_5_20', 'cdte', 1),
        ('czte_40_60', 'czt', 2),  # naming kept for compat
    ]:
        all_mjd, all_ctr = [], []
        for hdir in halves:
            fpath = os.path.join(hdir, detector, f"lightcurve_{detector}1.fits")
            if not os.path.exists(fpath):
                continue
            try:
                with fits.open(fpath) as f:
                    if hdu_idx < len(f):
                        all_mjd.append(f[hdu_idx].data['MJD'])
                        all_ctr.append(f[hdu_idx].data['CTR'])
            except Exception as e:
                print(f"    WARN: {fpath} HDU {hdu_idx}: {e}")
                continue

        if not all_mjd:
            continue

        mjd = np.concatenate(all_mjd)
        ctr = np.concatenate(all_ctr)
        order = np.argsort(mjd)
        mjd, ctr = mjd[order], ctr[order]
        base_mjd = int(mjd[0])
        t_hrs = (mjd - base_mjd) * 24

        result[band_name] = {'t_hrs': t_hrs, 'ctr': ctr}

    return result if result else None


# ============================================================
# 2. DETECTION ALGORITHMS (same as prototype_detect.py)
# ============================================================

def detect_solexs_threshold(t_hrs, counts, bg_window_sec=3600, threshold_factor=2.5,
                            min_peak_counts=40, min_prominence=20, min_distance_sec=300,
                            min_net_counts=30, min_sustained_sec=10):
    valid = ~np.isnan(counts)
    c = np.where(valid, counts, 0).astype(float)

    w = bg_window_sec
    background = np.full_like(c, np.nan)
    for i in range(w, len(c)):
        window = c[max(0, i - w):i]
        window_valid = window[window > 0]
        if len(window_valid) > 100:
            background[i] = np.percentile(window_valid, 5)

    first_valid = np.argmax(~np.isnan(background))
    background[:first_valid] = background[first_valid]
    bg_clean = np.where(np.isnan(background), np.nanmedian(background), background)
    threshold = bg_clean * threshold_factor

    peaks_idx, _ = find_peaks(c, height=min_peak_counts,
                               distance=min_distance_sec,
                               prominence=min_prominence)

    # Pre-compute sustained mask: count consecutive seconds above 2× background
    above_2x = (c > bg_clean * 2.0) & valid
    sustained = np.zeros(len(c), dtype=int)
    run = 0
    for i in range(len(c)):
        if above_2x[i]:
            run += 1
        else:
            # Write run length to all positions in the run
            if run > 0:
                sustained[i - run:i] = run
            run = 0
    if run > 0:
        sustained[len(c) - run:] = run

    detections = []
    for p in peaks_idx:
        net = c[p] - bg_clean[p]
        if c[p] > threshold[p] and valid[p] and net >= min_net_counts:
            # Check sustained duration around peak
            if sustained[p] < min_sustained_sec:
                continue
            detections.append({
                'time_hrs': t_hrs[p],
                'peak_counts': c[p],
                'background': bg_clean[p],
                'ratio': c[p] / max(bg_clean[p], 1),
                'net_counts': net,
                'sustained_sec': int(sustained[p]),
                'method': 'slx_threshold',
            })
    return detections, bg_clean


def detect_solexs_hardening(spec_t_hrs, hardness, high_counts,
                            ratio_threshold=0.003, sustained_sec=20,
                            refractory_min=10, min_high_counts=5):
    if hardness is None or spec_t_hrs is None:
        return []

    valid = ~np.isnan(hardness)
    n = len(hardness)

    w = 3600
    baseline_hardness = np.full(n, np.nan)
    for i in range(w, n):
        window = hardness[max(0, i - w):i]
        wvalid = window[~np.isnan(window)]
        if len(wvalid) > 100:
            baseline_hardness[i] = np.median(wvalid)

    first_valid = np.argmax(~np.isnan(baseline_hardness))
    baseline_hardness[:first_valid] = baseline_hardness[first_valid]
    bl = np.where(np.isnan(baseline_hardness), np.nanmedian(baseline_hardness), baseline_hardness)

    above = valid & (hardness > bl + ratio_threshold) & (high_counts > min_high_counts)

    detections = []
    run_length = 0
    last_trigger_hrs = -999

    for i in range(n):
        if above[i]:
            run_length += 1
            if run_length == sustained_sec:
                onset_idx = i - sustained_sec + 1
                onset_hrs = spec_t_hrs[onset_idx]

                if (onset_hrs - last_trigger_hrs) * 60 < refractory_min:
                    run_length = 0
                    continue

                end = min(n, onset_idx + 1800)
                peak_idx = onset_idx + np.nanargmax(hardness[onset_idx:end])

                detections.append({
                    'onset_hrs': spec_t_hrs[onset_idx],
                    'peak_hrs': spec_t_hrs[peak_idx],
                    'peak_hardness': hardness[peak_idx],
                    'baseline_hardness': bl[onset_idx],
                    'method': 'slx_hardening',
                })
                last_trigger_hrs = onset_hrs
                run_length = 0
        else:
            run_length = 0

    return detections


def detect_helios_cdte(t_hrs, ctr, onset_threshold=75, sustained_sec=5,
                       refractory_min=10):
    detections = []
    consecutive_high = 0
    nonzero_high_start = None
    last_trigger_hrs = -999

    for i in range(len(ctr)):
        if ctr[i] == 0:
            continue
        if ctr[i] >= onset_threshold:
            consecutive_high += 1
            if consecutive_high == 1:
                nonzero_high_start = i
            if consecutive_high >= sustained_sec:
                onset_hrs = t_hrs[nonzero_high_start]
                if (onset_hrs - last_trigger_hrs) * 60 < refractory_min:
                    consecutive_high = 0
                    continue
                end = min(len(ctr), i + 1800)
                peak_idx = i + np.argmax(ctr[i:end])
                detections.append({
                    'onset_hrs': onset_hrs,
                    'peak_hrs': t_hrs[peak_idx],
                    'peak_ctr': ctr[peak_idx],
                    'method': 'cdte_5_20',
                })
                last_trigger_hrs = onset_hrs
                consecutive_high = 0
        else:
            consecutive_high = 0
    return detections


def detect_helios_czt(t_hrs, ctr, onset_threshold=50, sustained_sec=3,
                      refractory_min=10):
    detections = []
    consecutive_high = 0
    nonzero_high_start = None
    last_trigger_hrs = -999

    for i in range(len(ctr)):
        if ctr[i] == 0:
            continue
        if ctr[i] >= onset_threshold:
            consecutive_high += 1
            if consecutive_high == 1:
                nonzero_high_start = i
            if consecutive_high >= sustained_sec:
                onset_hrs = t_hrs[nonzero_high_start]
                if (onset_hrs - last_trigger_hrs) * 60 < refractory_min:
                    consecutive_high = 0
                    continue
                end = min(len(ctr), i + 1800)
                peak_idx = i + np.argmax(ctr[i:end])
                detections.append({
                    'onset_hrs': onset_hrs,
                    'peak_hrs': t_hrs[peak_idx],
                    'peak_ctr': ctr[peak_idx],
                    'method': 'czt_40_60',
                })
                last_trigger_hrs = onset_hrs
                consecutive_high = 0
        else:
            consecutive_high = 0
    return detections


# ============================================================
# 3. MATCHING AND SCORING
# ============================================================

def match_detections(detections, goes_flares, window_min=10):
    matched = []
    used_goes = set()
    used_det = set()

    det_flare_pairs = []
    for i, det in enumerate(detections):
        det_time = det.get('time_hrs') or det.get('onset_hrs') or det.get('peak_hrs') or 0
        if det_time is None or det_time == 0:
            continue
        for j, flare in enumerate(goes_flares):
            dt = abs(det_time - flare['utc_hours']) * 60
            if dt < window_min:
                det_flare_pairs.append((dt, i, j))

    det_flare_pairs.sort()
    for dt, i, j in det_flare_pairs:
        if i in used_det or j in used_goes:
            continue
        matched.append((detections[i], goes_flares[j], dt))
        used_det.add(i)
        used_goes.add(j)

    unmatched = [d for i, d in enumerate(detections) if i not in used_det]
    missed = [f for j, f in enumerate(goes_flares) if j not in used_goes]
    return matched, unmatched, missed


def compute_lead_time(detections, goes_flares, window_min=15):
    used = set()
    results = []
    for det in detections:
        det_onset = det.get('onset_hrs') or det.get('time_hrs')
        best_j, best_lead = None, None
        for j, flare in enumerate(goes_flares):
            if j in used:
                continue
            lead = (flare['utc_hours'] - det_onset) * 60
            if -5 < lead < window_min + 15:
                if best_j is None or abs(lead) < abs(best_lead):
                    best_j = j
                    best_lead = lead
        if best_j is not None:
            used.add(best_j)
            results.append({
                'goes_class': goes_flares[best_j]['class'],
                'lead_time_min': best_lead,
            })
    return results


# ============================================================
# 4. RUN ONE DAY
# ============================================================

def run_day(date):
    """Run full detection pipeline on one day. Return per-method results."""
    datestr = date.strftime('%Y-%m-%d')

    goes_flares = load_goes_flares(date)
    # Filter to C/M/X only for scoring
    goes_cmx = [f for f in goes_flares if f['class'][0] in ('C', 'M', 'X')]

    slx = load_solexs(date)
    hel = load_helios(date)

    if slx is None:
        print(f"  {datestr}: NO SoLEXS data")
        return None
    if hel is None:
        print(f"  {datestr}: NO HEL1OS data")
        return None

    n_valid = (~np.isnan(slx['counts'])).sum()
    nan_pct = (1 - n_valid / len(slx['counts'])) * 100

    cdte = hel.get('cdte_5_20')
    czt = hel.get('czte_40_60')

    c_count = len([f for f in goes_cmx if f['class'][0] == 'C'])
    m_count = len([f for f in goes_cmx if f['class'][0] == 'M'])
    x_count = len([f for f in goes_cmx if f['class'][0] == 'X'])

    print(f"\n{'='*70}")
    print(f"  {datestr}  |  GOES: {c_count}C {m_count}M {x_count}X = {len(goes_cmx)} flares  |  NaN: {nan_pct:.0f}%")
    print(f"{'='*70}")

    if not goes_cmx:
        print(f"  No C/M/X flares this day — skipping scoring (quiet day)")

    for f in goes_cmx:
        print(f"    {f['time'].strftime('%H:%M')} {f['class']:>6s}  peak={f['peak_flux']:.2e}")

    results = {}

    # Method 1: SoLEXS threshold (adaptive merge: C=12min, M=30min, X=55min)
    slx_det_raw, background = detect_solexs_threshold(slx['t_hrs'], slx['counts'])
    slx_det = merge_nearby(slx_det_raw, merge_window_min=12, time_key='time_hrs',
                           peak_key='peak_counts', adaptive=True)

    # Method 2: Spectral hardening (lower threshold for C-class sensitivity)
    hard_det_raw = detect_solexs_hardening(slx['spec_t_hrs'], slx['hardness'], slx['high_counts'],
                                           ratio_threshold=0.002, sustained_sec=15, min_high_counts=2)
    hard_det = merge_nearby(hard_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_hardness')

    # Method 3: CdTe 5-20
    cdte_det = []
    if cdte is not None:
        cdte_det_raw = detect_helios_cdte(cdte['t_hrs'], cdte['ctr'])
        cdte_det = merge_nearby(cdte_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    # Method 4: CZT 40-60
    czt_det = []
    if czt is not None:
        czt_det_raw = detect_helios_czt(czt['t_hrs'], czt['ctr'])
        czt_det = merge_nearby(czt_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    # Method 5: AND-gate
    and_detections = []
    for sd in slx_det:
        for cd in cdte_det:
            sd_time = sd['time_hrs']
            cd_time = cd.get('onset_hrs', cd.get('time_hrs', 0))
            if abs(sd_time - cd_time) * 60 < 5:
                and_detections.append({
                    'time_hrs': min(sd_time, cd_time),
                    'slx_peak': sd['peak_counts'],
                    'cdte_peak': cd.get('peak_ctr', 0),
                    'method': 'and_gate',
                })
                break
    and_det = merge_nearby(and_detections, merge_window_min=12, time_key='time_hrs', peak_key='slx_peak')

    # Method 6: Combined (hardening trigger + counts classification + CdTe/CZT confirm)
    combined = []
    for hd in hard_det:
        onset = hd.get('onset_hrs', hd.get('time_hrs', 0))

        # Find SoLEXS peak counts in 20-min forward window
        best_slx = None
        for sd in slx_det_raw:
            dt_min = (sd['time_hrs'] - onset) * 60
            if -5 < dt_min < 20:
                if best_slx is None or sd['peak_counts'] > best_slx['peak_counts']:
                    best_slx = sd

        if best_slx:
            peak_counts = best_slx['peak_counts']
            bg = best_slx.get('background', 0)
        else:
            onset_idx = np.argmin(np.abs(slx['t_hrs'] - onset))
            end_idx = min(len(slx['counts']), onset_idx + 1200)
            window = slx['counts'][onset_idx:end_idx]
            valid_window = window[~np.isnan(window)]
            peak_counts = float(np.max(valid_window)) if len(valid_window) > 0 else 0
            bg = float(background[onset_idx]) if onset_idx < len(background) else 0

        pred_class = classify_by_counts(peak_counts, bg)

        cdte_confirmed = any(abs((cd.get('onset_hrs', cd.get('time_hrs', 0))) - onset) * 60 < 5 for cd in cdte_det)
        czt_confirmed = any(abs((cz.get('onset_hrs', cz.get('time_hrs', 0))) - onset) * 60 < 5 for cz in czt_det)

        confidence = 'LOW'
        if pred_class in ('M', 'X') and cdte_confirmed:
            confidence = 'MED'
        if pred_class == 'X' and czt_confirmed:
            confidence = 'HIGH'
        if pred_class in ('C', 'B'):
            confidence = 'MED'

        combined.append({
            'time_hrs': onset,
            'onset_hrs': onset,
            'pred_class': pred_class,
            'peak_counts': peak_counts,
            'background': bg,
            'net_counts': peak_counts - bg,
            'cdte_confirmed': cdte_confirmed,
            'czt_confirmed': czt_confirmed,
            'confidence': confidence,
            'method': 'combined',
        })

    # Method 7: Hybrid — SoLEXS threshold as primary (high TPR),
    # hardening or CdTe as confirmation to reduce FAR.
    # For C-class: SoLEXS-only is acceptable (CdTe can't see C-class)
    # For M+: require hardening OR CdTe confirmation
    hybrid = []
    for sd in slx_det:
        sd_time = sd['time_hrs']
        peak_counts = sd['peak_counts']
        bg = sd.get('background', 0)
        pred_class = classify_by_counts(peak_counts, bg)
        net = peak_counts - bg

        # Check confirmations
        hardening_confirmed = any(
            abs((hd.get('onset_hrs', hd.get('time_hrs', 0)) - sd_time)) * 60 < 10
            for hd in hard_det
        )
        cdte_confirmed = any(
            abs((cd.get('onset_hrs', cd.get('time_hrs', 0)) - sd_time)) * 60 < 5
            for cd in cdte_det
        )
        czt_confirmed = any(
            abs((cz.get('onset_hrs', cz.get('time_hrs', 0)) - sd_time)) * 60 < 5
            for cz in czt_det
        )

        # Decision: accept C-class from SoLEXS alone, require confirmation for M+
        # For M-class: accept if ratio > 5× (strong signal) OR hardening/CdTe confirms
        accept = False
        if pred_class in ('C', 'B'):
            accept = True  # SoLEXS-only OK for C-class
        elif pred_class == 'M':
            strong_signal = sd.get('ratio', 0) >= 5.0
            accept = hardening_confirmed or cdte_confirmed or strong_signal
        elif pred_class == 'X':
            accept = hardening_confirmed or cdte_confirmed or sd.get('ratio', 0) >= 10.0

        if not accept:
            continue

        # Lead time: use hardening onset if available, else SoLEXS peak time
        onset = sd_time
        for hd in hard_det:
            hd_time = hd.get('onset_hrs', hd.get('time_hrs', 0))
            if abs(hd_time - sd_time) * 60 < 10:
                onset = min(onset, hd_time)
                break

        confidence = 'LOW'
        if pred_class in ('C', 'B'):
            confidence = 'MED'
        if hardening_confirmed:
            confidence = 'MED'
        if cdte_confirmed:
            confidence = 'MED'
        if czt_confirmed:
            confidence = 'HIGH'

        hybrid.append({
            'time_hrs': onset,
            'onset_hrs': onset,
            'pred_class': pred_class,
            'peak_counts': peak_counts,
            'background': bg,
            'net_counts': net,
            'hardening_confirmed': hardening_confirmed,
            'cdte_confirmed': cdte_confirmed,
            'czt_confirmed': czt_confirmed,
            'confidence': confidence,
            'method': 'hybrid',
        })

    hybrid = merge_nearby(hybrid, merge_window_min=12, time_key='time_hrs',
                          peak_key='peak_counts', adaptive=True)

    # Score all methods
    methods = {
        'SoLEXS threshold': slx_det,
        'Hardening': [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in hard_det],
        'CdTe 5-20': [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in cdte_det],
        'CZT 40-60': [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in czt_det],
        'AND-gate': and_det,
        'Combined': combined,
        'Hybrid': hybrid,
    }

    print(f"\n  {'Method':20s} {'Det':>4s} {'TP':>4s} {'Miss':>4s} {'FA':>4s} {'TPR':>7s} {'FAR':>7s}")
    print(f"  {'-'*55}")

    for name, dets in methods.items():
        if goes_cmx:
            m, fa, mi = match_detections(dets, goes_cmx)
            tpr = len(m) / len(goes_cmx) * 100 if goes_cmx else 0
            far = len(fa) / max(len(dets), 1) * 100
            print(f"  {name:20s} {len(dets):4d} {len(m):4d} {len(mi):4d} {len(fa):4d} {tpr:6.1f}% {far:6.1f}%")
            results[name] = {
                'det': len(dets), 'tp': len(m), 'miss': len(mi), 'fa': len(fa),
                'n_flares': len(goes_cmx),
            }
        else:
            print(f"  {name:20s} {len(dets):4d}   (no flares to score against)")
            results[name] = {
                'det': len(dets), 'tp': 0, 'miss': 0, 'fa': len(dets),
                'n_flares': 0,
            }

    # Lead times for combined
    if goes_cmx and combined:
        leads = compute_lead_time(combined, goes_cmx)
        if leads:
            print(f"\n  Combined lead times:")
            for l in leads:
                print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")

    # Classification accuracy for hybrid
    if goes_cmx and hybrid:
        m, _, _ = match_detections(hybrid, goes_cmx)
        correct = sum(1 for det, flare, _ in m if det['pred_class'] == flare['class'][0])
        if m:
            print(f"  Hybrid class accuracy: {correct}/{len(m)} = {correct/len(m)*100:.0f}%")
            for det, flare, _ in m:
                actual = flare['class'][0]
                pred = det['pred_class']
                net = det.get('net_counts', 0)
                conf = det.get('confidence', '?')
                ok = "OK" if actual == pred else f"WRONG({pred})"
                print(f"    {flare['class']:>6s} → {pred}  net={net:.0f}  conf={conf}  {ok}")
        results['_class_correct'] = correct
        results['_class_total'] = len(m)

    # Per-class TPR for hybrid
    if goes_cmx and hybrid:
        for cls in ['C', 'M', 'X']:
            cls_flares = [f for f in goes_cmx if f['class'][0] == cls]
            if cls_flares:
                m_cls, _, _ = match_detections(hybrid, cls_flares)
                results[f'_tpr_{cls}'] = (len(m_cls), len(cls_flares))

    # Lead times for hybrid
    if goes_cmx and hybrid:
        leads = compute_lead_time(hybrid, goes_cmx)
        if leads:
            print(f"  Hybrid lead times:")
            for l in leads:
                print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")
            pos_leads = [l['lead_time_min'] for l in leads if l['lead_time_min'] > 0]
            if pos_leads:
                print(f"  Average lead: {np.mean(pos_leads):.1f} min")

    return results


# ============================================================
# 5. MAIN — RUN ALL DUAL-INSTRUMENT DAYS
# ============================================================

def main():
    dual_dates = [
        datetime(2024, 9, 14),
        datetime(2024, 10, 1),
        datetime(2024, 10, 3),
        datetime(2024, 10, 10),  # SoLEXS only — will skip
        datetime(2024, 11, 11),
        datetime(2024, 11, 14),
        datetime(2026, 2, 1),
        datetime(2026, 2, 4),
        datetime(2026, 4, 24),
        datetime(2026, 6, 3),
    ]

    print("=" * 70)
    print("MULTI-DAY DETECTION TEST — v3")
    print("=" * 70)

    all_results = {}
    for date in dual_dates:
        r = run_day(date)
        if r:
            all_results[date.strftime('%Y-%m-%d')] = r

    # Aggregate
    print("\n" + "=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)

    method_names = ['SoLEXS threshold', 'Hardening', 'CdTe 5-20', 'CZT 40-60', 'AND-gate', 'Combined', 'Hybrid']

    print(f"\n  {'Method':20s} {'Days':>4s} {'Det':>5s} {'TP':>5s} {'Miss':>5s} {'FA':>5s} {'TPR':>7s} {'FAR':>7s}")
    print(f"  {'-'*62}")

    for mname in method_names:
        tot_det = tot_tp = tot_miss = tot_fa = tot_flares = 0
        n_days = 0
        for date_str, day_results in all_results.items():
            if mname in day_results:
                r = day_results[mname]
                tot_det += r['det']
                tot_tp += r['tp']
                tot_miss += r['miss']
                tot_fa += r['fa']
                tot_flares += r['n_flares']
                n_days += 1

        tpr = tot_tp / max(tot_flares, 1) * 100
        far = tot_fa / max(tot_det, 1) * 100
        print(f"  {mname:20s} {n_days:4d} {tot_det:5d} {tot_tp:5d} {tot_miss:5d} {tot_fa:5d} {tpr:6.1f}% {far:6.1f}%")

    tot_flares = sum(r.get('Combined', {}).get('n_flares', 0) for r in all_results.values())
    print(f"\n  Total GOES flares across all days: {tot_flares}")

    # Per-class TPR for Combined method
    print(f"\n  Hybrid method — per-class TPR:")
    for cls in ['C', 'M', 'X']:
        tp_cls = sum(r.get(f'_tpr_{cls}', (0, 0))[0] for r in all_results.values())
        n_cls = sum(r.get(f'_tpr_{cls}', (0, 0))[1] for r in all_results.values())
        if n_cls:
            print(f"    {cls}-class: {tp_cls}/{n_cls} = {tp_cls/n_cls*100:.1f}%")

    # Classification accuracy aggregate
    tot_correct = sum(r.get('_class_correct', 0) for r in all_results.values())
    tot_classified = sum(r.get('_class_total', 0) for r in all_results.values())
    if tot_classified:
        print(f"\n  Hybrid classification accuracy: {tot_correct}/{tot_classified} = {tot_correct/tot_classified*100:.1f}%")


if __name__ == "__main__":
    main()
