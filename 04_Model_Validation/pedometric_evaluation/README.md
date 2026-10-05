# Pedometric & Regression Evaluation Suite
### AgriCare: Digital Soil Nutrient Mapping (MBU Final Year Project)
**Location:** `04_Model_Validation/pedometric_evaluation/`

This module provides a rigorous, standardized, 5-tier evaluation framework specifically tailored for **Digital Soil Mapping (DSM)** and **Soil Spectroscopy / SCORPAN modeling**.

---

## 📁 Directory Organization

```
04_Model_Validation/pedometric_evaluation/
├── __init__.py                         # Package entrypoint (exposes PedometricMetrics)
├── pedometric_metrics.py               # Core 5-tier evaluation engine & runner
├── README.md                           # Documentation & mathematical standards
└── results/
    ├── csv/                            # Exported benchmark CSV tables
    │   ├── production_master_metrics_summary.csv          # Master unified CV & pedometric metrics summary table
    │   ├── pedometric_comprehensive_metrics_2025_2026.csv # Out-of-time test set (RF, Ridge, PLSR, Calibrated)
    │   ├── pedometric_metrics_production_cv.csv           # 5-fold CV on production ExtraTrees (45 features)
    │   ├── statistical_significance_ttest.csv             # Statistical hypothesis testing (t-test & p-test)
    │   ├── uncertainty_bounds_quantile_rf.csv             # Tier 4 PICP & MPIW (90% & 95% nominal PIs)
    │   └── tier5_metrics_demonstration.csv                # Empirical proof of MAPE failure on low OC & P
    └── figures/                        # Publication-quality charts & dashboard
        └── pedometric_evaluation_dashboard.png            # 6-panel academic dashboard (300 DPI)
```

---

## 🎯 5-Tier Evaluation Hierarchy

| Tier | Metrics | Academic / Pedometric Standard |
| :--- | :--- | :--- |
| **Tier 1: Mandatory Core** | $R^2$, RMSE, MAE | Standard baseline regression metrics. |
| **Tier 2: Pedometric & Soil Standards** | RPIQ, RPD, Lin's CCC, Bias (MBE) | **High Academic Value**: RPIQ (Bellon-Maurel et al., 2010) handles skewed soil distributions; Lin's CCC measures 1:1 line concordance; MBE identifies location shifts. |
| **Tier 3: Scale Normalization & Skewness**| $NRMSE_{range}$, $NRMSE_{mean}$, RMSLE, Adjusted $R^2$ | RMSLE handles log-normal distributions for P & K; Adjusted $R^2$ verifies feature ablation without over-parameterization. |
| **Tier 4: Uncertainty Bounds** | PICP (Coverage %), MPIW (Interval Width) | Quantile Random Forest uncertainty bounds (90% and 95% nominal intervals). |
| **Tier 5: Avoid in Soil Analysis** | MAPE, NSE/KGE, AIC/BIC | **Caveats**: MAPE explodes on near-zero OC/P ($>400\%$); NSE/KGE are hydrology-specific; AIC/BIC are linear/parametric only. |
| **Statistical Hypothesis Testing** | Student's $t$-test, $p$-value ($p$-test) | **Significance Testing**: Correlation significance ($t = r\sqrt{\frac{N-2}{1-r^2}}$, $p < 0.001$), one-sample residual $t$-test for Mean Bias ($H_0: \text{MBE}=0$), and paired $t$-tests between models. Saved in `statistical_significance_ttest.csv`. |

---

## 🚀 Quick Execution

### Run Evaluation from Terminal:
```bash
python 04_Model_Validation/pedometric_evaluation/pedometric_metrics.py
```

### Import in Python Code:
```python
from pedometric_evaluation import PedometricMetrics

metrics = PedometricMetrics.evaluate_all(
    y_true=y_actual,
    y_pred=y_predicted,
    p_features=45,               # For Adjusted R²
    lower_bounds=q05_quantiles,  # For Tier 4 PICP & MPIW (optional)
    upper_bounds=q95_quantiles   # For Tier 4 PICP & MPIW (optional)
)
```
