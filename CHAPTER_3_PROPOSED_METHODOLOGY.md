# CHAPTER 3: PROPOSED METHODOLOGY

## 3.1 Detailed Explanation of System Architecture Schematic

### 3.1.1 Study Area and Data Sources
The study area is SPSR Nellore District, Andhra Pradesh, a semi-arid coastal district in which an irrigated delta (paddy) coexists with rainfed uplands (cotton, groundnut, maize). Ground-truth soil chemistry comes from government Soil Health Cards (SHC). Four properties are modelled: Available Nitrogen (N), Available Phosphorus (P), and Available Potassium (K), all in kg/ha, and Soil Organic Carbon (OC, %). The comprehensive modelling dataset contains 909 geo-referenced laboratory records. For the temporal experiments, three harmonized Sentinel-2 SCORPAN datasets for the agricultural cycles 2023–24 (948 samples), 2024–25 (952 samples), and 2025–26 (938 samples) are used. Four open data sources supply the explanatory covariates:

1. **Sentinel-2 MSI Level-2A (ESA Copernicus, `COPERNICUS/S2_SR_HARMONIZED`):** 12 surface-reflectance bands at 10 to 60 m spatial resolution.
2. **SRTM Digital Elevation Model (NASA, 30 m):** Elevation and terrain derivatives (slope, aspect, hillshade, curvature, Topographic Wetness Index).
3. **ERA5-Land reanalysis and TerraClimate:** Soil moisture and temperature, land surface temperature, precipitation, potential evapotranspiration, aridity, and vapor pressure deficit.
4. **ISRIC SoilGrids (250 m):** Clay, silt, and sand fractions (g/kg).

All raster layers are processed on Google Earth Engine (GEE), so no imagery has to be downloaded locally and the same workflow scales seamlessly from a single agricultural plot to the entire district.

---

### 3.1.2 System Architecture
AgriCare is organized into five sequential stages that mirror the structure of the project repository (Figure 3.1):
* **Stage 1 (`01_OCR_Raw_Data`):** Digitizes the paper ground-truth records using computer vision and OCR.
* **Stage 2 (`02_Satellite_Covariates`):** Extracts satellite and environmental covariates at every geo-referenced sample location on GEE.
* **Stage 3 (`03_Feature_Engineering`):** Engineers and selects the multi-physics SCORPAN feature set.
* **Stage 4 (`04_Model_Validation`):** Validates models across three rigorous tiers (random 5-fold, spatial-block, and temporal out-of-time), adapts them to new agricultural cycles via few-shot domain calibration ($K=25$), and quantifies prediction uncertainty with Conformalized Quantile Regression (CQR).
* **Stage 5 (`05_Production_Models`):** Trains production dual-head models and converts predicted fertility tiers into ANGRAU precision fertilizer prescriptions (Urea, DAP, MOP in kg/acre).

```
========================================================================================================
                      AgriCare: 5-Stage Digital Soil Mapping Architecture
========================================================================================================
 [Stage 1: Ground-Truth Digitization]  --> Soil Health Cards -> OpenCV + EasyOCR -> 909-sample ground truth
                 │
                 ▼
 [Stage 2: Covariate Extraction]       --> Sentinel-2 L2A (Bare-soil) + SRTM DEM + ERA5-Land + SoilGrids
                 │
                 ▼
 [Stage 3: Feature Engineering]        --> 39 Baseline Covariates + 3 Interactions + 3 Spatial = 45 Features
                 │
                 ▼
 [Stage 4: Validation & Calibration]   --> Random CV + Spatial Block CV + Few-Shot (K=25) + CQR Bounds
                 │
                 ▼
 [Stage 5: Production & Advisory]      --> Dual-Head ExtraTrees (Continuous + ICAR) -> ANGRAU Fertilizer Doses
========================================================================================================
```
*Figure 3.1: High-Level Schematic of the 5-Stage Digital Soil Mapping Pipeline.*

The design follows the SCORPAN paradigm of digital soil mapping (McBratney et al., 2003):
$$S = f(s, c, o, r, p, a, n)$$
where $s$ is soil, $c$ is climate, $o$ is organisms/vegetation, $r$ is relief/topography, $p$ is parent material, $a$ is time/age, and $n$ is spatial coordinates.

