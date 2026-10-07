#!/usr/bin/env python3
"""
================================================================================
DIGITAL SOIL NUTRIENT MAPPING (MBU FINAL YEAR PROJECT)
MODULE: COMPREHENSIVE PEDOMETRIC & REGRESSION EVALUATION METRICS SUITE
================================================================================
Implements all 5 Tiers from the Pedometrics and Soil Standards Evaluation Hierarchy:

  Tier 1: Mandatory Core (Non-Negotiable)
    1. R² (Coefficient of Determination)
    2. RMSE (Root Mean Squared Error)
    3. MAE (Mean Absolute Error)

  Tier 2: Pedometric & Soil Standards (High Academic Value)
    4. RPIQ (Ratio of Performance to Interquartile Distance)
    5. RPD (Ratio of Performance to Deviation)
    6. CCC (Lin's Concordance Correlation Coefficient)
    7. Bias / MBE (Mean Bias Error)

  Tier 3: Scale Normalization & Skewness Handling
    8. NRMSE (Normalized RMSE: Range-based % and Mean-based %)
    9. RMSLE (Root Mean Squared Logarithmic Error for Skewed P & K)
   10. Adjusted R² (Ablation and Feature Count Verification)

  Tier 4: Uncertainty Bounds (For Quantile Random Forest)
   11. PICP (Prediction Interval Coverage Probability) & MPIW (Mean Prediction Interval Width)

  Tier 5: Not Recommended / Avoid in Soil Analysis (Comparative Academic Analysis)
   12. MAPE (Mean Absolute Percentage Error - fails when OC/P near zero)
   13. NSE / KGE (Nash-Sutcliffe Efficiency / Kling-Gupta Efficiency - Hydrology specific)
   14. AIC / BIC (Akaike / Bayesian Information Criterion - OLS / Linear only)
================================================================================
"""

import sys
import os
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.cross_decomposition import PLSRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

# Academic styling
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.8
plt.rcParams['grid.color'] = '#cccccc'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.6


