"""
ML Experiments for SUDARSHAN
#1: XGBoost false-alarm classifier (reduce FAR from 31.6%)
#3: Spectral autoencoder for pre-flare anomaly detection
"""

import numpy as np
import os, glob
from datetime import datetime, timedelta
from astropy.io import fits
from scipy.signal import find_peaks
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix
import xgboost as xgb

# Import existing pipeline
from prototype_multiday import (
    load_goes_flares, load_solexs, load_helios,
    detect_solexs_threshold, detect_solexs_hardening,
    detect_helios_cdte, detect_helios_czt,
    merge_nearby, classify_by_counts, match_detections,
    CLASS_THRESHOLDS_BG_SUB,
)

DUAL_DATES = [
    datetime(2024, 9, 14),
    datetime(2024, 10, 1),
    datetime(2024, 10, 3),
    datetime(2024, 11, 11),
    datetime(2024, 11, 14),
    datetime(2026, 2, 1),
    datetime(2026, 2, 4),
    datetime(2026, 4, 24),
    datetime(2026, 6, 3),
]

# ============================================================
# EXPERIMENT 1: XGBoost False-Alarm Classifier
# ============================================================

def extract_features_one_day(date):
    """Run detection on one day, extract rich features per detection, label TP/FA."""
    slx = load_solexs(date)
    hel = load_helios(date)
    goes_flares = load_goes_flares(date)
    goes_cmx = [f for f in goes_flares if f['class'][0] in ('C', 'M', 'X')]

    if slx is None or hel is None:
        return [], []

    cdte = hel.get('cdte_5_20')
    czt = hel.get('czte_40_60')

    # Run detectors
    slx_det_raw, background = detect_solexs_threshold(slx['t_hrs'], slx['counts'])
    slx_det = merge_nearby(slx_det_raw, merge_window_min=12, time_key='time_hrs',
                           peak_key='peak_counts', adaptive=True)

    hard_det_raw = detect_solexs_hardening(slx['spec_t_hrs'], slx['hardness'], slx['high_counts'],
                                           ratio_threshold=0.002, sustained_sec=15, min_high_counts=2)
    hard_det = merge_nearby(hard_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_hardness')

    cdte_det = []
    if cdte is not None:
        cdte_det_raw = detect_helios_cdte(cdte['t_hrs'], cdte['ctr'])
        cdte_det = merge_nearby(cdte_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    czt_det = []
    if czt is not None:
        czt_det_raw = detect_helios_czt(czt['t_hrs'], czt['ctr'])
        czt_det = merge_nearby(czt_det_raw, merge_window_min=12, time_key='onset_hrs', peak_key='peak_ctr')

    # Extract features for each SoLEXS detection
    features = []
    for sd in slx_det:
        sd_time = sd['time_hrs']
        peak_counts = sd['peak_counts']
        bg = sd.get('background', 0)
        net = peak_counts - bg
        ratio = sd.get('ratio', peak_counts / max(bg, 1))
        sustained = sd.get('sustained_sec', 0)

        # Rise rate: counts increase per second in 60s before peak
        peak_idx = np.argmin(np.abs(slx['t_hrs'] - sd_time))
        start_idx = max(0, peak_idx - 60)
        valid_window = slx['counts'][start_idx:peak_idx]
        valid_window = valid_window[~np.isnan(valid_window)]
        if len(valid_window) > 5:
            rise_rate = (valid_window[-1] - valid_window[0]) / max(len(valid_window), 1)
        else:
            rise_rate = 0

        # Decay rate: counts decrease per second in 60s after peak
        end_idx = min(len(slx['counts']), peak_idx + 60)
        decay_window = slx['counts'][peak_idx:end_idx]
        decay_window = decay_window[~np.isnan(decay_window)]
        if len(decay_window) > 5:
            decay_rate = (decay_window[0] - decay_window[-1]) / max(len(decay_window), 1)
        else:
            decay_rate = 0

        # Peak width at half prominence
        if peak_idx > 10 and peak_idx < len(slx['counts']) - 10:
            half_level = bg + net / 2
            c = np.where(~np.isnan(slx['counts']), slx['counts'], 0).astype(float)
            # Count seconds above half level around peak
            above_half = 0
            for di in range(-300, 300):
                idx = peak_idx + di
                if 0 <= idx < len(c) and c[idx] > half_level:
                    above_half += 1
            peak_width_sec = above_half
        else:
            peak_width_sec = 0

        # Hardening confirmation
        hardening_confirmed = 0
        hardness_delta = 0
        for hd in hard_det:
            hd_time = hd.get('onset_hrs', hd.get('time_hrs', 0))
            if abs(hd_time - sd_time) * 60 < 10:
                hardening_confirmed = 1
                hardness_delta = hd.get('peak_hardness', 0) - hd.get('baseline_hardness', 0)
                break

        # CdTe confirmation + peak counts
        cdte_confirmed = 0
        cdte_peak = 0
        for cd in cdte_det:
            cd_time = cd.get('onset_hrs', cd.get('time_hrs', 0))
            if abs(cd_time - sd_time) * 60 < 5:
                cdte_confirmed = 1
                cdte_peak = cd.get('peak_ctr', 0)
                break

        # CZT confirmation
        czt_confirmed = 0
        czt_peak = 0
        for cz in czt_det:
            cz_time = cz.get('onset_hrs', cz.get('time_hrs', 0))
            if abs(cz_time - sd_time) * 60 < 5:
                czt_confirmed = 1
                czt_peak = cz.get('peak_ctr', 0)
                break

        # Spectral hardness at peak time (from spectra)
        peak_hardness = 0
        if slx['spec_t_hrs'] is not None and slx['hardness'] is not None:
            spec_idx = np.argmin(np.abs(slx['spec_t_hrs'] - sd_time))
            if not np.isnan(slx['hardness'][spec_idx]):
                peak_hardness = slx['hardness'][spec_idx]

        pred_class = classify_by_counts(peak_counts, bg)

        feat = {
            'time_hrs': sd_time,
            'date': date.strftime('%Y-%m-%d'),
            # Core features
            'peak_counts': peak_counts,
            'background': bg,
            'net_counts': net,
            'ratio': ratio,
            'log_ratio': np.log10(max(ratio, 1.01)),
            'sustained_sec': sustained,
            'rise_rate': rise_rate,
            'decay_rate': decay_rate,
            'peak_width_sec': peak_width_sec,
            # Cross-instrument features
            'hardening_confirmed': hardening_confirmed,
            'hardness_delta': hardness_delta,
            'cdte_confirmed': cdte_confirmed,
            'cdte_peak': cdte_peak,
            'czt_confirmed': czt_confirmed,
            'czt_peak': czt_peak,
            # Spectral
            'peak_hardness': peak_hardness,
            # Metadata
            'pred_class': pred_class,
        }
        features.append(feat)

    # Label: match against GOES
    labels = []
    matched, unmatched, missed = match_detections(
        [{'time_hrs': f['time_hrs'], **f} for f in features],
        goes_cmx
    )

    matched_times = set()
    matched_goes_classes = {}
    for det, flare, dt in matched:
        matched_times.add(det['time_hrs'])
        matched_goes_classes[det['time_hrs']] = flare['class']

    for feat in features:
        is_tp = feat['time_hrs'] in matched_times
        feat['label'] = 1 if is_tp else 0  # 1=real flare, 0=false alarm
        feat['goes_class'] = matched_goes_classes.get(feat['time_hrs'], '')

    return features, goes_cmx


def run_experiment_1():
    """XGBoost false-alarm classifier with leave-one-day-out CV."""
    print("=" * 70)
    print("EXPERIMENT 1: XGBoost False-Alarm Classifier")
    print("=" * 70)

    # Collect features from all days
    all_features = []
    for date in DUAL_DATES:
        datestr = date.strftime('%Y-%m-%d')
        feats, goes = extract_features_one_day(date)
        n_tp = sum(1 for f in feats if f['label'] == 1)
        n_fa = sum(1 for f in feats if f['label'] == 0)
        print(f"  {datestr}: {len(feats)} detections ({n_tp} TP, {n_fa} FA), {len(goes)} GOES flares")
        all_features.extend(feats)

    n_tp_total = sum(1 for f in all_features if f['label'] == 1)
    n_fa_total = sum(1 for f in all_features if f['label'] == 0)
    print(f"\n  Total: {len(all_features)} detections ({n_tp_total} TP, {n_fa_total} FA)")

    # Feature matrix
    feature_cols = [
        'net_counts', 'ratio', 'log_ratio', 'sustained_sec',
        'rise_rate', 'decay_rate', 'peak_width_sec',
        'hardening_confirmed', 'hardness_delta',
        'cdte_confirmed', 'cdte_peak',
        'czt_confirmed', 'czt_peak',
        'peak_hardness',
    ]

    X = np.array([[f[c] for c in feature_cols] for f in all_features])
    y = np.array([f['label'] for f in all_features])
    dates = np.array([f['date'] for f in all_features])

    print(f"\n  Feature matrix: {X.shape}")
    print(f"  Features: {feature_cols}")

    # Leave-one-day-out cross-validation
    unique_dates = sorted(set(dates))
    print(f"\n  Leave-one-day-out CV ({len(unique_dates)} folds):")

    all_preds = np.zeros(len(y), dtype=int)
    all_probs = np.zeros(len(y))

    for test_date in unique_dates:
        test_mask = dates == test_date
        train_mask = ~test_mask

        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        if len(X_test) == 0 or len(np.unique(y_train)) < 2:
            continue

        # XGBoost with class balancing
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        scale = n_neg / max(n_pos, 1)

        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            scale_pos_weight=scale,
            random_state=42,
            eval_metric='logloss',
        )
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)[:, 1]
        all_preds[test_mask] = preds
        all_probs[test_mask] = probs

        tp_test = ((preds == 1) & (y_test == 1)).sum()
        fa_kept = ((preds == 1) & (y_test == 0)).sum()
        fa_killed = ((preds == 0) & (y_test == 0)).sum()
        tp_lost = ((preds == 0) & (y_test == 1)).sum()
        print(f"    {test_date}: TP kept={tp_test}, TP lost={tp_lost}, FA killed={fa_killed}, FA kept={fa_kept}")

    # Sweep probability thresholds to find best operating point
    print(f"\n  Probability threshold sweep:")
    print(f"  {'Thresh':>7s} {'TP kept':>8s} {'TP lost':>8s} {'FA kill':>8s} {'FA kept':>8s} {'TPR':>7s} {'FAR':>7s}")
    best_thresh = 0.5
    best_score = -1
    for thresh in [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]:
        t_preds = (all_probs >= thresh).astype(int)
        t_tp = ((t_preds == 1) & (y == 1)).sum()
        t_tl = ((t_preds == 0) & (y == 1)).sum()
        t_fk = ((t_preds == 0) & (y == 0)).sum()
        t_fa = ((t_preds == 1) & (y == 0)).sum()
        t_tpr = t_tp / max(n_tp_total, 1) * 100
        t_far = t_fa / max(t_tp + t_fa, 1) * 100
        # Score: maximize TPR while minimizing FAR (TSS-like)
        score = t_tpr - t_far
        if score > best_score:
            best_score = score
            best_thresh = thresh
        print(f"  {thresh:7.2f} {t_tp:8d} {t_tl:8d} {t_fk:8d} {t_fa:8d} {t_tpr:6.1f}% {t_far:6.1f}%")

    print(f"\n  Best threshold: {best_thresh} (score={best_score:.1f})")

    # Use best threshold for final results
    final_preds = (all_probs >= best_thresh).astype(int)

    print(f"\n  Overall CV Results (threshold={best_thresh}):")
    tp_kept = ((final_preds == 1) & (y == 1)).sum()
    tp_lost = ((final_preds == 0) & (y == 1)).sum()
    fa_killed = ((final_preds == 0) & (y == 0)).sum()
    fa_kept = ((final_preds == 1) & (y == 0)).sum()

    total_kept = tp_kept + fa_kept
    new_tpr = tp_kept / max(n_tp_total, 1) * 100
    new_far = fa_kept / max(total_kept, 1) * 100
    old_far = n_fa_total / max(len(all_features), 1) * 100

    print(f"    TP kept:   {tp_kept}/{n_tp_total} ({new_tpr:.1f}%)")
    print(f"    TP lost:   {tp_lost}")
    print(f"    FA killed: {fa_killed}/{n_fa_total}")
    print(f"    FA kept:   {fa_kept}")
    print(f"    Old FAR:   {old_far:.1f}%")
    print(f"    New FAR:   {new_far:.1f}%")
    print(f"    FAR reduction: {old_far:.1f}% -> {new_far:.1f}%")

    # Feature importance (train on all data for this)
    model_full = xgb.XGBClassifier(
        n_estimators=100, max_depth=3, learning_rate=0.1,
        scale_pos_weight=n_fa_total / max(n_tp_total, 1),
        random_state=42, eval_metric='logloss',
    )
    model_full.fit(X, y)

    print(f"\n  Feature importance (gain):")
    importances = model_full.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    for idx in sorted_idx:
        print(f"    {feature_cols[idx]:25s}: {importances[idx]:.4f}")

    # Per-class analysis at best threshold
    print(f"\n  Per-class TP retention (thresh={best_thresh}):")
    for cls in ['C', 'M', 'X']:
        cls_mask = np.array([f['goes_class'].startswith(cls) for f in all_features])
        tp_mask = (y == 1) & cls_mask
        if tp_mask.sum() > 0:
            kept = ((final_preds == 1) & tp_mask).sum()
            total = tp_mask.sum()
            print(f"    {cls}-class: {kept}/{total} kept ({kept/total*100:.0f}%)")

    return {
        'tp_kept': int(tp_kept), 'tp_lost': int(tp_lost),
        'fa_killed': int(fa_killed), 'fa_kept': int(fa_kept),
        'old_far': old_far, 'new_far': new_far, 'new_tpr': new_tpr,
        'feature_importance': dict(zip(feature_cols, importances.tolist())),
    }


