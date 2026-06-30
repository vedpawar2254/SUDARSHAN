"""
Detection prototype v3 — Oct 3, 2024
v3 fixes: merge nearby detections (15 min), raise thresholds,
calibrated class bins, combined best method.
"""

import numpy as np
from astropy.io import fits
import netCDF4 as nc
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import glob, os

# ============================================================
# 0. UTILITY: MERGE NEARBY DETECTIONS
# ============================================================

def merge_nearby(detections, merge_window_min=12, time_key='time_hrs', peak_key='peak_counts'):
    """Merge detections within merge_window_min. Keep highest peak."""
    if not detections:
        return []
    sorted_dets = sorted(detections, key=lambda d: d.get(time_key) or d.get('onset_hrs', 0))
    merged = [sorted_dets[0].copy()]
    for d in sorted_dets[1:]:
        d_time = d.get(time_key) or d.get('onset_hrs', 0)
        m_time = merged[-1].get(time_key) or merged[-1].get('onset_hrs', 0)
        if abs(d_time - m_time) * 60 < merge_window_min:
            # Keep the one with higher peak
            d_peak = d.get(peak_key, d.get('peak_ctr', d.get('peak_hardness', 0)))
            m_peak = merged[-1].get(peak_key, merged[-1].get('peak_ctr', merged[-1].get('peak_hardness', 0)))
            if d_peak > m_peak:
                merged[-1] = d.copy()
        else:
            merged.append(d.copy())
    return merged


# Calibrated SoLEXS count thresholds (from GOES cross-calibration)
# C1.0 ≈ 33 counts, M1.0 ≈ 327 counts, X1.0 ≈ 3275 counts
# X threshold raised to 4000 — M6.7 has 4382 counts, causes misclass at 3275
CLASS_THRESHOLDS = {'C': 33, 'M': 327, 'X': 4000}

def classify_by_counts(peak_counts):
    """Classify flare by SoLEXS peak counts using calibrated thresholds."""
    if peak_counts >= CLASS_THRESHOLDS['X']:
        return 'X'
    elif peak_counts >= CLASS_THRESHOLDS['M']:
        return 'M'
    elif peak_counts >= CLASS_THRESHOLDS['C']:
        return 'C'
    else:
        return 'B'


# ============================================================
# 1. LOAD GOES GROUND TRUTH
# ============================================================

def load_goes_flares_oct3():
    """Load GOES flare catalog entries for Oct 3, 2024. Dedup G16/G18."""
    base = datetime(2000, 1, 1, 12, 0, 0)
    oct3_start = (datetime(2024, 10, 3, 0, 0) - base).total_seconds()
    oct3_end = (datetime(2024, 10, 4, 0, 0) - base).total_seconds()

    flares = []
    for catalog in glob.glob("data/goes_flares/sci_xrsf-l2-flsum_*.nc"):
        ds = nc.Dataset(catalog)
        time_data = ds.variables['time'][:]
        flare_class = ds.variables['flare_class'][:]
        xrsb = ds.variables['xrsb_flux'][:]

        mask = (time_data >= oct3_start) & (time_data < oct3_end)
        for i in np.where(mask)[0]:
            fc = str(flare_class[i]).strip()
            if not fc or fc == '--':
                continue
            if fc[0] in ('C', 'M', 'X'):
                t = base + timedelta(seconds=float(time_data[i]))
                flares.append({
                    'time': t,
                    'utc_hours': t.hour + t.minute / 60 + t.second / 3600,
                    'class': fc,
                    'peak_flux': float(xrsb[i]),
                })
        ds.close()

    # Dedup: merge entries within ±3 min, keep higher flux
    flares.sort(key=lambda x: x['utc_hours'])
    deduped = []
    for f in flares:
        if deduped and abs(f['utc_hours'] - deduped[-1]['utc_hours']) * 60 < 3:
            if f['peak_flux'] > deduped[-1]['peak_flux']:
                deduped[-1] = f
        else:
            deduped.append(f)

    return deduped


