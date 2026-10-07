#!/usr/bin/env python3
"""
================================================================================
FINAL YEAR PROJECT: DIGITAL SOIL NUTRIENT MAPPING (MBU)
MODULE: SPATIAL BLOCK CROSS-VALIDATION (TOBLER'S LAW LEAKAGE AUDIT)
================================================================================
Eliminates spatial autocorrelation data leakage by comparing:
  1. Standard Random 5-Fold Cross-Validation (Traditional baseline)
  2. Spatial Block 5-Fold Cross-Validation (GroupKFold by regional geographic clusters)

Guarantees that test folds consist of entirely unseen geographic sectors / land blocks,
providing honest, un-inflated regional out-of-field generalization metrics.
================================================================================
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.model_selection import KFold, GroupKFold
from sklearn.ensemble import ExtraTreesRegressor, ExtraTreesClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, accuracy_score
from scipy.stats import pearsonr

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add 05_Production_Models to path to reuse feature definitions
MODULE_DIR = Path(__file__).resolve().parent
BASE_DIR = MODULE_DIR.parent
sys.path.append(str(BASE_DIR / "05_Production_Models"))

from train_dual_head_models import (
    ALL_MODEL_FEATURES,
    engineer_raw_features,
    get_icar_class,
    ICAR_CLASS_LABELS
)


def run_spatial_block_cv():
    data_file = BASE_DIR / "02_Satellite_Covariates" / "ExtractDependencies" / "SPSR_Nellore_Final_Comprehensive_SCORPAN_Dataset.csv"
    results_dir = MODULE_DIR / "results"
    pedometric_csv_dir = MODULE_DIR / "pedometric_evaluation" / "results" / "csv"
    results_dir.mkdir(parents=True, exist_ok=True)
    pedometric_csv_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 85)
    print("MBU DIGITAL SOIL MAPPING: SPATIAL BLOCK CROSS-VALIDATION AUDIT")
    print("=" * 85)
    print(f"[*] Reading dataset: {data_file}")
    df_raw = pd.read_csv(data_file)
    print(f"[+] Loaded {len(df_raw)} samples across SPSR Nellore District.")

    df_proc = engineer_raw_features(df_raw)
    X = df_proc[ALL_MODEL_FEATURES].copy()
    targets = ['N', 'P', 'K', 'OC']
    units = {'N': 'kg/ha', 'P': 'kg/ha', 'K': 'kg/ha', 'OC': '%'}
    y = df_proc[targets].copy()

    # Create 5 Non-Overlapping Spatial Geographic Blocks via Spatial K-Means on coordinates
    coords = df_raw[['Latitude', 'Longitude']].values
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    spatial_groups = kmeans.fit_predict(coords)
    df_proc['Spatial_Cluster_ID'] = spatial_groups

    print("[+] Spatial Geographic Clusters (K=5 Sectors):")
    for g_id in range(5):
        cnt = (spatial_groups == g_id).sum()
        lat_c = coords[spatial_groups == g_id, 0].mean()
        lon_c = coords[spatial_groups == g_id, 1].mean()
        print(f"    - Cluster {g_id}: {cnt:3d} points | Centroid: ({lat_c:.4f}° N, {lon_c:.4f}° E)")

    # Define validation strategies
    cv_random = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_spatial = GroupKFold(n_splits=5)

    comparison_records = []

    for t in targets:
        y_t = y[t].values
        y_classes = get_icar_class(t, y_t)
        use_log = t in ['P', 'K']

        # ---------------------------------------------------------------------
        # 1. Random 5-Fold Cross-Validation
        # ---------------------------------------------------------------------
        y_pred_rand_cont = np.zeros_like(y_t, dtype=float)
        y_pred_rand_cls = np.zeros_like(y_classes, dtype=int)

        for tr_idx, te_idx in cv_random.split(X, y_t):
            X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
            y_tr, y_te = y_t[tr_idx], y_t[te_idx]
            y_cls_tr = y_classes[tr_idx]

            imp = SimpleImputer(strategy='median')
            X_tr_imp = imp.fit_transform(X_tr)
            X_te_imp = imp.transform(X_te)

            scl = StandardScaler()
            X_tr_s = scl.fit_transform(X_tr_imp)
            X_te_s = scl.transform(X_te_imp)

            y_tr_fit = np.log1p(y_tr) if use_log else y_tr
            reg = ExtraTreesRegressor(n_estimators=350, max_depth=16, min_samples_leaf=2, max_features=0.65, random_state=42, n_jobs=-1)
            reg.fit(X_tr_s, y_tr_fit)
            p_cont = reg.predict(X_te_s)
            if use_log:
                p_cont = np.clip(np.expm1(p_cont), 0, None)
            y_pred_rand_cont[te_idx] = p_cont

            clf = ExtraTreesClassifier(n_estimators=300, max_depth=14, min_samples_leaf=2, max_features=0.65, random_state=42, n_jobs=-1)
            clf.fit(X_tr_s, y_cls_tr)
            y_pred_rand_cls[te_idx] = clf.predict(X_te_s)

        r2_rand = r2_score(y_t, y_pred_rand_cont)
        r_rand, _ = pearsonr(y_t, y_pred_rand_cont)
        rmse_rand = np.sqrt(mean_squared_error(y_t, y_pred_rand_cont))
        mae_rand = mean_absolute_error(y_t, y_pred_rand_cont)
        acc_rand = accuracy_score(y_classes, y_pred_rand_cls) * 100.0
        safe_rand = np.mean(np.abs(y_classes - y_pred_rand_cls) <= 1) * 100.0

        # ---------------------------------------------------------------------
        # 2. Spatial Block 5-Fold Cross-Validation (GroupKFold by Sector)
        # ---------------------------------------------------------------------
        y_pred_spat_cont = np.zeros_like(y_t, dtype=float)
        y_pred_spat_cls = np.zeros_like(y_classes, dtype=int)

        for tr_idx, te_idx in cv_spatial.split(X, y_t, groups=spatial_groups):
            X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
            y_tr, y_te = y_t[tr_idx], y_t[te_idx]
            y_cls_tr = y_classes[tr_idx]

            imp = SimpleImputer(strategy='median')
            X_tr_imp = imp.fit_transform(X_tr)
            X_te_imp = imp.transform(X_te)

            scl = StandardScaler()
            X_tr_s = scl.fit_transform(X_tr_imp)
            X_te_s = scl.transform(X_te_imp)

            y_tr_fit = np.log1p(y_tr) if use_log else y_tr
            reg = ExtraTreesRegressor(n_estimators=350, max_depth=16, min_samples_leaf=2, max_features=0.65, random_state=42, n_jobs=-1)
            reg.fit(X_tr_s, y_tr_fit)
            p_cont = reg.predict(X_te_s)
            if use_log:
                p_cont = np.clip(np.expm1(p_cont), 0, None)
            y_pred_spat_cont[te_idx] = p_cont

            clf = ExtraTreesClassifier(n_estimators=300, max_depth=14, min_samples_leaf=2, max_features=0.65, random_state=42, n_jobs=-1)
            clf.fit(X_tr_s, y_cls_tr)
            y_pred_spat_cls[te_idx] = clf.predict(X_te_s)

        r2_spat = r2_score(y_t, y_pred_spat_cont)
        r_spat, _ = pearsonr(y_t, y_pred_spat_cont)
        rmse_spat = np.sqrt(mean_squared_error(y_t, y_pred_spat_cont))
        mae_spat = mean_absolute_error(y_t, y_pred_spat_cont)
        acc_spat = accuracy_score(y_classes, y_pred_spat_cls) * 100.0
        safe_spat = np.mean(np.abs(y_classes - y_pred_spat_cls) <= 1) * 100.0

        r2_penalty = r2_rand - r2_spat

        comparison_records.append({
            'Target': t,
            'Unit': units[t],
            'Samples': len(y_t),
            'Random_CV_R2': round(r2_rand, 4),
            'Spatial_Block_CV_R2': round(r2_spat, 4),
            'Spatial_R2_Penalty': round(r2_penalty, 4),
            'Random_CV_Pearson_r': round(r_rand, 4),
            'Spatial_Block_Pearson_r': round(r_spat, 4),
            'Random_CV_RMSE': round(rmse_rand, 2),
            'Spatial_Block_RMSE': round(rmse_spat, 2),
            'Random_CV_MAE': round(mae_rand, 2),
            'Spatial_Block_MAE': round(mae_spat, 2),
            'Random_ICAR_Class_Acc_%': round(acc_rand, 2),
            'Spatial_ICAR_Class_Acc_%': round(acc_spat, 2),
            'Random_Safe_Tier_Agree_%': round(safe_rand, 2),
            'Spatial_Safe_Tier_Agree_%': round(safe_spat, 2)
        })

    comp_df = pd.DataFrame(comparison_records)
    csv_out1 = results_dir / "spatial_block_cv_metrics.csv"
    csv_out2 = pedometric_csv_dir / "spatial_block_cv_metrics.csv"
    comp_df.to_csv(csv_out1, index=False)
    comp_df.to_csv(csv_out2, index=False)

    print("\n" + "=" * 85)
    print("RESULTS: RANDOM 5-FOLD CV vs. SPATIAL BLOCK 5-FOLD CV")
    print("=" * 85)
    for rec in comparison_records:
        t = rec['Target']
        u = rec['Unit']
        print(f"\nSoil Target: {t} ({u})")
        print(f"  • Random CV R²        : {rec['Random_CV_R2']:0.4f}  |  Spatial Block CV R²: {rec['Spatial_Block_CV_R2']:0.4f} (Penalty: {rec['Spatial_R2_Penalty']:0.4f})")
        print(f"  • Pearson r           : {rec['Random_CV_Pearson_r']:0.4f}  |  Spatial Block r    : {rec['Spatial_Block_Pearson_r']:0.4f}")
        print(f"  • RMSE                : {rec['Random_CV_RMSE']:6.2f}  |  Spatial Block RMSE : {rec['Spatial_Block_RMSE']:6.2f} {u}")
        print(f"  • ICAR Class Accuracy : {rec['Random_ICAR_Class_Acc_%']:5.2f}% |  Spatial Class Acc  : {rec['Spatial_ICAR_Class_Acc_%']:5.2f}%")
        print(f"  • Safe-Tier Agreement : {rec['Random_Safe_Tier_Agree_%']:5.2f}% |  Spatial Safe-Tier   : {rec['Spatial_Safe_Tier_Agree_%']:5.2f}%")

    print("\n" + "=" * 85)
    print(f"[+] Saved Spatial Block CV benchmark table to:\n    - {csv_out1}\n    - {csv_out2}")
    print("=" * 85)


if __name__ == '__main__':
    run_spatial_block_cv()