# ============================================================
# EXPERIMENT 3: Spectral Autoencoder for Pre-Flare Anomaly
# ============================================================

def load_spectra_for_date(date):
    """Load full 340-channel spectra for a date, return (times_hrs, spectra_matrix)."""
    datestr = date.strftime('%Y%m%d')
    pi_pattern = f"data/AL1_SLX_L1_{datestr}_*/SDD2/*.pi"
    pi_files = glob.glob(pi_pattern)
    if not pi_files:
        return None, None, None

    # Also load LC for time reference
    lc_pattern = f"data/AL1_SLX_L1_{datestr}_*/SDD2/*.lc"
    lc_files = glob.glob(lc_pattern)
    t0 = None
    if lc_files:
        with fits.open(lc_files[0]) as f:
            t0 = f[1].data['TIME'][0]

    with fits.open(pi_files[0]) as f:
        d = f[1].data
        spec_time = d['TSTART']
        if t0 is not None:
            t_hrs = (spec_time - t0) / 3600
        else:
            t_hrs = (spec_time - spec_time[0]) / 3600

        n = len(d)
        n_channels = len(d['COUNTS'][0])
        spectra = np.zeros((n, n_channels))
        for i in range(n):
            spectra[i] = d['COUNTS'][i]

    return t_hrs, spectra, t0