---

## 3.2 Modular Breakdown of the Technical Pipeline

### 3.2.1 Data Digitization and Computer Vision Pipeline (Stage 1)
Historical ground truth in Andhra Pradesh is stored on printed bilingual (Telugu and English) Soil Health Cards, frequently degraded by scanning artifacts, folds, and ink smudges. Manual transcription is error-prone and time-consuming, necessitating an automated computer-vision pipeline.

Each scanned card is converted to grayscale, binarized using an adaptive Gaussian threshold that accommodates non-uniform lighting, and dilated morphologically to isolate table grid lines and text regions. Text bounding boxes are passed to EasyOCR, combining a convolutional feature extractor, a bidirectional recurrent network, and Connectionist Temporal Classification (CTC) decoding. Regular expressions parse numerical attributes for Latitude, Longitude, Available N, P, K (kg/ha), and Soil Organic Carbon (%). A strict range filter discards physically impossible values (e.g., $N > 600\text{ kg/ha}$ or $OC > 5.0\%$). A secondary vision-language model parser (LLaVA via Ollama) serves as an alternative for cards with low OCR confidence scores.

#### Algorithm 1: Soil Health Card Digitization
```text
Input: Set of scanned card images I
Output: Validated ground-truth table G (lat, lon, N, P, K, OC)
 1: G <- empty set
 2: for each image I in I do
 3:     S <- Grayscale(I); B <- AdaptiveGaussianThreshold(S); D <- Dilate(B)
 4:     R <- LocalizeBoxes(D)               # Table grid and text-region bounding boxes
 5:     T <- EasyOCR.Recognize(R)           # Telugu + English text
 6:     (lat, lon, N, P, K, OC) <- RegexParse(T)
 7:     if any field is missing or (lat, lon) is invalid then continue
 8:     if value is physically impossible (e.g., N > 600 or OC > 5.0) then continue
 9:     G <- G U {(lat, lon, N, P, K, OC)}
10: end for
11: return G                                # Exported to Soil_Test_Results.xlsx
```

---

### 3.2.2 Cloud Geospatial Covariate Extraction on Google Earth Engine (Stage 2)
Sentinel-2 Level-2A bottom-of-atmosphere surface reflectance is ingested via Google Earth Engine (`COPERNICUS/S2_SR_HARMONIZED`).

#### Table 3.1: Sentinel-2 Multispectral Instrument (MSI) Spectral Band Specifications
| Band | Central $\lambda$ (nm) | Bandwidth (nm) | Spatial Resolution | Pedological / Agronomic Sensitivity |
| :--- | :---: | :---: | :---: | :--- |
| **B1 Coastal Aerosol** | 443 | 20 | 60 m | Atmospheric scattering correction |
| **B2 Blue** | 490 | 65 | 10 m | Organic matter absorption; ferric iron oxides |
| **B3 Green** | 560 | 35 | 10 m | Chlorophyll reflectance peak |
| **B4 Red** | 665 | 30 | 10 m | Chlorophyll and ferric iron (hematite) absorption |
| **B5 Red Edge 1** | 705 | 15 | 20 m | Crop canopy / vegetation stress boundary |
| **B6 Red Edge 2** | 740 | 15 | 20 m | Leaf mesophyll structure; nitrogen proxy |
| **B7 Red Edge 3** | 783 | 20 | 20 m | Canopy biomass density |
| **B8 Broad NIR** | 842 | 115 | 10 m | Structural cellular scattering |
| **B8A Narrow NIR**| 865 | 20 | 20 m | Narrow NIR plateau; organic carbon absorption |
| **B9 Water Vapor** | 945 | 20 | 60 m | Atmospheric water-vapor absorption |
| **B11 SWIR 1** | 1610 | 90 | 20 m | Clay-mineral OH absorption; topsoil moisture |
| **B12 SWIR 2** | 2190 | 180 | 20 m | C-H organic carbon absorption; carbonates |