def load_goes_flux_oct3():
    """Load GOES 1-min XRS flux for Oct 3, 2024."""
    base = datetime(2000, 1, 1, 12, 0, 0)
    oct3_start = (datetime(2024, 10, 3, 0, 0) - base).total_seconds()
    oct3_end = (datetime(2024, 10, 4, 0, 0) - base).total_seconds()

    for gfile in glob.glob("data/goes/sci_xrsf-l2-avg1m_g18_y2024*.nc"):
        ds = nc.Dataset(gfile)
        time_data = ds.variables['time'][:]
        xrsb = ds.variables['xrsb_flux'][:]
        mask = (time_data >= oct3_start) & (time_data < oct3_end)
        t_hrs = (time_data[mask] - oct3_start) / 3600
        flux = xrsb[mask]
        ds.close()
        return t_hrs, flux
    return None, None


# ============================================================
# 2. LOAD SOLEXS DATA
# ============================================================

def load_solexs_oct3():
    """Load SoLEXS SDD2 light curve and spectra for Oct 3."""
    with fits.open("data/AL1_SLX_L1_20241003_v1.0/SDD2/AL1_SOLEXS_20241003_SDD2_L1.lc") as f:
        time_unix = f[1].data['TIME']
        counts = f[1].data['COUNTS']

    t0 = time_unix[0]
    t_hrs = (time_unix - t0) / 3600

    with fits.open("data/AL1_SLX_L1_20241003_v1.0/SDD2/AL1_SOLEXS_20241003_SDD2_L1.pi") as f:
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
    }


# ============================================================
# 3. LOAD HEL1OS DATA
# ============================================================

def load_helios_oct3():
    """Load HEL1OS CdTe + CZT for both halves of Oct 3, stitched."""
    halves = sorted(glob.glob("data/helios/2024/10/03/HLS_*"))

    result = {}
    for band_name, detector, hdu_idx in [
        ('cdte_5_20', 'cdte', 1),
        ('cdte_20_30', 'cdte', 2),
        ('cdte_40_60', 'cdte', 4),
        ('cdte_full', 'cdte', 5),
        ('czt_20_40', 'czt', 1),
        ('czt_40_60', 'czt', 2),
        ('czt_60_80', 'czt', 3),
        ('czt_80_150', 'czt', 4),
        ('czt_full', 'czt', 5),
    ]:
        all_mjd, all_ctr = [], []
        for hdir in halves:
            fpath = os.path.join(hdir, detector, f"lightcurve_{detector}1.fits")
            if not os.path.exists(fpath):
                continue
            with fits.open(fpath) as f:
                all_mjd.append(f[hdu_idx].data['MJD'])
                all_ctr.append(f[hdu_idx].data['CTR'])

        mjd = np.concatenate(all_mjd)
        ctr = np.concatenate(all_ctr)
        order = np.argsort(mjd)
        mjd, ctr = mjd[order], ctr[order]
        base_mjd = int(mjd[0])
        t_hrs = (mjd - base_mjd) * 24

        result[band_name] = {'t_hrs': t_hrs, 'ctr': ctr}

    return result


# ============================================================
# 4. DETECTION ALGORITHMS
# ============================================================

def detect_solexs_threshold(t_hrs, counts, bg_window_sec=3600, threshold_factor=3.0,
                            min_peak_counts=200, min_prominence=100, min_distance_sec=300):
    """
    SoLEXS detection: rolling 5th-percentile background.
    Threshold = background * threshold_factor (multiplicative, not additive sigma).
    Min peak counts filters out noise bumps.
    """
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

    # Multiplicative threshold: peak must be N× above background
    threshold = bg_clean * threshold_factor

    # Find peaks
    peaks_idx, _ = find_peaks(c, height=min_peak_counts,
                               distance=min_distance_sec,
                               prominence=min_prominence)

    detections = []
    for p in peaks_idx:
        if c[p] > threshold[p] and valid[p]:
            detections.append({
                'time_hrs': t_hrs[p],
                'peak_counts': c[p],
                'background': bg_clean[p],
                'ratio': c[p] / max(bg_clean[p], 1),
                'method': 'slx_threshold',
            })

    return detections, threshold, bg_clean