def run_experiment_3():
    """Spectral autoencoder for pre-flare anomaly detection."""
    from sklearn.neural_network import MLPRegressor

    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Spectral Autoencoder for Pre-Flare Anomaly Detection")
    print("=" * 70)

    # Step 1: Collect quiet vs flare spectra across all days
    quiet_spectra = []
    flare_windows = []  # (date, start_hrs, peak_hrs, class)

    for date in DUAL_DATES:
        datestr = date.strftime('%Y-%m-%d')
        t_hrs, spectra, t0 = load_spectra_for_date(date)
        if t_hrs is None:
            print(f"  {datestr}: no spectral data")
            continue

        goes_flares = load_goes_flares(date)
        goes_cmx = [f for f in goes_flares if f['class'][0] in ('C', 'M', 'X')]

        print(f"  {datestr}: {len(spectra)} spectra, {spectra.shape[1]} channels, {len(goes_cmx)} flares")

        # Mark flare periods (15 min before to 30 min after each flare)
        is_flare = np.zeros(len(t_hrs), dtype=bool)
        for flare in goes_cmx:
            flare_hrs = flare['utc_hours']
            mask = (t_hrs > flare_hrs - 0.25) & (t_hrs < flare_hrs + 0.5)
            is_flare |= mask
            flare_windows.append({
                'date': datestr,
                'peak_hrs': flare_hrs,
                'class': flare['class'],
                't_hrs': t_hrs,
                'spectra': spectra,
            })

        # Quiet spectra: not during flares, not NaN-heavy
        for i in range(len(spectra)):
            if not is_flare[i] and np.sum(spectra[i]) > 10:  # not empty
                quiet_spectra.append(spectra[i])

    quiet_spectra = np.array(quiet_spectra)
    print(f"\n  Quiet spectra collected: {quiet_spectra.shape}")

    # Step 2: Normalize — log1p then standardize per channel
    quiet_log = np.log1p(quiet_spectra)
    channel_mean = quiet_log.mean(axis=0)
    channel_std = quiet_log.std(axis=0)
    channel_std[channel_std < 1e-6] = 1  # avoid div/0

    quiet_norm = (quiet_log - channel_mean) / channel_std

    # Use channels 5-300 (skip dead/noisy edges)
    ch_start, ch_end = 5, 300
    n_features = ch_end - ch_start
    quiet_input = quiet_norm[:, ch_start:ch_end].astype(np.float64)
    quiet_input = np.nan_to_num(quiet_input, nan=0.0, posinf=0.0, neginf=0.0)

    print(f"  Using channels {ch_start}-{ch_end} ({n_features} features)")
    print(f"  Training autoencoder on {len(quiet_input)} quiet spectra...")

    # Step 3: MLPRegressor as autoencoder (input=output, bottleneck in hidden layers)
    # Architecture: 295 -> 128 -> 32 -> 128 -> 295 (bottleneck autoencoder)
    model = MLPRegressor(
        hidden_layer_sizes=(128, 32, 128),
        activation='relu',
        solver='adam',
        learning_rate_init=1e-3,
        max_iter=100,
        batch_size=256,
        random_state=42,
        verbose=True,
    )

    # Subsample if too large (>50k) for speed
    if len(quiet_input) > 50000:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(quiet_input), 50000, replace=False)
        train_data = quiet_input[idx]
        print(f"  Subsampled to {len(train_data)} for training")
    else:
        train_data = quiet_input

    model.fit(train_data, train_data)  # autoencoder: predict self

    # Step 4: Compute reconstruction error on quiet data to set threshold
    quiet_recon = model.predict(quiet_input)
    quiet_errors = np.mean((quiet_input - quiet_recon) ** 2, axis=1)

    threshold_95 = np.percentile(quiet_errors, 95)
    threshold_99 = np.percentile(quiet_errors, 99)
    threshold_999 = np.percentile(quiet_errors, 99.9)

    print(f"\n  Quiet reconstruction error stats:")
    print(f"    Mean:   {quiet_errors.mean():.6f}")
    print(f"    Std:    {quiet_errors.std():.6f}")
    print(f"    95th:   {threshold_95:.6f}")
    print(f"    99th:   {threshold_99:.6f}")
    print(f"    99.9th: {threshold_999:.6f}")

    # Step 5: Test on flare periods — does error spike BEFORE the peak?
    print(f"\n  Flare anomaly detection results:")
    print(f"  {'Date':12s} {'Class':>6s} {'Peak':>6s} {'Pre-flare err':>14s} {'At-peak err':>12s} {'Ratio':>7s} {'Anomaly':>8s} {'Lead(min)':>10s}")

    results = []
    for fw in flare_windows:
        t_hrs = fw['t_hrs']
        spectra = fw['spectra']
        peak_hrs = fw['peak_hrs']
        cls = fw['class']

        # Normalize using quiet stats, handle NaN
        spec_log = np.log1p(spectra)
        spec_norm = ((spec_log - channel_mean) / channel_std)[:, ch_start:ch_end].astype(np.float64)
        # Replace NaN/inf with 0 (dead channels)
        spec_norm = np.nan_to_num(spec_norm, nan=0.0, posinf=0.0, neginf=0.0)

        # Compute reconstruction error for each spectrum
        recon = model.predict(spec_norm)
        errors = np.mean((spec_norm - recon) ** 2, axis=1)

        # Pre-flare window: 15 min to 2 min before peak
        pre_mask = (t_hrs > peak_hrs - 0.25) & (t_hrs < peak_hrs - 0.033)
        # At-peak window: ±1 min of peak
        peak_mask = (t_hrs > peak_hrs - 0.017) & (t_hrs < peak_hrs + 0.017)

        pre_err = errors[pre_mask].mean() if pre_mask.any() else 0
        peak_err = errors[peak_mask].mean() if peak_mask.any() else 0
        ratio = pre_err / max(quiet_errors.mean(), 1e-8)

        # Find earliest anomaly (error > 99th percentile) before peak
        lead_min = None
        anomaly_detected = False
        pre_flare_indices = np.where((t_hrs > peak_hrs - 0.5) & (t_hrs < peak_hrs))[0]
        for idx in pre_flare_indices:
            if errors[idx] > threshold_99:
                lead_min = (peak_hrs - t_hrs[idx]) * 60
                anomaly_detected = True
                break

        lead_str = f"{lead_min:.1f}" if lead_min is not None else "---"
        anom_str = "YES" if anomaly_detected else "no"

        print(f"  {fw['date']:12s} {cls:>6s} {peak_hrs:6.2f}h {pre_err:14.6f} {peak_err:12.6f} {ratio:7.1f}x {anom_str:>8s} {lead_str:>10s}")

        results.append({
            'date': fw['date'],
            'class': cls,
            'peak_hrs': peak_hrs,
            'pre_flare_error': pre_err,
            'peak_error': peak_err,
            'quiet_ratio': ratio,
            'anomaly_detected': anomaly_detected,
            'lead_min': lead_min,
        })

    # Summary by class
    print(f"\n  Summary by class:")
    for cls in ['C', 'M', 'X']:
        cls_results = [r for r in results if r['class'].startswith(cls)]
        if not cls_results:
            continue
        detected = sum(1 for r in cls_results if r['anomaly_detected'])
        leads = [r['lead_min'] for r in cls_results if r['lead_min'] is not None]
        avg_lead = np.mean(leads) if leads else 0
        avg_ratio = np.mean([r['quiet_ratio'] for r in cls_results])
        print(f"    {cls}-class: {detected}/{len(cls_results)} detected pre-flare ({detected/len(cls_results)*100:.0f}%)")
        print(f"             avg quiet_ratio={avg_ratio:.1f}x, avg lead={avg_lead:.1f} min")

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SUDARSHAN — ML EXPERIMENTS")
    print("=" * 70)

    exp1_results = run_experiment_1()

    exp3_results = run_experiment_3()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n  Exp 1 (XGBoost FA classifier):")
    print(f"    FAR: {exp1_results['old_far']:.1f}% -> {exp1_results['new_far']:.1f}%")
    print(f"    TPR preserved: {exp1_results['new_tpr']:.1f}%")
    print(f"    FA killed: {exp1_results['fa_killed']}")

    anomaly_detected = sum(1 for r in exp3_results if r['anomaly_detected'])
    print(f"\n  Exp 3 (Spectral autoencoder):")
    print(f"    Pre-flare anomalies detected: {anomaly_detected}/{len(exp3_results)}")
    mx_results = [r for r in exp3_results if r['class'][0] in ('M', 'X')]
    mx_detected = sum(1 for r in mx_results if r['anomaly_detected'])
    if mx_results:
        print(f"    M/X-class pre-flare: {mx_detected}/{len(mx_results)} ({mx_detected/len(mx_results)*100:.0f}%)")
    leads = [r['lead_min'] for r in exp3_results if r['lead_min'] is not None]
    if leads:
        print(f"    Avg lead time: {np.mean(leads):.1f} min")