#### Bare-Soil Compositing Window
To eliminate green vegetation and cloud contamination, imagery is restricted to the pre-sowing window (**1 April to 30 June**), when agricultural parcels in SPSR Nellore are ploughed and free of standing crops. Clouds are masked via the QA60 bitmask and Scene Classification Layer (SCL). For every clear pixel, the Normalized Difference Vegetation Index (NDVI) and Bare Soil Index (BSI) are evaluated:
$$\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}} \tag{3.1}$$
$$\text{BSI} = \frac{(\text{B11} + \text{B4}) - (\text{B8} + \text{B2})}{(\text{B11} + \text{B4}) + (\text{B8} + \text{B2})} \tag{3.2}$$

A pixel is retained only when it fulfills the dual physical bare-soil condition:
$$M(t) = \begin{cases} 1, & \text{if } \text{NDVI}(t) < 0.25 \text{ and } \text{BSI}(t) > 0.05 \\ 0, & \text{otherwise} \end{cases} \tag{3.3}$$
$$\rho_b = \text{median}_{t} \{ \rho_b(t) : M(t) = 1 \}, \quad b \in \{\text{B1}, \dots, \text{B12}\} \tag{3.4}$$

The temporal median reducer removes residual cloud shadows and sensor anomalies. Environmental covariates from SRTM DEM (30 m), ERA5-Land / TerraClimate, and ISRIC SoilGrids (250 m) are sampled synchronously at the ground-truth coordinates.

#### Algorithm 2: Bare-Soil Composite and Covariate Extraction
```text
Input: Sample coordinates P = {(lat, lon)}, Window [1 Apr, 30 Jun], tau_NDVI = 0.25, tau_BSI = 0.05
Output: Base covariate table X_base (|P| x 39)
 1: C <- Sentinel2_L2A.FilterDate(Window).FilterBounds(Nellore)
 2: for each image s in C do
 3:     s <- MaskClouds(s, QA60, SCL)
 4:     compute NDVI(s) and BSI(s) using Eqs. (3.1) and (3.2)
 5:     s' <- s restricted to pixels with NDVI < tau_NDVI and BSI > tau_BSI
 6: end for
 7: rho <- PerBandTemporalMedian({s'})          # 12-band bare-soil composite
 8: T <- TerrainDerivatives(SRTM_30m)            # 7 variables (Elevation, Slope, TWI, Curvature, etc.)
 9: Q <- ClimateLayers(ERA5-Land, TerraClimate)  # 7 variables (Moisture, Temp, LST, VPD, PET, etc.)
10: S <- SoilGrids(clay, sand, silt)             # 3 texture fractions
11: for each p = (lat, lon) in P do
12:     row <- Sample(rho, p) U Sample(T, p) U Sample(Q, p) U Sample(S, p) U {lat, lon}
13:     append spectral indices (Section 3.2.3) to row
14: end for
15: return X_base
```

---

### 3.2.3 SCORPAN Feature Engineering and Mathematical Formulations (Stage 3)
The baseline matrix comprises 39 covariates. Six domain interaction terms are engineered, producing **45 model input features**:

#### Spectral Indices:
$$\text{NDRE} = \frac{\text{B8} - \text{B5}}{\text{B8} + \text{B5}} \tag{3.5}$$
$$\text{EVI} = 2.5 \cdot \frac{\text{B8} - \text{B4}}{\text{B8} + 6.0 \cdot \text{B4} - 7.5 \cdot \text{B2} + 1.0} \tag{3.6}$$
$$\text{SAVI} = 1.5 \cdot \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4} + 0.5} \tag{3.7}$$
$$\text{Clay\_Ratio} = \frac{\text{B11}}{\text{B12}} \tag{3.8}$$
$$\text{OC\_Index} = \frac{\text{B5} - \text{B6}}{\text{B4} + \text{B8}} \tag{3.9}$$
$$\text{Cumulative\_Integral\_NDVI} = \int_{t_1}^{t_2} \text{NDVI}(t) \, dt \tag{3.10}$$

#### Topographic & Atmospheric Derivations:
$$\text{Aspect\_Sin} = \sin(\theta), \quad \text{Aspect\_Cos} = \cos(\theta) \quad (\theta = \text{aspect in radians}) \tag{3.11}$$
$$\text{TWI} = \ln\left( \frac{a}{\tan \beta} \right) \tag{3.12}$$
$$\text{VPD} = 0.6108 \cdot \exp\left( \frac{17.27 \cdot T}{T + 237.3} \right) \cdot \left( 1 - \frac{RH}{100} \right) \tag{3.13}$$

