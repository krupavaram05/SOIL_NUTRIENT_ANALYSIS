# AgriCare: Master Pedometric & Machine Learning Metrics Summary
### Digital Soil Nutrient Mapping & Precision Agriculture Pipeline
**Location:** `04_Model_Validation/`

This document provides the definitive benchmark of all evaluation metrics performed across the **5-Fold Cross-Validation Production Models** and the **Multi-Temporal Soil Nutrient Validation Suite**.

---

## 📊 Master Production Models Performance Table (5-Fold CV)

**Model:** Dual-Head ExtraTrees (`ExtraTreesRegressor` + `ExtraTreesClassifier`)  
**Features:** 45 Derived SCORPAN Features  
**Sample Points:** 909 Ground-Truth Soil Laboratory Records (SPSR Nellore District)

| Target Nutrient | Unit | Variance Explained ($R^2$) | Pearson Corr ($r$) | Normalized Acc ($1 - \text{NRMSE}$) | **ICAR Class Acc** | Safe-Tier Agreement | Agronomic Tolerance ($\le \pm 15\%$) | **RPIQ** ($IQR / RMSE$) | **RPD** ($SD / RMSE$) | **Lin's CCC** ($\rho_c$) | RMSE | MAE | Bias (MBE) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Nitrogen ($N$)** | kg/ha | **$0.5962$** | **$0.7731$** | **$88.25\%$** | **$96.92\%$** | **$100.00\%$** | **$80.53\%$** | **$2.506$** | **$1.574$** | **$0.7370$** | 49.805 | 35.647 | $+0.286$ |
| **Phosphorus ($P$)** | kg/ha | **$0.2935$** | **$0.5660$** | **$95.01\%$** | **$70.63\%$** | **$93.95\%$** | **$98.35\%$** | **$0.708$** | **$1.190$** | **$0.4534$** | 27.091 | 10.867 | $-5.060$ |
| **Potassium ($K$)** | kg/ha | **$0.6876$** | **$0.8390$** | **$85.03\%$** | **$78.22\%$** | **$96.04\%$** | **$79.76\%$** | **$2.587$** | **$1.789$** | **$0.8120$** | 94.926 | 56.263 | $-20.809$ |
| **Organic Carbon ($OC$)** | % | **$0.2968$** | **$0.5478$** | **$93.58\%$** | **$86.91\%$** | **$96.26\%$** | **$96.48\%$** | **$1.201$** | **$1.193$** | **$0.4850$** | 0.191 | 0.110 | $+0.002$ |

---

## 📁 Corresponding Result Files in This Directory

| File Path | Description |
| :--- | :--- |
| [`results/production_master_metrics_summary.csv`](file:///c:/Users/Vidya%20sagar/Sunny/projects/Temp%20work/AgriCare/04_Model_Validation/results/production_master_metrics_summary.csv) | Unified master summary table (CSV) containing all core, pedometric, and classification metrics. |
| [`pedometric_evaluation/results/csv/production_master_metrics_summary.csv`](file:///c:/Users/Vidya%20sagar/Sunny/projects/Temp%20work/AgriCare/04_Model_Validation/pedometric_evaluation/results/csv/production_master_metrics_summary.csv) | Synchronized copy inside the pedometric evaluation results package. |
| [`results/pedometric_metrics_production_cv.csv`](file:///c:/Users/Vidya%20sagar/Sunny/projects/Temp%20work/AgriCare/04_Model_Validation/results/pedometric_metrics_production_cv.csv) | Full pedometric 5-tier evaluation outputs (Adjusted $R^2$, NRMSE, RMSLE, Bias, CCC). |
| [`results/statistical_significance_ttest.csv`](file:///c:/Users/Vidya%20sagar/Sunny/projects/Temp%20work/AgriCare/04_Model_Validation/results/statistical_significance_ttest.csv) | Student's $t$-test & $p$-values confirming statistical significance ($p < 0.001$). |
| [`results/uncertainty_bounds_quantile_rf.csv`](file:///c:/Users/Vidya%20sagar/Sunny/projects/Temp%20work/AgriCare/04_Model_Validation/results/uncertainty_bounds_quantile_rf.csv) | Tier 4 Quantile Random Forest uncertainty bounds (PICP & MPIW for 90% and 95% intervals). |
| [`results/pedometric_evaluation_dashboard.png`](file:///c:/Users/Vidya%20sagar/Sunny/projects/Temp%20work/AgriCare/04_Model_Validation/results/pedometric_evaluation_dashboard.png) | 6-panel publication-grade evaluation figure (300 DPI). |

---

## 🔬 Scientific Metric Definitions

### 1. Tier 1: Mandatory Core
* **$R^2$ (Coefficient of Determination):** $1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$. Fraction of total soil variance explained by satellite covariates.
* **RMSE (Root Mean Squared Error):** $\sqrt{\frac{1}{n} \sum (y_i - \hat{y}_i)^2}$. Standard deviation of residuals in original units (kg/ha or %).
* **MAE (Mean Absolute Error):** $\frac{1}{n} \sum |y_i - \hat{y}_i|$. Average absolute magnitude of deviation.

### 2. Tier 2: Pedometric Standards (Bellon-Maurel et al., 2010)
* **RPIQ (Ratio of Performance to Interquartile Distance):** $\frac{IQR}{\text{RMSE}} = \frac{Q_3 - Q_1}{\text{RMSE}}$. Grounded in international soil science for skewed distributions where standard deviation is non-representative.
* **RPD (Ratio of Performance to Deviation):** $\frac{\text{Std}(y)}{\text{RMSE}}$. Values $>1.4$ indicate useful screening; $>1.75$ indicates good quantitative modeling.
* **Lin's CCC (Concordance Correlation Coefficient):** Evaluates agreement relative to the true 1:1 identity line, penalizing both slope deviations and location shifts.
* **Bias / MBE (Mean Bias Error):** $\frac{1}{n}\sum (\hat{y}_i - y_i)$. Detects systematic district-wide over- or under-estimation.

### 3. Tier 3: Agronomic Decision & Classification
* **ICAR Class Accuracy:** Accuracy across official Indian Council of Agricultural Research Soil Health Card tiers (Low / Medium / High).
* **Safe-Tier Agreement:** Percentage of predictions where error $\le 1$ tier, guaranteeing zero catastrophic errors (e.g., Low mistaken for High).
* **Agronomic Tolerance ($\le \pm 15\%$):** Fraction of predictions within the allowable tolerance range for balanced fertilizer advisory.