def detect_solexs_hardening(spec_t_hrs, hardness, high_counts,
                            ratio_threshold=0.003, sustained_sec=20,
                            refractory_min=10, min_high_counts=5):
    """
    SoLEXS spectral hardening: relative rise above rolling baseline.
    Uses rolling median hardness as baseline, triggers on ratio_threshold above it.
    Refractory period prevents re-triggering on the same event.
    """
    valid = ~np.isnan(hardness)
    n = len(hardness)

    # Rolling baseline hardness (60 min, median of valid values)
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

    # Trigger: hardness exceeds baseline + ratio_threshold AND high_counts above min
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


def detect_helios_cdte(t_hrs, ctr, onset_threshold=50, sustained_sec=5,
                       refractory_min=10):
    """
    HEL1OS CdTe 5-20 keV onset detection for M-class.
    CdTe 5-20 sees M-class (160-1089 cps) while CZT can't.
    Must handle duty cycle (zeros).
    """
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
    """
    HEL1OS CZT 40-60 keV onset: X-class only trigger.
    Raised threshold to 50 (quiet max is ~29). Fewer sustained needed.
    """
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


def detect_helios_duty_cycle(t_hrs, ctr, window_sec=60, dc_threshold=0.40,
                             refractory_min=10):
    """
    Duty cycle jump on CdTe 5-20 keV.
    Quiet = ~20% nonzero. Flare = 50-100%.
    Trigger at 40% (2× quiet).
    """
    w = window_sec
    detections = []
    last_trigger_hrs = -999

    for i in range(w, len(ctr)):
        window = ctr[i - w:i]
        dc = (window > 0).sum() / len(window)

        if dc >= dc_threshold:
            onset_hrs = t_hrs[i]
            if (onset_hrs - last_trigger_hrs) * 60 < refractory_min:
                continue

            end = min(len(ctr), i + 1800)
            peak_idx = i + np.argmax(ctr[i:end])

            detections.append({
                'onset_hrs': onset_hrs,
                'peak_hrs': t_hrs[peak_idx],
                'peak_ctr': ctr[peak_idx],
                'duty_cycle': dc,
                'method': 'duty_cycle',
            })
            last_trigger_hrs = onset_hrs

    return detections


# ============================================================
# 5. MATCHING AND SCORING
# ============================================================

def match_detections(detections, goes_flares, window_min=10):
    """Match detections to GOES flares within window_min."""
    matched = []
    used_goes = set()
    used_det = set()

    # Sort detections by closeness to any GOES flare
    det_flare_pairs = []
    for i, det in enumerate(detections):
        det_time = det.get('time_hrs') or det.get('onset_hrs') or det.get('peak_hrs')
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
    """Lead time = GOES_peak - detection_onset. Positive = early."""
    used = set()
    results = []
    for det in detections:
        det_onset = det.get('onset_hrs') or det.get('time_hrs')

        best_j = None
        best_lead = None
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
                'goes_peak_hrs': goes_flares[best_j]['utc_hours'],
                'det_onset_hrs': det_onset,
                'lead_time_min': best_lead,
                'method': det['method'],
            })

    return results


# ============================================================
# 6. MAIN
# ============================================================