#### Physical Interactions & Spatial Polynomials:
$$\text{Clay} \times \text{Moisture} = \text{Clay\_Fraction} \cdot \text{Soil\_Moisture\_0\_7cm}$$
$$\text{Temp} \times \text{VPD} = \text{Soil\_Temp\_K} \cdot \text{VPD\_kpa}$$
$$\text{BSI/NDVI} = \frac{\text{BSI}}{|\text{NDVI}| + \epsilon} \tag{3.14}$$
*(where $\epsilon = 0.05$ represents an empirical regularization constant, with absolute denominator $|\text{NDVI}|$ applied to prevent numerical singularity across bare-soil parcels).*

$$\text{Lat}^2 = (\text{Latitude} - 14.6642)^2, \quad \text{Lon}^2 = (\text{Longitude} - 79.7775)^2$$
$$\text{Lat} \times \text{Lon} = (\text{Latitude} - 14.6642) \cdot (\text{Longitude} - 79.7775) \tag{3.15}$$

#### Table 3.2: Complete Catalog of 45 SCORPAN Model Features
| Feature Category | Count | Variables Included | Pedological / Agronomic Rationale |
| :--- | :---: | :--- | :--- |
| **1. Sentinel-2 Bands** | 12 | B1, B2, B3, B4, B5, B6, B7, B8, B8A, B9, B11, B12 | Direct surface reflectance across VIS, NIR, and SWIR |
| **2. Spectral Indices** | 8 | NDVI, NDRE, EVI, SAVI, BSI, Clay_Ratio, OC_Index, Cumulative_Integral_NDVI | Biomass vigor, soil background, clay minerals, organic carbon |
| **3. Geomorphometry** | 7 | Elevation_m, Slope_deg, Hillshade, TWI, Terrain_Curvature, Aspect_Sin, Aspect_Cos | Runoff accumulation, hydrological wetness, topographic drainage |
| **4. Climatic Reanalysis** | 7 | Soil_Moisture_0_7cm, Soil_Temp_K, LST_K, Precipitation_m, PET_mm, Aridity_Index, VPD_kpa | Weathering rate, evaporative demand, soil moisture regime |
| **5. Texture & Space** | 5 | Clay, Sand, Silt fractions (g/kg), Latitude, Longitude | Soil mineral matrix, cation exchange capacity, spatial coordinates |
| **6. Physical Interactions** | 3 | Clay_x_Moisture, Temp_x_VPD, BSI_div_NDVI | Multi-domain physical couplings |
| **7. Spatial Polynomials** | 3 | Spatial_Lat2, Spatial_Lon2, Spatial_Lat_Lon | Macro-scale regional spatial trend surface |

#### Preprocessing & Skewness Correction
Missing values are imputed using median training values, and all covariates are normalized using z-score standardization fitted strictly on training splits to prevent data leakage:
$$x' = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}} \tag{3.16}$$

Available Phosphorus ($P$) and Potassium ($K$) exhibit strong positive skewness. During training, both targets undergo logarithmic transformation:
$$y_{\text{trans}} = \ln(1 + y), \quad \hat{y} = \max\left(0, \, \exp(\hat{y}_{\text{trans}}) - 1\right) \tag{3.17}$$

---

### 3.2.4 Feature Selection and Incremental Ablation
Three feature spaces were benchmarked per nutrient:
1. **Full Feature Matrix (Branch A):** 39 baseline SCORPAN covariates.
2. **Orthogonal PCA Transformation (Branch B):** Principal components retaining $\ge 95\%$ cumulative variance (15 PCs).
3. **Consensus Subset (Branch C):** Intersection of Top-10 Random Forest Mean Decrease in Impurity (MDI) importance and Top-10 Recursive Feature Elimination (RFE), with TreeSHAP computed for interpretability.