class PedometricMetrics:
    """
    Pedometric & Regression Metrics Calculator implementing Tiers 1 through 5.
    """

    @staticmethod
    def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Tier 1: Coefficient of Determination (R²)"""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        if ss_tot == 0:
            return 0.0
        return float(1.0 - (ss_res / ss_tot))

    @staticmethod
    def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Tier 1: Root Mean Squared Error (RMSE)"""
        return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    @staticmethod
    def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Tier 1: Mean Absolute Error (MAE)"""
        return float(np.mean(np.abs(y_true - y_pred)))

    @staticmethod
    def rpiq(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 2: Ratio of Performance to Interquartile Distance (RPIQ)
        Formula: IQR / RMSE = (Q3 - Q1) / RMSE
        Recommended by Bellon-Maurel et al. (2010) for non-normal, skewed soil distributions.
        """
        rmse_val = PedometricMetrics.rmse(y_true, y_pred)
        if rmse_val == 0:
            return float('inf')
        q75, q25 = np.percentile(y_true, [75, 25])
        iqr = q75 - q25
        return float(iqr / rmse_val)

    @staticmethod
    def rpd(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 2: Ratio of Performance to Deviation (RPD)
        Formula: SD(y_true) / RMSE
        Classic pedometrics metric (Williams, 1987; Chang et al., 2001).
        """
        rmse_val = PedometricMetrics.rmse(y_true, y_pred)
        if rmse_val == 0:
            return float('inf')
        sd = np.std(y_true, ddof=1)
        return float(sd / rmse_val)

    @staticmethod
    def ccc(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 2: Lin's Concordance Correlation Coefficient (CCC)
        Formula: 2 * Cov(y, y_pred) / (s_y^2 + s_pred^2 + (mean_y - mean_pred)^2)
        Measures agreement along the 1:1 perfect concordance line.
        Penalizes both rotation/slope deviation and mean translation/bias.
        """
        mean_t = np.mean(y_true)
        mean_p = np.mean(y_pred)
        var_t = np.var(y_true, ddof=1)
        var_p = np.var(y_pred, ddof=1)
        cov = np.cov(y_true, y_pred)[0, 1]
        denom = var_t + var_p + (mean_t - mean_p) ** 2
        if denom == 0:
            return 0.0
        return float((2.0 * cov) / denom)

    @staticmethod
    def mbe(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 2: Mean Bias Error (MBE / Bias)
        Formula: (1/n) * sum(y_pred - y_true)
        Positive indicates systematic overestimation; negative indicates underestimation.
        """
        return float(np.mean(y_pred - y_true))

    @staticmethod
    def nrmse_range(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 3: Range-Normalized RMSE (%)
        Formula: [RMSE / (max(y_true) - min(y_true))] * 100
        """
        y_range = np.max(y_true) - np.min(y_true)
        if y_range == 0:
            return 0.0
        return float((PedometricMetrics.rmse(y_true, y_pred) / y_range) * 100.0)

    @staticmethod
    def nrmse_mean(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 3: Mean-Normalized RMSE (CV-RMSE %)
        Formula: [RMSE / mean(y_true)] * 100
        """
        mean_val = np.mean(y_true)
        if mean_val == 0:
            return 0.0
        return float((PedometricMetrics.rmse(y_true, y_pred) / mean_val) * 100.0)

    @staticmethod
    def rmsle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 3: Root Mean Squared Logarithmic Error (RMSLE)
        Formula: sqrt( (1/n) * sum( (log(y_pred + 1) - log(y_true + 1))^2 ) )
        Designed for skewed distributions (P & K) with order-of-magnitude ranges.
        """
        y_p_clipped = np.clip(y_pred, 0, None)
        y_t_clipped = np.clip(y_true, 0, None)
        return float(np.sqrt(np.mean((np.log1p(y_p_clipped) - np.log1p(y_t_clipped)) ** 2)))

    @staticmethod
    def adjusted_r2(y_true: np.ndarray, y_pred: np.ndarray, p: int) -> float:
        """
        Tier 3: Adjusted R²
        Formula: 1 - [(1 - R²) * (n - 1) / (n - p - 1)]
        p: number of predictors / features.
        """
        n = len(y_true)
        if n <= p + 1:
            return 0.0
        r2_val = PedometricMetrics.r2(y_true, y_pred)
        adj_r2 = 1.0 - ((1.0 - r2_val) * (n - 1) / (n - p - 1))
        return float(adj_r2)

    @staticmethod
    def picp_mpiw(y_true: np.ndarray, lower_bounds: np.ndarray, upper_bounds: np.ndarray) -> dict:
        """
        Tier 4: Prediction Interval Coverage Probability (PICP) & Mean Prediction Interval Width (MPIW)
        PICP: % of true observations within [lower_bound, upper_bound]
        MPIW: Mean width of the interval (upper_bound - lower_bound)
        NMPIW: Normalized MPIW relative to the range of y_true (%)
        """
        covered = (y_true >= lower_bounds) & (y_true <= upper_bounds)
        picp = float(np.mean(covered) * 100.0)
        widths = upper_bounds - lower_bounds
        mpiw = float(np.mean(widths))
        y_range = np.max(y_true) - np.min(y_true)
        nmpiw = float((mpiw / y_range) * 100.0) if y_range > 0 else 0.0
        return {
            'PICP_%': round(picp, 2),
            'MPIW': round(mpiw, 3),
            'NMPIW_%': round(nmpiw, 2)
        }

    @staticmethod
    def conformalized_quantile_regression(y_calib: np.ndarray,
                                          q_low_calib: np.ndarray,
                                          q_high_calib: np.ndarray,
                                          q_low_test: np.ndarray,
                                          q_high_test: np.ndarray,
                                          nominal_level: float = 90.0,
                                          clip_min: float = 0.0) -> tuple:
        r"""
        Tier 4: Conformalized Quantile Regression (CQR; Romano, Patterson & Candès, NeurIPS 2019).
        Computes non-conformity scores:
            E_i = max(q_low_calib(x_i) - y_i, y_i - q_high_calib(x_i))
        Calculates empirical finite-sample correction quantile:
            q_conf = quantile(E_i, ceil((1 - alpha) * (N + 1)) / N)
        Adjusts prediction intervals:
            [max(clip_min, q_low_test - q_conf), q_high_test + q_conf]
        Guarantees marginal coverage P(Y \in C(X)) >= 1 - alpha.
        """
        alpha = (100.0 - nominal_level) / 100.0
        n_calib = len(y_calib)
        E = np.maximum(q_low_calib - y_calib, y_calib - q_high_calib)
        conf_level = np.ceil((1.0 - alpha) * (n_calib + 1)) / n_calib
        conf_level = min(1.0, float(conf_level))
        cqr_offset = float(np.percentile(E, conf_level * 100.0))
        cqr_lower = np.clip(q_low_test - cqr_offset, clip_min, None)
        cqr_upper = q_high_test + cqr_offset
        return cqr_lower, cqr_upper, cqr_offset

    # =========================================================================
    # Tier 5: Not Recommended / Avoid in Soil Analysis (Pedometric Evaluation)
    # =========================================================================
    @staticmethod
    def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-6) -> float:
        """
        Tier 5: Mean Absolute Percentage Error (MAPE)
        Formula: (100% / n) * sum(|y_true - y_pred| / y_true)
        WHY AVOIDED IN SOIL ANALYSIS:
          Fails severely when Organic Carbon (OC) is near 0 (e.g. 0.1-0.3%) or Available P is near 0.
          Division by small denominators causes percentage error to blow up infinitely (e.g. >10,000%).
        """
        denom = np.where(np.abs(y_true) < eps, eps, np.abs(y_true))
        return float(np.mean(np.abs((y_true - y_pred) / denom)) * 100.0)

    @staticmethod
    def nse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 5: Nash-Sutcliffe Efficiency (NSE)
        Formula: 1 - [sum((y_true - y_pred)^2) / sum((y_true - mean(y_true))^2)]
        Mathematically equivalent to R² under 1:1 line constraint, but conceptually
        defined for hydrological continuous time-series streamflow discharge hydrographs.
        """
        return PedometricMetrics.r2(y_true, y_pred)

    @staticmethod
    def kge(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Tier 5: Kling-Gupta Efficiency (KGE - Gupta et al., 2009)
        Formula: 1 - sqrt((r - 1)^2 + (alpha - 1)^2 + (beta - 1)^2)
        where r = Pearson correlation, alpha = std(y_pred)/std(y_true), beta = mean(y_pred)/mean(y_true)
        Specifically decomposes hydrological errors into correlation, variability, and volume bias.
        Not suited for discrete spatial soil fertility tests.
        """
        if len(y_true) < 2 or np.std(y_true) == 0 or np.std(y_pred) == 0:
            return 0.0
        r_val, _ = pearsonr(y_true, y_pred)
        alpha = np.std(y_pred) / (np.std(y_true) + 1e-9)
        beta = np.mean(y_pred) / (np.mean(y_true) + 1e-9)
        ed = np.sqrt((r_val - 1.0) ** 2 + (alpha - 1.0) ** 2 + (beta - 1.0) ** 2)
        return float(1.0 - ed)

    @staticmethod
    def aic_bic_ols(y_true: np.ndarray, y_pred: np.ndarray, k: int) -> dict:
        """
        Tier 5: AIC & BIC (Akaike & Bayesian Information Criteria)
        Calculated assuming Gaussian residual likelihood:
          AIC = n * ln(SSE / n) + 2 * k
          BIC = n * ln(SSE / n) + k * ln(n)
        WHY AVOIDED FOR RANDOM FORESTS & NON-PARAMETRIC ENSEMBLES:
          k (effective degrees of freedom) is well-defined for OLS linear models,
          but indeterminate for deep decision trees, random forests, and gradient boosters.
        """
        n = len(y_true)
        sse = np.sum((y_true - y_pred) ** 2)
        if sse <= 0 or n == 0:
            return {'AIC': float('nan'), 'BIC': float('nan')}
        aic = n * np.log(sse / n) + 2 * k
        bic = n * np.log(sse / n) + k * np.log(n)
        return {'AIC': round(float(aic), 2), 'BIC': round(float(bic), 2)}

    @classmethod
    def evaluate_all(cls, y_true: np.ndarray, y_pred: np.ndarray, p_features: int = 32,
                     lower_bounds: np.ndarray = None, upper_bounds: np.ndarray = None) -> dict:
        """
        Computes all tiers of metrics simultaneously for a given target and model.
        """
        res = {
            # Tier 1: Mandatory Core
            'R2': round(cls.r2(y_true, y_pred), 4),
            'RMSE': round(cls.rmse(y_true, y_pred), 3),
            'MAE': round(cls.mae(y_true, y_pred), 3),

            # Tier 2: Pedometric & Soil Standards
            'RPIQ': round(cls.rpiq(y_true, y_pred), 3),
            'RPD': round(cls.rpd(y_true, y_pred), 3),
            'CCC': round(cls.ccc(y_true, y_pred), 4),
            'Bias_MBE': round(cls.mbe(y_true, y_pred), 3),

            # Tier 3: Scale Normalization & Skewness Handling
            'NRMSE_Range_%': round(cls.nrmse_range(y_true, y_pred), 2),
            'NRMSE_Mean_%': round(cls.nrmse_mean(y_true, y_pred), 2),
            'RMSLE': round(cls.rmsle(y_true, y_pred), 4),
            'Adjusted_R2': round(cls.adjusted_r2(y_true, y_pred, p_features), 4),

            # Tier 5: Avoid / Caveat Soil Metrics
            'MAPE_%': round(cls.mape(y_true, y_pred), 2),
            'NSE': round(cls.nse(y_true, y_pred), 4),
            'KGE': round(cls.kge(y_true, y_pred), 4)
        }

        # Tier 4: Uncertainty Bounds (if lower & upper provided)
        if lower_bounds is not None and upper_bounds is not None:
            unc = cls.picp_mpiw(y_true, lower_bounds, upper_bounds)
            res.update({
                'PICP_%': unc['PICP_%'],
                'MPIW': unc['MPIW'],
                'NMPIW_%': unc['NMPIW_%']
            })

        return res


def run_full_pedometric_evaluation():
    # Detect directories robustly
    this_dir = Path(__file__).resolve().parent
    if this_dir.name == "pedometric_evaluation":
        stage4_dir = this_dir.parent
        base_dir = stage4_dir.parent
    else:
        stage4_dir = this_dir
        base_dir = stage4_dir.parent

    # Destination directories for clean organization
    suite_dir = stage4_dir / "pedometric_evaluation"
    suite_results_dir = suite_dir / "results"
    csv_dir = suite_results_dir / "csv"
    fig_dir = suite_results_dir / "figures"
    legacy_results_dir = stage4_dir / "results"

    csv_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    legacy_results_dir.mkdir(parents=True, exist_ok=True)

    pred_file = legacy_results_dir / "predictions_2025_2026.csv"

    print("=" * 85)
    print("MBU DIGITAL SOIL NUTRIENT MAPPING: COMPREHENSIVE PEDOMETRIC EVALUATION")
    print("=" * 85)
    print(f"[*] Package Directory: {suite_dir}")
    print(f"[*] Output CSV Dir   : {csv_dir}")
    print(f"[*] Output Figure Dir: {fig_dir}")

    if not pred_file.exists():
        raise FileNotFoundError(f"Predictions file not found at: {pred_file}")

    df_preds = pd.read_csv(pred_file)
    print(f"[+] Loaded Out-of-Time Predictions (2025-2026 Cycle): {len(df_preds)} samples.")

    # Target metadata
    targets = ['N', 'P', 'K', 'OC']
    units = {'N': 'kg/ha', 'P': 'kg/ha', 'K': 'kg/ha', 'OC': '%'}
    models = ['Random Forest', 'Ridge', 'PLSR']
    
    # Clip outlier in ground truth test point for N
    df_preds['N_Actual'] = df_preds['N_Actual'].clip(0, 500)

    # -------------------------------------------------------------------------
    # PART 1: FIT QUANTILE RANDOM FOREST (Tier 4 Uncertainty Bounds)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 85)
    print("COMPUTING TIER 4: QUANTILE RANDOM FOREST UNCERTAINTY BOUNDS (PICP & MPIW)")
    print("-" * 85)

    data_dir = base_dir / "02_Satellite_Covariates" / "3_years_sentinal2_images"
    train_years = ['2023-24', '2024-25']
    raw_dfs = {y: pd.read_csv(data_dir / f"nellore_sentinel2_scorpan_{y}.csv") for y in train_years}
    test_raw_df = pd.read_csv(data_dir / "nellore_sentinel2_scorpan_2025-26.csv")

    common_cols = set(raw_dfs['2023-24'].columns).intersection(raw_dfs['2024-25'].columns).intersection(test_raw_df.columns)
    id_cols = ['Village', 'Feature_ID']
    feat_cols = sorted([c for c in common_cols if c not in id_cols and c not in targets])

    train_df = pd.concat([raw_dfs['2023-24'][feat_cols + targets], raw_dfs['2024-25'][feat_cols + targets]], ignore_index=True)
    test_df = test_raw_df[feat_cols + targets].copy()

    imputer = SimpleImputer(strategy='median')
    X_train_imp = imputer.fit_transform(train_df[feat_cols])
    X_test_imp = imputer.transform(test_df[feat_cols])

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)

    qrf_bounds = {}
    cqr_bounds = {}
    cqr_offsets = {}
    p_feature_count = len(feat_cols)
    print(f"[+] Quantile RF & CQR Engine initialized with p={p_feature_count} mutual SCORPAN covariates.")

    # 80/20 train/calibration split for Conformalized Quantile Regression (Romano et al., 2019)
    np.random.seed(42)
    n_train_tot = len(X_train_s)
    perm_idx = np.random.permutation(n_train_tot)
    calib_split = int(0.20 * n_train_tot)
    c_idx, pt_idx = perm_idx[:calib_split], perm_idx[calib_split:]
    X_prop_tr, X_calib = X_train_s[pt_idx], X_train_s[c_idx]

    for t in targets:
        y_tr = train_df[t].values
        y_prop_tr = y_tr[pt_idx]
        y_cal = y_tr[c_idx]
        y_te = test_df[t].values.copy()
        if t == 'N':
            y_te = np.clip(y_te, 0, 500)
        use_log = t in ['P', 'K']
        y_fit = np.log1p(y_prop_tr) if use_log else y_prop_tr

        rf = RandomForestRegressor(n_estimators=350, max_depth=12, random_state=42, n_jobs=-1)
        rf.fit(X_prop_tr, y_fit)

        # Calibration set tree predictions
        cal_tree_preds = np.array([tree.predict(X_calib) for tree in rf.estimators_])
        if use_log:
            cal_tree_preds = np.clip(np.expm1(cal_tree_preds), 0, None)

        # Test set tree predictions
        test_tree_preds = np.array([tree.predict(X_test_s) for tree in rf.estimators_])
        if use_log:
            test_tree_preds = np.clip(np.expm1(test_tree_preds), 0, None)

        # 90% and 95% nominal raw quantiles
        q05_cal = np.percentile(cal_tree_preds, 5, axis=0)
        q95_cal = np.percentile(cal_tree_preds, 95, axis=0)
        q025_cal = np.percentile(cal_tree_preds, 2.5, axis=0)
        q975_cal = np.percentile(cal_tree_preds, 97.5, axis=0)

        q05_te = np.percentile(test_tree_preds, 5, axis=0)
        q95_te = np.percentile(test_tree_preds, 95, axis=0)
        q025_te = np.percentile(test_tree_preds, 2.5, axis=0)
        q975_te = np.percentile(test_tree_preds, 97.5, axis=0)

        # CQR conformal calibration
        cqr_low_90, cqr_high_90, offset_90 = PedometricMetrics.conformalized_quantile_regression(
            y_calib=y_cal, q_low_calib=q05_cal, q_high_calib=q95_cal,
            q_low_test=q05_te, q_high_test=q95_te, nominal_level=90.0, clip_min=0.0
        )
        cqr_low_95, cqr_high_95, offset_95 = PedometricMetrics.conformalized_quantile_regression(
            y_calib=y_cal, q_low_calib=q025_cal, q_high_calib=q975_cal,
            q_low_test=q025_te, q_high_test=q975_te, nominal_level=95.0, clip_min=0.0
        )

        qrf_bounds[t] = {
            '90%': (q05_te, q95_te),
            '95%': (q025_te, q975_te),
            'rf_model': rf
        }
        cqr_bounds[t] = {
            '90%': (cqr_low_90, cqr_high_90),
            '95%': (cqr_low_95, cqr_high_95)
        }
        cqr_offsets[t] = {'90%': offset_90, '95%': offset_95}

        m90_raw = PedometricMetrics.picp_mpiw(y_te, q05_te, q95_te)
        m90_cqr = PedometricMetrics.picp_mpiw(y_te, cqr_low_90, cqr_high_90)
        m95_raw = PedometricMetrics.picp_mpiw(y_te, q025_te, q975_te)
        m95_cqr = PedometricMetrics.picp_mpiw(y_te, cqr_low_95, cqr_high_95)

        print(f" [+] Soil {t:<3} | 90% PI: Raw PICP={m90_raw['PICP_%']:5.2f}% -> CQR PICP={m90_cqr['PICP_%']:5.2f}% (Target: 90%) [Offset: +{offset_90:.2f} {units[t]}]")
        print(f"            | 95% PI: Raw PICP={m95_raw['PICP_%']:5.2f}% -> CQR PICP={m95_cqr['PICP_%']:5.2f}% (Target: 95%) [Offset: +{offset_95:.2f} {units[t]}]")

    # -------------------------------------------------------------------------
    # PART 2: FEW-SHOT SEASONAL CALIBRATION (N=25)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 85)
    print("CALCULATING METRICS FOR FEW-SHOT CALIBRATED RANDOM FOREST (N=25 ANCHORS)")
    print("-" * 85)
    np.random.seed(42)
    anchor_idx = np.random.choice(df_preds.index, size=25, replace=False)
    eval_idx = [i for i in df_preds.index if i not in anchor_idx]
    anchor_df = df_preds.loc[anchor_idx]
    eval_df = df_preds.loc[eval_idx]

    calibrated_preds = {}
    for t in targets:
        act = anchor_df[f"{t}_Actual"].values
        pred = anchor_df[f"{t}_Pred_Random_Forest"].values
        delta = float(np.mean(act - pred))
        calibrated_preds[t] = np.clip(eval_df[f"{t}_Pred_Random_Forest"].values + delta, 0, None)
        print(f" [+] Soil {t:<3}: Seasonal Delta = {delta:+7.2f} {units[t]}")

    # -------------------------------------------------------------------------
    # PART 3: SYSTEMATIC COMPUTATION ACROSS TIERS 1-5
    # -------------------------------------------------------------------------
    all_evaluation_records = []
    
    for m in models:
        m_col = m.replace(' ', '_')
        for t in targets:
            y_true = df_preds[f"{t}_Actual"].values
            y_pred = df_preds[f"{t}_Pred_{m_col}"].values
            
            l_b, u_b = None, None
            if m == 'Random Forest':
                l_b, u_b = qrf_bounds[t]['90%']

            rec = PedometricMetrics.evaluate_all(y_true, y_pred, p_features=p_feature_count,
                                                 lower_bounds=l_b, upper_bounds=u_b)
            rec.update({
                'Evaluation_Scope': 'Out-of-Time Test (2025-26)',
                'Model': m,
                'Target': t,
                'Unit': units[t],
                'Sample_Count': len(y_true),
                'Feature_Count': p_feature_count
            })
            all_evaluation_records.append(rec)

    for t in targets:
        y_true_eval = eval_df[f"{t}_Actual"].values
        y_pred_cal = calibrated_preds[t]
        delta = float(np.mean(anchor_df[f"{t}_Actual"].values - anchor_df[f"{t}_Pred_Random_Forest"].values))
        l_b_cal = np.clip(qrf_bounds[t]['90%'][0][eval_idx] + delta, 0, None)
        u_b_cal = np.clip(qrf_bounds[t]['90%'][1][eval_idx] + delta, 0, None)

        rec = PedometricMetrics.evaluate_all(y_true_eval, y_pred_cal, p_features=p_feature_count,
                                             lower_bounds=l_b_cal, upper_bounds=u_b_cal)
        rec.update({
            'Evaluation_Scope': 'Calibrated Out-of-Time Test (N=25 anchors)',
            'Model': 'Calibrated Random Forest',
            'Target': t,
            'Unit': units[t],
            'Sample_Count': len(y_true_eval),
            'Feature_Count': p_feature_count
        })
        all_evaluation_records.append(rec)

    eval_df_out = pd.DataFrame(all_evaluation_records)
    col_order = [
        'Evaluation_Scope', 'Target', 'Unit', 'Model', 'Sample_Count', 'Feature_Count',
        'R2', 'RMSE', 'MAE',
        'RPIQ', 'RPD', 'CCC', 'Bias_MBE',
        'NRMSE_Range_%', 'NRMSE_Mean_%', 'RMSLE', 'Adjusted_R2',
        'PICP_%', 'MPIW', 'NMPIW_%',
        'MAPE_%', 'NSE', 'KGE'
    ]
    col_order = [c for c in col_order if c in eval_df_out.columns]
    eval_df_out = eval_df_out[col_order]

    # Save to dedicated csv folder and legacy folder
    master_csv_path = csv_dir / "pedometric_comprehensive_metrics_2025_2026.csv"
    eval_df_out.to_csv(master_csv_path, index=False)
    eval_df_out.to_csv(legacy_results_dir / "pedometric_comprehensive_metrics_2025_2026.csv", index=False)
    print(f"\n[+] Master Pedometric Metrics CSV saved to:\n    - {master_csv_path}\n    - {legacy_results_dir / 'pedometric_comprehensive_metrics_2025_2026.csv'}")

    # -------------------------------------------------------------------------
    # PART 4: UNCERTAINTY BOUNDS TABLE & CQR CALIBRATION (Tier 4)
    # -------------------------------------------------------------------------
    uncertainty_records = []
    cqr_comparison_records = []

    for t in targets:
        y_te = df_preds[f"{t}_Actual"].values
        m90_raw = PedometricMetrics.picp_mpiw(y_te, qrf_bounds[t]['90%'][0], qrf_bounds[t]['90%'][1])
        m95_raw = PedometricMetrics.picp_mpiw(y_te, qrf_bounds[t]['95%'][0], qrf_bounds[t]['95%'][1])
        m90_cqr = PedometricMetrics.picp_mpiw(y_te, cqr_bounds[t]['90%'][0], cqr_bounds[t]['90%'][1])
        m95_cqr = PedometricMetrics.picp_mpiw(y_te, cqr_bounds[t]['95%'][0], cqr_bounds[t]['95%'][1])

        uncertainty_records.append({
            'Target': t,
            'Unit': units[t],
            'Test_Samples': len(y_te),
            '90%_Nominal_Target_%': 90.0,
            '90%_PICP_%': m90_cqr['PICP_%'],
            '90%_Raw_PICP_%': m90_raw['PICP_%'],
            '90%_CQR_Calibrated_PICP_%': m90_cqr['PICP_%'],
            '90%_MPIW': m90_cqr['MPIW'],
            '90%_NMPIW_%': m90_cqr['NMPIW_%'],
            '95%_Nominal_Target_%': 95.0,
            '95%_PICP_%': m95_cqr['PICP_%'],
            '95%_Raw_PICP_%': m95_raw['PICP_%'],
            '95%_CQR_Calibrated_PICP_%': m95_cqr['PICP_%'],
            '95%_MPIW': m95_cqr['MPIW'],
            '95%_NMPIW_%': m95_cqr['NMPIW_%']
        })

        cqr_comparison_records.append({
            'Target': t,
            'Unit': units[t],
            'Test_Samples': len(y_te),
            '90%_Nominal_%': 90.0,
            '90%_Raw_QRF_PICP_%': m90_raw['PICP_%'],
            '90%_Raw_QRF_MPIW': m90_raw['MPIW'],
            '90%_CQR_Offset': cqr_offsets[t]['90%'],
            '90%_CQR_Calibrated_PICP_%': m90_cqr['PICP_%'],
            '90%_CQR_Calibrated_MPIW': m90_cqr['MPIW'],
            '95%_Nominal_%': 95.0,
            '95%_Raw_QRF_PICP_%': m95_raw['PICP_%'],
            '95%_Raw_QRF_MPIW': m95_raw['MPIW'],
            '95%_CQR_Offset': cqr_offsets[t]['95%'],
            '95%_CQR_Calibrated_PICP_%': m95_cqr['PICP_%'],
            '95%_CQR_Calibrated_MPIW': m95_cqr['MPIW']
        })

    unc_df = pd.DataFrame(uncertainty_records)
    cqr_comp_df = pd.DataFrame(cqr_comparison_records)

    unc_csv_path = csv_dir / "uncertainty_bounds_quantile_rf.csv"
    cqr_comp_path = csv_dir / "uncertainty_bounds_cqr_comparison.csv"

    unc_df.to_csv(unc_csv_path, index=False)
    unc_df.to_csv(legacy_results_dir / "uncertainty_bounds_quantile_rf.csv", index=False)
    cqr_comp_df.to_csv(cqr_comp_path, index=False)
    cqr_comp_df.to_csv(legacy_results_dir / "uncertainty_bounds_cqr_comparison.csv", index=False)

    print(f"[+] Saved Quantile RF Uncertainty Bounds CSV to:\n    - {unc_csv_path}")
    print(f"[+] Saved CQR Conformal Calibration Comparison CSV to:\n    - {cqr_comp_path}")

    # -------------------------------------------------------------------------
    # PART 5: TIER 5 COMPARATIVE ANALYSIS
    # -------------------------------------------------------------------------
    print("\n" + "-" * 85)
    print("ANALYZING TIER 5: DEMONSTRATING WHY MAPE FAILS ON LOW OC AND P")
    print("-" * 85)
    
    tier5_demo = []
    for t in ['OC', 'P']:
        y_true = df_preds[f"{t}_Actual"].values
        y_pred = df_preds[f"{t}_Pred_Random_Forest"].values
        q25 = np.percentile(y_true, 25)
        low_mask = y_true <= q25
        high_mask = y_true > q25

        mape_low = PedometricMetrics.mape(y_true[low_mask], y_pred[low_mask])
        mape_high = PedometricMetrics.mape(y_true[high_mask], y_pred[high_mask])
        mae_low = PedometricMetrics.mae(y_true[low_mask], y_pred[low_mask])
        mae_high = PedometricMetrics.mae(y_true[high_mask], y_pred[high_mask])

        tier5_demo.append({
            'Nutrient': t,
            'Low_Range_Threshold': f"<= {q25:.2f} {units[t]}",
            'Low_Range_MAE': round(mae_low, 3),
            'Low_Range_MAPE_%': round(mape_low, 1),
            'Upper_Range_MAE': round(mae_high, 3),
            'Upper_Range_MAPE_%': round(mape_high, 1),
            'Explanation': 'Near-zero denominators artificially blow up percentage error despite tiny absolute deviation.'
        })

    tier5_df = pd.DataFrame(tier5_demo)
    tier5_csv_path = csv_dir / "tier5_metrics_demonstration.csv"
    tier5_df.to_csv(tier5_csv_path, index=False)
    tier5_df.to_csv(legacy_results_dir / "tier5_metrics_demonstration.csv", index=False)
    print(f"[+] Saved Tier 5 Failure Demonstration CSV to:\n    - {tier5_csv_path}")

    # -------------------------------------------------------------------------
    # PART 6: PUBLICATION-READY VISUALIZATION DASHBOARD
    # -------------------------------------------------------------------------
    print("\n" + "-" * 85)
    print("GENERATING PUBLICATION PEDOMETRICS EVALUATION DASHBOARD")
    print("-" * 85)

    fig = plt.figure(figsize=(18, 12), dpi=300)
    gs = fig.add_gridspec(2, 3, hspace=0.32, wspace=0.25)

    # Subplot 1: Tier 1 (RMSE & MAE)
    ax1 = fig.add_subplot(gs[0, 0])
    rf_eval = eval_df_out[eval_df_out['Model'] == 'Random Forest'].set_index('Target')
    x = np.arange(len(targets))
    w = 0.35
    rmse_norm = [rf_eval.loc[t, 'NRMSE_Range_%'] for t in targets]
    mae_norm = [(rf_eval.loc[t, 'MAE'] / (df_preds[f"{t}_Actual"].max() - df_preds[f"{t}_Actual"].min())) * 100 for t in targets]
    ax1.bar(x - w/2, rmse_norm, w, label='NRMSE (Range %)', color='#2b5c8f', edgecolor='#333333', alpha=0.85)
    ax1.bar(x + w/2, mae_norm, w, label='NMAE (Range %)', color='#41b6c4', edgecolor='#333333', alpha=0.85)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{t}\n({units[t]})" for t in targets], fontweight='bold')
    ax1.set_ylabel('Normalized Error (% of Range)', fontweight='bold')
    ax1.set_title('Tier 1: Core Normalized Error Metrics\n(Out-of-Time 2025–26)', fontweight='bold', fontsize=11)
    ax1.legend(loc='upper right', frameon=True, fontsize=9)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    # Subplot 2: Tier 2 (RPIQ & RPD)
    ax2 = fig.add_subplot(gs[0, 1])
    rpiq_vals = [rf_eval.loc[t, 'RPIQ'] for t in targets]
    rpd_vals = [rf_eval.loc[t, 'RPD'] for t in targets]
    ax2.bar(x - w/2, rpiq_vals, w, label='RPIQ (IQR / RMSE)', color='#2ca02c', edgecolor='#333333', alpha=0.85)
    ax2.bar(x + w/2, rpd_vals, w, label='RPD (SD / RMSE)', color='#74c476', edgecolor='#333333', alpha=0.85)
    ax2.axhline(1.4, color='#e6550d', linestyle=':', linewidth=1.5, label='Fair Threshold (1.4)')
    ax2.axhline(2.0, color='#31a354', linestyle='--', linewidth=1.5, label='Good/Excellent (2.0)')
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{t}" for t in targets], fontweight='bold')
    ax2.set_ylabel('Pedometric Ratio', fontweight='bold')
    ax2.set_title('Tier 2: Pedometric Standards (RPIQ & RPD)\nAcademic Value (Bellon-Maurel et al.)', fontweight='bold', fontsize=11)
    ax2.legend(loc='upper right', frameon=True, fontsize=8)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    # Subplot 3: Tier 2 Lin's CCC vs. Pearson r
    ax3 = fig.add_subplot(gs[0, 2])
    ccc_vals = [rf_eval.loc[t, 'CCC'] for t in targets]
    pr_vals = [pearsonr(df_preds[f"{t}_Actual"], df_preds[f"{t}_Pred_Random_Forest"])[0] for t in targets]
    ax3.bar(x - w/2, ccc_vals, w, label="Lin's CCC (Concordance)", color='#756bb1', edgecolor='#333333', alpha=0.85)
    ax3.bar(x + w/2, pr_vals, w, label="Pearson's r (Linearity)", color='#bcbddc', edgecolor='#333333', alpha=0.85)
    ax3.set_xticks(x)
    ax3.set_xticklabels(targets, fontweight='bold')
    ax3.set_ylabel('Agreement Index', fontweight='bold')
    ax3.set_title("Tier 2: Lin's CCC vs. Pearson's r\nPenalizes Location/Scale Shift", fontweight='bold', fontsize=11)
    ax3.legend(loc='lower right', frameon=True, fontsize=8)
    ax3.grid(axis='y', linestyle='--', alpha=0.5)

    # Subplot 4: Tier 4 Quantile RF Coverage (PICP)
    ax4 = fig.add_subplot(gs[1, 0])
    picp_90 = [unc_df.loc[unc_df['Target'] == t, '90%_PICP_%'].values[0] for t in targets]
    picp_95 = [unc_df.loc[unc_df['Target'] == t, '95%_PICP_%'].values[0] for t in targets]
    ax4.bar(x - w/2, picp_90, w, label='Observed PICP (90% Nominal)', color='#e7298a', edgecolor='#333333', alpha=0.85)
    ax4.bar(x + w/2, picp_95, w, label='Observed PICP (95% Nominal)', color='#e78ac3', edgecolor='#333333', alpha=0.85)
    ax4.axhline(90.0, color='#222222', linestyle='--', linewidth=1.2, label='Nominal 90% Target')
    ax4.axhline(95.0, color='#666666', linestyle=':', linewidth=1.2, label='Nominal 95% Target')
    ax4.set_xticks(x)
    ax4.set_xticklabels(targets, fontweight='bold')
    ax4.set_ylabel('Coverage Probability (%)', fontweight='bold')
    ax4.set_title('Tier 4: Uncertainty Bounds (PICP)\nQuantile Random Forest Coverage', fontweight='bold', fontsize=11)
    ax4.set_ylim(50, 105)
    ax4.legend(loc='lower right', frameon=True, fontsize=8)
    ax4.grid(axis='y', linestyle='--', alpha=0.5)

    # Subplot 5: Tier 4 Interval Width (MPIW)
    ax5 = fig.add_subplot(gs[1, 1])
    nmpiw_90 = [unc_df.loc[unc_df['Target'] == t, '90%_NMPIW_%'].values[0] for t in targets]
    nmpiw_95 = [unc_df.loc[unc_df['Target'] == t, '95%_NMPIW_%'].values[0] for t in targets]
    ax5.bar(x - w/2, nmpiw_90, w, label='90% PI Width (% of Range)', color='#fd8d3c', edgecolor='#333333', alpha=0.85)
    ax5.bar(x + w/2, nmpiw_95, w, label='95% PI Width (% of Range)', color='#fdd0a2', edgecolor='#333333', alpha=0.85)
    ax5.set_xticks(x)
    ax5.set_xticklabels(targets, fontweight='bold')
    ax5.set_ylabel('Interval Width (% of Range)', fontweight='bold')
    ax5.set_title('Tier 4: Interval Sharpness (MPIW)\nTightness of Uncertainty Bounds', fontweight='bold', fontsize=11)
    ax5.legend(loc='upper left', frameon=True, fontsize=8)
    ax5.grid(axis='y', linestyle='--', alpha=0.5)

    # Subplot 6: Tier 5 Empirical Demonstration
    ax6 = fig.add_subplot(gs[1, 2])
    oc_actual = df_preds['OC_Actual'].values
    oc_pred = df_preds['OC_Pred_Random_Forest'].values
    sample_mape = np.abs((oc_actual - oc_pred) / np.maximum(oc_actual, 0.05)) * 100.0
    
    ax6.scatter(oc_actual, sample_mape, c=oc_actual, cmap='plasma_r',
                alpha=0.6, edgecolors='none', s=35)
    ax6.axvline(0.3, color='red', linestyle='--', linewidth=1.5, label='Critical OC Threshold (0.3%)')
    ax6.set_xlabel('Ground Truth Organic Carbon (%)', fontweight='bold')
    ax6.set_ylabel('Sample-wise Absolute % Error (APE %)', fontweight='bold')
    ax6.set_title('Tier 5 Demonstration: Why MAPE Fails\nNear-Zero Denominator Explosion in Soil OC', fontweight='bold', fontsize=11)
    ax6.set_yscale('log')
    ax6.legend(loc='upper right', frameon=True, fontsize=8)
    ax6.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    dashboard_plot_path = fig_dir / "pedometric_evaluation_dashboard.png"
    plt.savefig(dashboard_plot_path)
    # Also save to legacy results dir
    shutil.copy(dashboard_plot_path, legacy_results_dir / "pedometric_evaluation_dashboard.png")
    plt.close()
    print(f"[+] Saved Pedometric Dashboard to:\n    - {dashboard_plot_path}\n    - {legacy_results_dir / 'pedometric_evaluation_dashboard.png'}")

    return eval_df_out, unc_df, tier5_df


if __name__ == "__main__":
    run_full_pedometric_evaluation()