def main():
    print("=" * 70)
    print("DETECTION PROTOTYPE v2 — Oct 3, 2024")
    print("=" * 70)

    # Load ground truth
    goes_flares = load_goes_flares_oct3()
    goes_hrs, goes_flux = load_goes_flux_oct3()

    print(f"\nGOES ground truth: {len(goes_flares)} flares")
    for f in goes_flares:
        print(f"  {f['time'].strftime('%H:%M')} {f['class']:>6s}  peak={f['peak_flux']:.2e}")

    c_flares = [f for f in goes_flares if f['class'][0] == 'C']
    m_flares = [f for f in goes_flares if f['class'][0] == 'M']
    x_flares = [f for f in goes_flares if f['class'][0] == 'X']
    print(f"  Summary: {len(c_flares)}C + {len(m_flares)}M + {len(x_flares)}X")

    # Load instrument data
    print("\nLoading SoLEXS...")
    slx = load_solexs_oct3()
    print(f"  {len(slx['counts'])} samples, {(~np.isnan(slx['counts'])).sum()} valid")

    print("Loading HEL1OS...")
    hel = load_helios_oct3()
    cdte = hel['cdte_5_20']
    czt = hel['czt_40_60']
    print(f"  CdTe 5-20: {len(cdte['ctr'])} samples, {(cdte['ctr']>0).sum()} nonzero ({(cdte['ctr']>0).sum()/len(cdte['ctr'])*100:.1f}%)")
    print(f"  CZT 40-60: {len(czt['ctr'])} samples, {(czt['ctr']>0).sum()} nonzero ({(czt['ctr']>0).sum()/len(czt['ctr'])*100:.1f}%)")

    # ========================================
    # METHOD 1: SoLEXS threshold (3× background, min 200 cps)
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 1: SoLEXS threshold (peak > 3.5× rolling p5 background, min 200 cps)")
    print("=" * 70)

    slx_det_raw, _, background = detect_solexs_threshold(
        slx['t_hrs'], slx['counts'],
        bg_window_sec=3600, threshold_factor=3.5,
        min_peak_counts=200, min_prominence=100, min_distance_sec=600)
    slx_det = merge_nearby(slx_det_raw, merge_window_min=12, time_key='time_hrs', peak_key='peak_counts')

    print(f"  Detections: {len(slx_det)}")
    for d in slx_det:
        print(f"    {int(d['time_hrs'])}:{int((d['time_hrs']%1)*60):02d}  "
              f"peak={d['peak_counts']:.0f}  bg={d['background']:.0f}  ratio={d['ratio']:.1f}×")

    matched, fa, missed = match_detections(slx_det, goes_flares)
    print(f"\n  TPR: {len(matched)}/{len(goes_flares)} = {len(matched)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa)}/{len(slx_det)} = {len(fa)/max(len(slx_det),1)*100:.1f}%")
    if missed:
        print(f"  Missed:")
        for m in missed:
            print(f"    {m['time'].strftime('%H:%M')} {m['class']}")

    # ========================================
    # METHOD 2: SoLEXS spectral hardening (relative, with refractory)
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 2: SoLEXS spectral hardening (ratio > baseline + 0.003, 20s sustained, 10min refractory)")
    print("=" * 70)

    hard_det_raw = detect_solexs_hardening(
        slx['spec_t_hrs'], slx['hardness'], slx['high_counts'],
        ratio_threshold=0.003, sustained_sec=20, refractory_min=10, min_high_counts=5)
    hard_det = merge_nearby(hard_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_hardness')

    print(f"  Detections: {len(hard_det)}")
    for d in hard_det:
        print(f"    {int(d['onset_hrs'])}:{int((d['onset_hrs']%1)*60):02d}  "
              f"peak_ratio={d['peak_hardness']:.4f}  baseline={d['baseline_hardness']:.4f}")

    matched_h, fa_h, missed_h = match_detections(
        [{'time_hrs': d['onset_hrs'], **d} for d in hard_det], goes_flares)
    print(f"\n  TPR: {len(matched_h)}/{len(goes_flares)} = {len(matched_h)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa_h)}/{len(hard_det)} = {len(fa_h)/max(len(hard_det),1)*100:.1f}%")

    leads = compute_lead_time([{'time_hrs': d['onset_hrs'], **d} for d in hard_det], goes_flares)
    if leads:
        print(f"  Lead times:")
        for l in leads:
            print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")

    # ========================================
    # METHOD 3: CdTe 5-20 keV onset (M-class trigger)
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 3: CdTe 5-20 keV onset (threshold=75 cps, 5 sustained nonzero)")
    print("=" * 70)

    cdte_det_raw = detect_helios_cdte(cdte['t_hrs'], cdte['ctr'],
                                       onset_threshold=75, sustained_sec=5)
    cdte_det = merge_nearby(cdte_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    print(f"  Detections: {len(cdte_det)}")
    for d in cdte_det:
        print(f"    {int(d['onset_hrs'])}:{int((d['onset_hrs']%1)*60):02d}  "
              f"peak={d['peak_ctr']:.0f} cps")

    matched_cd, fa_cd, missed_cd = match_detections(
        [{'time_hrs': d['onset_hrs'], **d} for d in cdte_det], goes_flares)
    print(f"\n  TPR: {len(matched_cd)}/{len(goes_flares)} = {len(matched_cd)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa_cd)}/{len(cdte_det)} = {len(fa_cd)/max(len(cdte_det),1)*100:.1f}%")

    leads = compute_lead_time([{'time_hrs': d['onset_hrs'], **d} for d in cdte_det], goes_flares)
    if leads:
        print(f"  Lead times:")
        for l in leads:
            print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")

    # ========================================
    # METHOD 4: CZT 40-60 keV onset (X-class trigger)
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 4: CZT 40-60 keV onset (threshold=50 cps, X-class only)")
    print("=" * 70)

    czt_det_raw = detect_helios_czt(czt['t_hrs'], czt['ctr'],
                                     onset_threshold=50, sustained_sec=3)
    czt_det = merge_nearby(czt_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    print(f"  Detections: {len(czt_det)}")
    for d in czt_det:
        print(f"    {int(d['onset_hrs'])}:{int((d['onset_hrs']%1)*60):02d}  "
              f"peak={d['peak_ctr']:.0f} cps")

    matched_cz, fa_cz, missed_cz = match_detections(
        [{'time_hrs': d['onset_hrs'], **d} for d in czt_det], goes_flares)
    print(f"\n  TPR (all): {len(matched_cz)}/{len(goes_flares)}")
    print(f"  FAR: {len(fa_cz)}/{len(czt_det)} = {len(fa_cz)/max(len(czt_det),1)*100:.1f}%")

    leads = compute_lead_time([{'time_hrs': d['onset_hrs'], **d} for d in czt_det], goes_flares)
    if leads:
        print(f"  Lead times:")
        for l in leads:
            print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")

    # ========================================
    # METHOD 5: CdTe duty cycle jump
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 5: CdTe 5-20 duty cycle jump (>40% nonzero in 60s window)")
    print("=" * 70)

    dc_det_raw = detect_helios_duty_cycle(cdte['t_hrs'], cdte['ctr'],
                                           window_sec=60, dc_threshold=0.40)
    dc_det = merge_nearby(dc_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    print(f"  Detections: {len(dc_det)}")
    for d in dc_det:
        print(f"    {int(d['onset_hrs'])}:{int((d['onset_hrs']%1)*60):02d}  "
              f"DC={d['duty_cycle']:.0%}  peak={d['peak_ctr']:.0f}")

    matched_dc, fa_dc, missed_dc = match_detections(
        [{'time_hrs': d['onset_hrs'], **d} for d in dc_det], goes_flares)
    print(f"\n  TPR: {len(matched_dc)}/{len(goes_flares)} = {len(matched_dc)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa_dc)}/{len(dc_det)} = {len(fa_dc)/max(len(dc_det),1)*100:.1f}%")

    leads = compute_lead_time([{'time_hrs': d['onset_hrs'], **d} for d in dc_det], goes_flares)
    if leads:
        print(f"  Lead times:")
        for l in leads:
            print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")

    # ========================================
    # METHOD 6: AND-gate (SoLEXS + CdTe within 5 min)
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 6: AND-gate (SoLEXS threshold + CdTe 5-20 onset within 5 min)")
    print("=" * 70)

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

    and_deduped = merge_nearby(and_detections, merge_window_min=12, time_key='time_hrs', peak_key='slx_peak')

    matched_and, fa_and, missed_and = match_detections(and_deduped, goes_flares)
    print(f"  AND-gate detections: {len(and_deduped)}")
    for d in and_deduped:
        print(f"    {int(d['time_hrs'])}:{int((d['time_hrs']%1)*60):02d}  "
              f"SoLEXS={d['slx_peak']:.0f}  CdTe={d['cdte_peak']:.0f}")
    print(f"\n  TPR: {len(matched_and)}/{len(goes_flares)} = {len(matched_and)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa_and)}/{len(and_deduped)} = {len(fa_and)/max(len(and_deduped),1)*100:.1f}%")

    # ========================================
    # METHOD 7: Calibrated classification (count-based)
    # C<327, M=327-3275, X>3275 SoLEXS counts
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 7: Calibrated classification (SoLEXS counts → C/M/X)")
    print("=" * 70)

    classified = []
    for sd in slx_det:
        pred_class = classify_by_counts(sd['peak_counts'])
        classified.append({
            'time_hrs': sd['time_hrs'],
            'pred_class': pred_class,
            'peak_counts': sd['peak_counts'],
            'method': 'classified',
        })

    print(f"  Classified detections: {len(classified)}")
    for d in classified:
        print(f"    {int(d['time_hrs'])}:{int((d['time_hrs']%1)*60):02d}  "
              f"class={d['pred_class']}  peak={d['peak_counts']:.0f}")

    matched_cl, fa_cl, missed_cl = match_detections(classified, goes_flares)
    print(f"\n  TPR: {len(matched_cl)}/{len(goes_flares)} = {len(matched_cl)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa_cl)}/{len(classified)} = {len(fa_cl)/max(len(classified),1)*100:.1f}%")

    correct_class = 0
    for det, flare, dt in matched_cl:
        actual = flare['class'][0]
        predicted = det['pred_class']
        match_str = "OK" if actual == predicted else f"WRONG (predicted {predicted})"
        print(f"    {flare['class']:>6s} → {predicted}  {match_str}")
        if actual == predicted:
            correct_class += 1
    print(f"  Class accuracy: {correct_class}/{len(matched_cl)} = {correct_class/max(len(matched_cl),1)*100:.1f}%")

    # ========================================
    # METHOD 8: Combined best — hardening trigger + CdTe confirm + calibrated class
    # Primary: spectral hardening (earliest, best TPR)
    # Confirm M+: CdTe 5-20 within 5 min
    # Confirm X: CZT 40-60 within 5 min
    # Classify: SoLEXS peak counts (calibrated)
    # ========================================
    print("\n" + "=" * 70)
    print("METHOD 8: Combined (hardening trigger → CdTe/CZT confirm → calibrated class)")
    print("=" * 70)

    combined = []
    for hd in hard_det:
        onset = hd.get('onset_hrs', hd.get('time_hrs', 0))

        # Find matching SoLEXS threshold detection for peak counts
        # Hardening fires at onset, SoLEXS threshold fires at peak — can be 15+ min apart
        # Search FORWARD from onset up to 20 min
        best_slx = None
        for sd in slx_det_raw:  # use raw (unmerged) for best peak match
            dt_min = (sd['time_hrs'] - onset) * 60
            if -5 < dt_min < 20:  # allow 5 min before to 20 min after onset
                if best_slx is None or sd['peak_counts'] > best_slx['peak_counts']:
                    best_slx = sd

        if best_slx:
            peak_counts = best_slx['peak_counts']
        else:
            # No threshold detection — look up raw SoLEXS counts near onset
            onset_idx = np.argmin(np.abs(slx['t_hrs'] - onset))
            end_idx = min(len(slx['counts']), onset_idx + 1200)  # 20 min forward
            window = slx['counts'][onset_idx:end_idx]
            valid_window = window[~np.isnan(window)]
            peak_counts = float(np.max(valid_window)) if len(valid_window) > 0 else 0
        pred_class = classify_by_counts(peak_counts)

        # CdTe confirmation?
        cdte_confirmed = False
        for cd in cdte_det:
            cd_time = cd.get('onset_hrs', cd.get('time_hrs', 0))
            if abs(cd_time - onset) * 60 < 5:
                cdte_confirmed = True
                break

        # CZT confirmation?
        czt_confirmed = False
        for cz in czt_det:
            cz_time = cz.get('onset_hrs', cz.get('time_hrs', 0))
            if abs(cz_time - onset) * 60 < 5:
                czt_confirmed = True
                break

        confidence = 'LOW'
        if pred_class in ('M', 'X') and cdte_confirmed:
            confidence = 'MED'
        if pred_class == 'X' and czt_confirmed:
            confidence = 'HIGH'
        if pred_class in ('C', 'B'):
            confidence = 'MED'  # SoLEXS-only is fine for C-class

        combined.append({
            'time_hrs': onset,
            'onset_hrs': onset,
            'pred_class': pred_class,
            'peak_counts': peak_counts,
            'cdte_confirmed': cdte_confirmed,
            'czt_confirmed': czt_confirmed,
            'confidence': confidence,
            'method': 'combined',
        })

    print(f"  Combined detections: {len(combined)}")
    for d in combined:
        conf_str = ""
        if d['cdte_confirmed']:
            conf_str += " +CdTe"
        if d['czt_confirmed']:
            conf_str += " +CZT"
        print(f"    {int(d['time_hrs'])}:{int((d['time_hrs']%1)*60):02d}  "
              f"class={d['pred_class']}  peak={d['peak_counts']:.0f}  "
              f"conf={d['confidence']}{conf_str}")

    matched_comb, fa_comb, missed_comb = match_detections(combined, goes_flares)
    print(f"\n  TPR: {len(matched_comb)}/{len(goes_flares)} = {len(matched_comb)/len(goes_flares)*100:.1f}%")
    print(f"  FAR: {len(fa_comb)}/{len(combined)} = {len(fa_comb)/max(len(combined),1)*100:.1f}%")

    correct_comb = 0
    for det, flare, dt in matched_comb:
        actual = flare['class'][0]
        predicted = det['pred_class']
        match_str = "OK" if actual == predicted else f"WRONG (predicted {predicted})"
        print(f"    {flare['class']:>6s} → {predicted}  conf={det['confidence']}  {match_str}")
        if actual == predicted:
            correct_comb += 1
    print(f"  Class accuracy: {correct_comb}/{len(matched_comb)} = {correct_comb/max(len(matched_comb),1)*100:.1f}%")

    leads = compute_lead_time(combined, goes_flares)
    if leads:
        print(f"  Lead times:")
        for l in leads:
            print(f"    {l['goes_class']:>6s}: {l['lead_time_min']:+.1f} min")
        avg_lead = np.mean([l['lead_time_min'] for l in leads if l['lead_time_min'] > 0])
        print(f"  Average lead (positive): {avg_lead:.1f} min")

    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 70)
    print("SUMMARY — Oct 3, 2024")
    print("=" * 70)
    print(f"Ground truth: {len(c_flares)}C + {len(m_flares)}M + {len(x_flares)}X = {len(goes_flares)} flares\n")

    all_methods = [
        ("SoLEXS threshold (3.5×bg)", slx_det),
        ("SoLEXS hardening", [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in hard_det]),
        ("CdTe 5-20 onset", [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in cdte_det]),
        ("CZT 40-60 onset", [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in czt_det]),
        ("CdTe duty cycle", [{'time_hrs': d.get('onset_hrs', d.get('time_hrs')), **d} for d in dc_det]),
        ("AND-gate (SLX+CdTe)", and_deduped),
        ("Calibrated class", classified),
        ("Combined best", combined),
    ]

    print(f"{'Method':28s} {'Det':>4s} {'Match':>6s} {'Miss':>6s} {'FA':>4s} {'TPR':>7s} {'FAR':>7s}")
    print("-" * 70)
    for name, dets in all_methods:
        m, fa, mi = match_detections(dets, goes_flares)
        tpr = len(m) / len(goes_flares) * 100
        far = len(fa) / max(len(dets), 1) * 100
        print(f"  {name:26s} {len(dets):4d} {len(m):6d} {len(mi):6d} {len(fa):4d} {tpr:6.1f}% {far:6.1f}%")


if __name__ == "__main__":
    main()