In parallel, Zayani incremental ablation curves evaluated marginal predictive contributions by adding covariate groups sequentially: Bands (12) $\rightarrow$ +Indices (20) $\rightarrow$ +Topography (27) $\rightarrow$ +Climate (34) $\rightarrow$ +Texture/Space (39).

---

### 3.2.5 Dual-Head Machine Learning Architecture (Stage 5)
Post-hoc thresholding of continuous regression predictions generates severe boundary errors near class limits. AgriCare therefore introduces a **Dual-Head ExtraTrees architecture** operating in parallel on the identical 45-feature matrix:

* **Head A (Continuous Regressor):** `ExtraTreesRegressor` (350 trees, max_depth=16, min_samples_leaf=2, max_features=0.65). Random thresholding provides robust variance reduction across collinear multispectral features.
* **Head B (ICAR Fertility Classifier):** Dedicated `ExtraTreesClassifier` (300 trees, max_depth=14, min_samples_leaf=2, max_features=0.65) trained directly on statutory Indian Council of Agricultural Research (ICAR) fertility classes:
$$\text{tier}(v) = \begin{cases} 0 \text{ (Low)}, & \text{if } v < L \\ 1 \text{ (Medium)}, & \text{if } L \le v \le H \\ 2 \text{ (High)}, & \text{if } v > H \end{cases} \tag{3.18}$$

The classifier posterior probability and reported confidence are:
$$P(c \mid x) = \frac{1}{M} \sum_{m=1}^{M} P_m(c \mid x) \tag{3.19}$$
$$\text{Confidence (\%)} = \max_c P(c \mid x) \cdot 100 \tag{3.20}$$

#### Table 3.3: Statutory ICAR Soil Fertility Classification Scales
| Soil Nutrient / Property | Low (Tier 0) | Medium (Tier 1) | High (Tier 2) | Official Standard & Laboratory Method |
| :--- | :---: | :---: | :---: | :--- |
| **Available Nitrogen ($N$)** | $< 280\text{ kg/ha}$ | $280\text{--}560\text{ kg/ha}$ | $> 560\text{ kg/ha}$ | Alkaline $\text{KMnO}_4$ Distillation (Subbiah & Asija) |
| **Available Phosphorus ($P$, Olsen)** | **$< 10\text{ kg/ha}$**<br>*(equiv. $< 23\text{ kg/ha } P_2O_5$)* | **$10\text{--}25\text{ kg/ha}$**<br>*(equiv. $23\text{--}56\text{ kg/ha } P_2O_5$)* | **$> 25\text{ kg/ha}$**<br>*(equiv. $> 56\text{ kg/ha } P_2O_5$)* | Olsen's $0.5\text{M } \text{NaHCO}_3$ Spectrophotometry |
| **Available Potassium ($K$)** | **$< 140\text{ kg/ha}$**<br>*(equiv. $< 168\text{ kg/ha } K_2O$)* | **$140\text{--}280\text{ kg/ha}$**<br>*(equiv. $168\text{--}337\text{ kg/ha } K_2O$)* | **$> 280\text{ kg/ha}$**<br>*(equiv. $> 337\text{ kg/ha } K_2O$)* | Neutral $1\text{N } \text{NH}_4\text{OAc}$ Flame Photometry |
| **Soil Organic Carbon ($OC$)** | $< 0.50\%$ | $0.50\text{--}0.75\%$ | $> 0.75\%$ | Walkley-Black Wet Dichromate Oxidation |

*(Note: Laboratory Soil Health Cards record elemental quantities for $P$ and $K$. For commercial fertilizer conversion, stoichiometric factors $P \times 2.29 = P_2O_5$ and $K \times 1.20 = K_2O$ are applied).*

---

### 3.2.6 Multi-Level Validation Framework (Stage 4)
To audit spatial and temporal transferability, validation is structured into three levels:

1. **Random 5-Fold Cross-Validation:** Standard baseline validation over 909 ground-truth samples.
2. **Spatial Block Cross-Validation (Tobler's Law Audit):** Partitions sample coordinates into 5 regional geographic clusters using Spatial K-Means. `GroupKFold` holds out entire non-overlapping geographic blocks, providing honest regional out-of-field generalization metrics.
3. **Temporal Out-of-Time Cross-Cycle Test:** Trained on historical cycles 2023–24 and 2024–25 ($\approx 1,900$ points) and evaluated on the unseen 2025–26 cycle (938 points).

#### Evaluated Pedometric & Agronomic Metrics:
$$\text{RPD} = \frac{\text{SD}(y)}{\text{RMSE}}, \quad \text{RPIQ} = \frac{\text{IQR}(y)}{\text{RMSE}} = \frac{Q_3 - Q_1}{\text{RMSE}} \tag{3.21}$$
$$\text{MBE} = \frac{1}{n} \sum_{i=1}^{n} (\hat{y}_i - y_i) \tag{3.22}$$
$$\text{CCC} = \frac{2 \cdot r \cdot \sigma_y \cdot \sigma_{\hat{y}}}{\sigma_y^2 + \sigma_{\hat{y}}^2 + (\mu_y - \mu_{\hat{y}})^2} \tag{3.23}$$
$$\text{Safe-Tier Agreement (\%)} = \frac{100}{n} \sum_{i=1}^{n} \mathbf{1}[|\hat{c}_i - c_i| \le 1] \tag{3.24}$$

---

### 3.2.7 Few-Shot Seasonal Calibration Engine (Stage 4)
Inter-annual monsoon variations alter baseline soil moisture and surface albedo, causing temporal drift. AgriCare estimates this drift using a small anchor set ($K = 25$ test points drawn from the new season). The mean residual offset is added to all remaining un-sampled predictions:
$$\Delta = \frac{1}{K} \sum_{i=1}^{K} (y_{i, \text{true}} - \hat{y}_{i, \text{base}}) \tag{3.25}$$
$$\hat{y}_{\text{calibrated}} = \max\left(0, \, \hat{y}_{\text{base}} + \Delta\right) \tag{3.26}$$

The single additive constant prevents anchor overfitting, requires no model retraining, and reduces cross-season RMSE by $32.4\%$.

---

### 3.2.8 Prediction Uncertainty: Conformalized Quantile Regression (CQR)
Point estimates alone do not convey risk. AgriCare equips predictions with statistically valid prediction intervals. A Random Forest (350 trees, max_depth=12) is fitted on $80\%$ proper training data. Raw quantiles ($5\% / 95\%$ for $90\%$ interval; $2.5\% / 97.5\%$ for $95\%$ interval) under-cover true field observations due to finite bagging variance.

**Conformalized Quantile Regression (Romano et al., NeurIPS 2019)** computes non-conformity scores on a held-out $20\%$ calibration set:
$$E_i = \max\left( \hat{q}_{\text{lo}}(x_i) - y_i, \, y_i - \hat{q}_{\text{hi}}(x_i) \right) \tag{3.27}$$
$$\hat{q}_{\text{conf}} = \text{Quantile of } \{E_i\} \text{ at level } \frac{\lceil (1 - \alpha)(n + 1) \rceil}{n} \tag{3.28}$$
$$\text{CQR Interval} = \left[ \max(0, \, \hat{q}_{\text{lo}} - \hat{q}_{\text{conf}}), \quad \hat{q}_{\text{hi}} + \hat{q}_{\text{conf}} \right]$$

This mathematically guarantees empirical test coverage: $\text{PICP} \ge 1 - \alpha$.

---

### 3.2.9 ANGRAU Precision Fertilizer Advisory Engine (Stage 5)
Predicted ICAR fertility tiers are converted into actionable commercial fertilizer prescriptions (Urea, DAP, MOP in kg/acre) using Acharya N.G. Ranga Agricultural University (ANGRAU) baseline recommendations:

#### Table 3.4: ANGRAU Baseline Fertilizer Recommendations for Major Crops in SPSR Nellore
| Crop | Baseline N (kg/ha) | Baseline $\text{P}_2\text{O}_5$ (kg/ha) | Baseline $\text{K}_2\text{O}$ (kg/ha) | Target Yield (q/ha) |
| :--- | :---: | :---: | :---: | :---: |
| **Paddy (Irrigated Delta)** | 120 | 60 | 40 | 65 – 75 |
| **Maize (Kharif / Rabi)** | 150 | 60 | 50 | 70 – 80 |
| **Cotton (Rainfed / Irrigated)** | 120 | 60 | 60 | 25 – 30 |
| **Groundnut (Spanish Bunch)** | 20 | 40 | 50 | 25 – 35 |

Dosages are scaled by statutory tier factors $f \in \{1.25 \text{ (Low)}, \, 1.00 \text{ (Medium)}, \, 0.75 \text{ (High)}\}$:
$$R_N = N_{\text{base}} \cdot f_N, \quad R_P = P_2O_{5, \text{base}} \cdot f_P, \quad R_K = K_2O_{\text{base}} \cdot f_K \tag{3.29}$$

Because Di-Ammonium Phosphate (DAP) contains $18\%\text{ N}$ and $46\%\text{ P}_2\text{O}_5$, DAP is computed first, and its nitrogen contribution is credited against Urea:
$$\text{DAP (kg/ha)} = \frac{R_P}{0.46}, \quad N_{\text{DAP}} = 0.18 \cdot \text{DAP} \tag{3.30}$$
$$\text{Urea (kg/ha)} = \frac{\max(0, \, R_N - N_{\text{DAP}})}{0.46}, \quad \text{MOP (kg/ha)} = \frac{R_K}{0.60} \tag{3.31}$$
$$\text{Prescription (kg/acre)} = \text{Dose (kg/ha)} \times 0.4047 \tag{3.32}$$

*Illustrative Example (Paddy: N=Low, P=Medium, K=High):*  
$R_N = 120 \times 1.25 = 150\text{ kg/ha}$, $R_P = 60\text{ kg/ha}$, $R_K = 40 \times 0.75 = 30\text{ kg/ha}$.  
$\text{DAP} = 60 / 0.46 = 130.4\text{ kg/ha}$ (supplies $23.5\text{ kg N}$);  
$\text{Urea} = (150 - 23.5) / 0.46 = 275.0\text{ kg/ha}$;  
$\text{MOP} = 30 / 0.60 = 50.0\text{ kg/ha}$.  
Converting to field units yields: **$52.8\text{ kg DAP}$**, **$111.3\text{ kg Urea}$**, and **$20.2\text{ kg MOP}$ per acre**.

---

## 3.3 Summary of Algorithmic Pipeline Mappings

#### Table 3.5: Summary of Algorithms in the AgriCare Framework
| Algorithm No. | Module & Lifecycle Stage | Primary Output | Core Computational Operations |
| :---: | :--- | :--- | :--- |
| **Alg 1** | Ground-Truth Digitization (Stage 1) | `Soil_Test_Results.xlsx` | Adaptive thresholding, CRAFT, EasyOCR, regex parsing, range validation |
| **Alg 2** | GEE Covariate Extraction (Stage 2) | 39 Baseline Covariates | QA60/SCL masking, NDVI/BSI bare-soil filters, temporal median compositing |
| **Alg 3** | SCORPAN Feature Assembly (Stage 3) | 45-D Scaled Matrix | Spectral indices, terrain aspect sin/cos, physical interactions, spatial polynomials |
| **Alg 4** | Feature Selection & Ablation (Stage 3) | Ablation curves, rankings | TreeSHAP, RF-MDI, RFE, 95% PCA, Zayani incremental ablation |
| **Alg 5** | Dual-Head Production Training (Stage 5) | Serialized models & preprocessors | ExtraTrees regressors & classifiers, $\ln(1+y)$ target transform |
| **Alg 6** | Spatial & Temporal Validation (Stage 4) | Regional & out-of-time metrics | K-Means spatial sectors, `GroupKFold`, 2-year train to 1-year test |
| **Alg 7** | Few-Shot Seasonal Calibration (Stage 4) | Drift-calibrated predictions | Residual offset $\Delta$ from $K=25$ ground anchors |
| **Alg 8** | Conformalized Quantile Reg (Stage 4) | $90\%$ and $95\%$ Prediction Intervals | Quantile RF, finite-sample holdout conformal offset $\hat{q}_{\text{conf}}$ |
| **Alg 9** | ANGRAU Fertilizer Advisory (Stage 5) | Farmer dosage (kg/acre) | Tier factor scaling, DAP-first nitrogen mass balance crediting |
