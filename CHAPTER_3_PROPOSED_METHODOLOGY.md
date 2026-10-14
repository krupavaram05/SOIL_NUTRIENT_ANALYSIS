# CHAPTER 3: PROPOSED METHODOLOGY

## 3.1 Detailed Explanation of System Architecture Schematic

### 3.1.1 Study Area and Data Sources
The study area is SPSR Nellore District, Andhra Pradesh, a semi-arid coastal district in which an irrigated delta (paddy) coexists with rainfed uplands (cotton, groundnut, maize). Ground-truth soil chemistry originates from official government Soil Health Cards (SHC). Four critical pedological properties are modelled: Available Nitrogen ($N$), Available Phosphorus ($P$), and Available Potassium ($K$), all expressed in kilograms per hectare ($\text{kg/ha}$), and Soil Organic Carbon ($OC$, $\%$). The comprehensive modelling dataset contains 909 geo-referenced laboratory records spanning 46 mandals. For multi-year temporal transferability experiments, three harmonized Sentinel-2 SCORPAN datasets for agricultural cycles 2023–24 (948 samples), 2024–25 (952 samples), and 2025–26 (938 samples) are utilized.

Four open-access geospatial and hydrometeorological data sources supply the explanatory covariates:
1. **Sentinel-2 Multispectral Instrument (MSI) Level-2A (`COPERNICUS/S2_SR_HARMONIZED`):** 12 bottom-of-atmosphere surface reflectance bands resampled to a uniform 10 m processing grid.
2. **NASA Shuttle Radar Topography Mission (SRTM) DEM (30 m):** Geomorphometric derivatives (elevation, slope, aspect, hillshade, terrain curvature, and Topographic Wetness Index).
3. **ECMWF ERA5-Land Reanalysis & TerraClimate (0.1° / 4 km):** Soil moisture (0–7 cm), soil temperature, land surface temperature, precipitation, potential evapotranspiration, aridity index, and vapor pressure deficit.
4. **ISRIC SoilGrids (250 m):** Clay, silt, and sand physical mineral fractions ($\text{g/kg}$).

All raster layers are ingested, harmonized, and processed directly within Google Earth Engine (GEE), eliminating local storage bottlenecks and ensuring scalability from a single agricultural parcel to regional scale.

---

### 3.1.2 System Architecture
AgriCare is structured into five sequential operational stages that strictly mirror the architecture of the project repository (Figure 3.1):
* **Stage 1 (`01_OCR_Raw_Data`):** Digitizes legacy paper Soil Health Cards using OpenCV morphological filters and EasyOCR with regular expression validators.
* **Stage 2 (`02_Satellite_Covariates`):** Ingests and composited bare-soil Sentinel-2 reflectance and samples environmental rasters on GEE.
* **Stage 3 (`03_Feature_Engineering`):** Constructs and evaluates the 47-dimensional multi-physics SCORPAN feature matrix.
* **Stage 4 (`04_Model_Validation`):** Validates predictive generalizability across three tiers (random, spatial-block, and temporal out-of-time), implements $N=25$ few-shot domain calibration, and establishes finite-sample prediction intervals via Conformalized Quantile Regression (CQR).
* **Stage 5 (`05_Production_Models`):** Executes production dual-head models (Hybrid VotingRegressor + ExtraTreesClassifier) and translates fertility classes into precision ANGRAU fertilizer mass-balance prescriptions in $\text{kg/acre}$.

```
========================================================================================================
                                     AGRICARE 5-STAGE PIPELINE ARCHITECTURE
========================================================================================================
 [Stage 1: Ground-Truth OCR]  ──►  [Stage 2: GEE Bare-Soil Extraction]  ──►  [Stage 3: SCORPAN Feature Matrix]
  EasyOCR + OpenCV bounding-        Pre-sowing window (Apr–Jun)              47 features (12 Bands, 8 Indices,
  box parser (N=909 SHC points).    BSI > 0.05, NDVI < 0.25 median.          7 Terrain, 7 Climate, 8 Interactions).
                                                                                         │
                                                                                         ▼
 [Stage 5: ANGRAU Advisory Engine] ◄── [Stage 4: Dual-Head & Few-Shot CQR] ◄────────────┘
  STCR Urea, DAP, MOP mass balance     Continuous VotingRegressor + ICAR
  prescription (kg/acre).              Classifier + N=25 Seasonal Anchor CQR.
========================================================================================================
```
*Figure 3.1: High-Level Schematic of the 5-Stage Digital Soil Mapping Pipeline.*

The architecture formalizes Hans Jenny's state factor model as extended by McBratney's SCORPAN digital soil mapping paradigm:
$$S = f(s, c, o, r, p, a, n)$$
where $s$ denotes soil properties (texture fractions), $c$ represents climatic forcing, $o$ signifies organisms and vegetation history, $r$ denotes relief/geomorphometry, $p$ represents parent material, $a$ denotes time/age, and $n$ designates geographic spatial coordinates.

---

## 3.2 Modular Breakdown of the Technical Pipeline

### 3.2.1 Stage 1: Soil Health Card Digitization & Computer Vision OCR Pipeline
Ground-truth soil records across Andhra Pradesh are maintained on printed, bilingual (Telugu and English) Soil Health Cards. These documents frequently suffer from skew, non-uniform illumination, ink smudges, and fold degradations. Manual transcription is error-prone and unscalable.

The automated Stage 1 pipeline executes in five sequential steps:
1. **Grayscale & Adaptive Binarization:** Scans are converted to grayscale and binarized using an adaptive Gaussian threshold ($C = 2$, block size $11 \times 11$) to compensate for uneven illumination.
2. **Morphological Grid Isolation:** Morphological dilation using a rectangular structuring element connects fragmented printed borders and isolates tabular cell regions.
3. **Bounding-Box Localization:** Connected components identify table cell coordinates and pass cropped bounding boxes to the optical character recognizer.
4. **Bilingual Text Recognition:** EasyOCR combines a ResNet convolutional backbone, a bidirectional LSTM sequence recognizer, and Connectionist Temporal Classification (CTC) decoding to parse Telugu and English text tokens.
5. **Regex Extraction & Range Filtering:** Regular expressions parse coordinates and nutrient quantities. Physical plausibility filters discard invalid laboratory entries ($N > 600\text{ kg/ha}$, $P > 150\text{ kg/ha}$, $K > 1200\text{ kg/ha}$, $OC > 5.0\%$). A secondary vision-language parser (LLaVA via Ollama) serves as a fallback for degraded cards with low OCR confidence.

#### Algorithm 1: Soil Health Card Digitization Pipeline
```text
Input: Set of scanned Soil Health Card images I
Output: Validated geo-referenced ground-truth table G (lat, lon, N, P, K, OC)
 1: G <- empty set
 2: for each image I in I do
 3:     S <- Grayscale(I);  B <- AdaptiveGaussianThreshold(S);  D <- Dilate(B)
 4:     R <- LocalizeBoundingBoxes(D)         # Tabular grid and cell segmentation
 5:     T <- EasyOCR.Recognize(R)             # Bilingual (Telugu + English) character recognition
 6:     (lat, lon, N, P, K, OC) <- RegexParse(T)
 7:     if (lat, lon) is outside SPSR Nellore bounds then continue
 8:     if any nutrient violates physical threshold (N > 600 or OC > 5.0) then continue
 9:     G <- G U {(lat, lon, N, P, K, OC)}
10: end for
11: return G                                  # Exported to Soil_Test_Results.xlsx (N = 909)
```

---

### 3.2.2 Stage 2: Cloud Geospatial Covariate Extraction via Google Earth Engine
Sentinel-2 Level-2A bottom-of-atmosphere surface reflectance is ingested via Google Earth Engine (`COPERNICUS/S2_SR_HARMONIZED`).

#### Resampling to Effective 10m Spatial Resolution
In Google Earth Engine, all 20 m and 60 m Sentinel-2 Level-2A surface reflectance bands are resampled to a uniform 10 m processing resolution via bilinear interpolation. This spatial alignment matches the 10 m visible and broad NIR bands (B2, B3, B4, B8), establishing an effective 10 m field-scale digital soil mapping matrix.

#### Table 3.1: Spectral Band Specifications of the Multispectral Instrument (Effective Resolution: 10m)
| Band Identifier | Central Wavelength ($\lambda$, nm) | Bandwidth (nm) | Processing Spatial Resolution | Physical Pedological Sensitivity |
| :--- | :---: | :---: | :---: | :--- |
| **B1 Coastal Aerosol** | 443 | 20 | 10 m (Resampled from 60m) | Atmospheric aerosol scattering correction |
| **B2 Blue** | 490 | 65 | 10 m (Native) | Organic matter absorption; iron oxide discrimination |
| **B3 Green** | 560 | 35 | 10 m (Native) | Chlorophyll reflectance peak; green peak |
| **B4 Red** | 665 | 30 | 10 m (Native) | Chlorophyll and ferric iron (hematite) absorption |
| **B5 Red Edge 1** | 705 | 15 | 10 m (Resampled from 20m) | Boundary of vegetation stress & canopy chlorophyll |
| **B6 Red Edge 2** | 740 | 15 | 10 m (Resampled from 20m) | Leaf cellular structure; surrogate for nitrogen |
| **B7 Red Edge 3** | 783 | 20 | 10 m (Resampled from 20m) | Canopy biomass density & Leaf Area Index |
| **B8 Broad NIR** | 842 | 115 | 10 m (Native) | Structural scattering by vegetation canopy |
| **B8A Narrow NIR** | 865 | 20 | 10 m (Resampled from 20m) | Narrow near-infrared plateau; organic carbon |
| **B9 Water Vapour** | 945 | 20 | 10 m (Resampled from 60m) | Atmospheric water-vapour column correction |
| **B11 SWIR 1** | 1610 | 90 | 10 m (Resampled from 20m) | Clay-mineral ($\text{O-H}$) lattice absorption & moisture |
| **B12 SWIR 2** | 2190 | 180 | 10 m (Resampled from 20m) | $\text{C-H}$ absorption in organic carbon; carbonates |

#### Bare-Soil Compositing Window
Standing agricultural canopies and atmospheric clouds attenuate topsoil reflectance. AgriCare restricts image ingestion to the dry pre-sowing window (**1 April to 30 June**), when agricultural parcels in SPSR Nellore are ploughed and free of standing crops.

Clouds and shadow pixels are eliminated via the QA60 bitmask and Scene Classification Layer (SCL). For every unmasked pixel, the Normalized Difference Vegetation Index (NDVI) and Bare Soil Index (BSI) are evaluated:
$$\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}} \tag{3.1}$$
$$\text{BSI} = \frac{(\text{B11} + \text{B4}) - (\text{B8} + \text{B2})}{(\text{B11} + \text{B4}) + (\text{B8} + \text{B2})} \tag{3.2}$$

A pixel observation at acquisition time $t$ is retained only when meeting the dual physical bare-soil threshold:
$$M(t) = \begin{cases} 1, & \text{if } \text{NDVI}(t) < 0.25 \text{ and } \text{BSI}(t) > 0.05 \\ 0, & \text{otherwise} \end{cases} \tag{3.3}$$
$$\rho_b = \text{median}_{t} \{ \rho_b(t) : M(t) = 1 \}, \quad b \in \{\text{B1}, \dots, \text{B12}\} \tag{3.4}$$

The temporal median reducer eliminates cloud shadow artifacts and transient illumination noise, producing a seamless bare-soil reflectance mosaic across Nellore. Environmental layers from SRTM DEM (30 m), ERA5-Land, and ISRIC SoilGrids (250 m) are sampled synchronously at the ground-truth coordinates.

#### Algorithm 2: Bare-Soil Composite and Covariate Extraction
```text
Input: Sample coordinates P = {(lat, lon)}, Pre-sowing window [1 Apr, 30 Jun], tau_NDVI = 0.25, tau_BSI = 0.05
Output: Base covariate table X_base (|P| x 39)
 1: C <- Sentinel2_L2A.FilterDate(window).FilterBounds(Nellore)
 2: for each image s in C do
 3:     s <- MaskClouds(s, QA60, SCL)
 4:     compute NDVI(s) and BSI(s) via Eqs. (3.1) and (3.2)
 5:     s' <- s restricted to pixels with NDVI < tau_NDVI and BSI > tau_BSI
 6: end for
 7: rho <- PerBandTemporalMedian({s'})          # 12-band resampled 10m bare-soil composite
 8: T <- TerrainDerivatives(SRTM_30m)            # 7 variables (Elevation, Slope, Aspect, TWI, etc.)
 9: Q <- ClimateLayers(ERA5-Land, TerraClimate)  # 7 variables (Moisture, Temp, LST, VPD, PET, etc.)
10: S <- SoilGrids(clay, sand, silt)             # 3 physical texture fractions
11: for each p = (lat, lon) in P do
12:     row <- Sample(rho, p) U Sample(T, p) U Sample(Q, p) U Sample(S, p) U {lat, lon}
13:     append spectral indices (Section 3.2.3) to row
14: end for
15: return X_base                                # 39 baseline covariates per sample
```

---

### 3.2.3 Stage 3: SCORPAN Feature Engineering & Multi-Physics Synthesis
The baseline matrix comprises 39 covariates. Eight domain interaction and spatial terms are engineered across three specialized categories, expanding the matrix to **47 model input features**:

#### Spectral Indices (8 features):
$$\text{NDRE} = \frac{\text{B8} - \text{B5}}{\text{B8} + \text{B5}} \tag{3.5}$$
$$\text{EVI} = 2.5 \cdot \frac{\text{B8} - \text{B4}}{\text{B8} + 6.0 \cdot \text{B4} - 7.5 \cdot \text{B2} + 1.0} \tag{3.6}$$
$$\text{SAVI} = 1.5 \cdot \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4} + 0.5} \tag{3.7}$$
$$\text{Clay\_Ratio} = \frac{\text{B11}}{\text{B12}} \tag{3.8}$$
$$\text{OC\_Index} = \frac{\text{B5} - \text{B6}}{\text{B4} + \text{B8}} \tag{3.9}$$
$$\text{Cumulative\_Integral\_NDVI} = \int_{t_1}^{t_2} \text{NDVI}(t) \, dt \tag{3.10}$$

#### Topographic & Atmospheric Derivatives (7 features each):
$$\text{Aspect\_Sin} = \sin(\theta), \quad \text{Aspect\_Cos} = \cos(\theta) \quad (\theta = \text{aspect in radians}) \tag{3.11}$$
$$\text{TWI} = \ln\left( \frac{a}{\tan \beta} \right) \tag{3.12}$$
$$\text{VPD} = 0.6108 \cdot \exp\left( \frac{17.27 \cdot T}{T + 237.3} \right) \cdot \left( 1 - \frac{RH}{100} \right) \tag{3.13}$$

#### Physical Interactions, Spatial Polynomials, and Soil-Terrain Hydrology (8 features):
$$\text{Clay} \times \text{Moisture} = \text{Clay\_Fraction} \cdot \text{Soil\_Moisture\_0\_7cm}$$
$$\text{Temp} \times \text{VPD} = \text{Soil\_Temp\_K} \cdot \text{VPD\_kpa}$$
$$\text{BSI/NDVI} = \frac{\text{BSI}}{|\text{NDVI}| + 0.05} \tag{3.14}$$

$$\text{Lat}^2 = (\text{Latitude} - 14.6642)^2, \quad \text{Lon}^2 = (\text{Longitude} - 79.7775)^2$$
$$\text{Lat} \times \text{Lon} = (\text{Latitude} - 14.6642) \cdot (\text{Longitude} - 79.7775) \tag{3.15}$$

$$\text{Clay} \times \text{Elevation} = \text{Clay\_Fraction} \cdot \text{Elevation\_m} \tag{3.16}$$
$$\text{Moisture} / \text{Slope} = \frac{\text{Soil\_Moisture\_0\_7cm}}{\text{Slope\_deg} + 0.1} \tag{3.17}$$

The soil-terrain hydrology interaction terms capture sediment redistribution, catenary position, and drainage ponding across the coastal plain.

#### Table 3.2: Complete Catalog of 47 Engineered SCORPAN Features in AgriCare
| Category | Count | Variable Names / Symbols | Physical Domain Rationale |
| :--- | :---: | :--- | :--- |
| **1. Sentinel-2 Bands** | 12 | B1, B2, B3, B4, B5, B6, B7, B8, B8A, B9, B11, B12 | Direct optical and shortwave infrared reflectance (effective 10m) |
| **2. Spectral Indices** | 8 | NDVI, NDRE, EVI, SAVI, BSI, Clay_Ratio, OC_Index, Cumulative_Integral_NDVI | Vegetation vigor, bare soil albedo, clay/carbon absorption |
| **3. Geomorphometry** | 7 | Elevation_m, Slope_deg, Hillshade, TWI, Terrain_Curvature, Aspect_Sin, Aspect_Cos | Topographic water accumulation, illumination, drainage |
| **4. Climate Reanalysis** | 7 | Soil_Moisture, Soil_Temp, LST_K, Precip_Mean, PET, Aridity_Index, VPD | Thermodynamic soil moisture, weathering, evapotranspiration |
| **5. Texture & Space** | 5 | Clay_Fraction, Sand_Fraction, Silt_Fraction, Latitude, Longitude | Physical mineral matrix, cation exchange, coordinates |
| **6. Physical Interactions** | 3 | Clay_x_Moisture, Temp_x_VPD, BSI_div_NDVI | Coupled hydrological and atmospheric evaporative demand |
| **7. Spatial Polynomials** | 3 | Spatial_Lat2, Spatial_Lon2, Spatial_Lat_Lon | Macro-scale geographic trend surface across Nellore delta |
| **8. Soil-Terrain Hydrology** | 2 | Clay_x_Elevation, Moisture_div_Slope | Sediment redistribution & erosion-deposition dynamics |

#### Preprocessing & Logarithmic Transformation
Missing values are imputed using column medians, and features are standardized to zero mean and unit variance using parameters fitted exclusively on the training fold:
$$x' = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}}$$

Available Phosphorus ($P$) and Potassium ($K$) exhibit pronounced right-skewness. Targets are normalized via natural logarithmic transformation before model fitting and exponentiated post-prediction:
$$y_{\text{trans}} = \ln(1 + y) \implies \hat{y} = \max\left(0, \, \exp(\hat{y}_{\text{trans}}) - 1\right) \tag{3.18}$$

#### Feature Selection and Incremental Ablation
Three feature selection paradigms were benchmarked:
1. **Full Feature Matrix:** 39 baseline SCORPAN covariates.
2. **Orthogonal PCA Transformation:** Components retaining $\ge 95\%$ cumulative variance (15 PCs).
3. **Consensus Subset:** Intersection of Top-10 Random Forest MDI importance and Top-10 Recursive Feature Elimination (RFE), with TreeSHAP computed for interpretability.

Ablation experiments prove that optical satellite bands alone yield a mean $R^2 = 0.3415$. Progressively layering geomorphometry ($R^2 = 0.4120$), climate ($R^2 = 0.4682$), texture ($R^2 = 0.4935$), and the 8 physical interaction terms elevates overall mean $R^2$ to **$0.5207$**.

#### Algorithm 3: Feature Construction and Leakage-Free Preprocessing
```text
Input: X_base (n x 39), training indices T, evaluation indices E
Output: Scaled feature matrices X_T, X_E (n x 47)
 1: for each row x in X_base do
 2:     compute Aspect_Sin, Aspect_Cos from Aspect_deg                   # Eq. (3.11)
 3:     compute Clay_x_Moisture, Temp_x_VPD, BSI_div_NDVI                # Eq. (3.14)
 4:     compute Spatial_Lat2, Spatial_Lon2, Spatial_Lat_Lon              # Eq. (3.15)
 5:     compute Clay_x_Elevation, Moisture_div_Slope                     # Eqs. (3.16), (3.17)
 6: end for
 7: assert column count == 47 (12 + 8 + 7 + 7 + 5 + 3 + 3 + 2)
 8: Imputer <- SimpleImputer(strategy='median').fit(X[T])
 9: X <- Imputer.transform(X)
10: Scaler <- StandardScaler().fit(X[T]);  X <- Scaler.transform(X)
11: for nutrient j in {P, K} do  y_j <- ln(1 + y_j)                      # Eq. (3.18)
12: return X[T], X[E], Imputer, Scaler
```

---

### 3.2.4 Stage 4: Dual-Head Machine Learning Architecture & Multi-Tier Validation
To resolve boundary classification errors caused by post-hoc thresholding, AgriCare operates a **Dual-Head Architecture**:

* **Head A (Continuous Regressor):** A hybrid `VotingRegressor` combining $70\%$ `ExtraTreesRegressor` (350 trees, max_depth=16, min_samples_leaf=2, max_features=0.65) and $30\%$ `GradientBoostingRegressor`:
$$\hat{y}_{\text{continuous}} = 0.70 \cdot \hat{y}_{\text{ExtraTrees}} + 0.30 \cdot \hat{y}_{\text{GradientBoosting}} \tag{3.19}$$
* **Head B (ICAR Fertility Classifier):** Dedicated `ExtraTreesClassifier` (300 trees, max_depth=14, min_samples_leaf=2, max_features=0.65) trained directly on statutory Indian Council of Agricultural Research (ICAR) fertility ratings:
$$\text{tier}(v) = \begin{cases} 0 \text{ (Low)}, & \text{if } v < L \\ 1 \text{ (Medium)}, & \text{if } L \le v \le H \\ 2 \text{ (High)}, & \text{if } v > H \end{cases} \tag{3.20}$$

The classification posterior and associated decision confidence are:
$$P(c \mid x) = \frac{1}{M} \sum_{m=1}^{M} P_m(c \mid x) \tag{3.21}$$
$$\text{Confidence (\%)} = \max_c P(c \mid x) \cdot 100 \tag{3.22}$$

#### Table 3.3: Statutory ICAR Soil Fertility Classification Scales
| Soil Nutrient / Property | Low (Tier 0) | Medium (Tier 1) | High (Tier 2) | Official Analytical Method |
| :--- | :---: | :---: | :---: | :--- |
| **Available Nitrogen ($N$)** | $< 280\text{ kg/ha}$ | $280\text{--}560\text{ kg/ha}$ | $> 560\text{ kg/ha}$ | Alkaline $\text{KMnO}_4$ Distillation |
| **Available Phosphorus ($P$, Olsen)** | **$< 10\text{ kg/ha}$**<br>*(equiv. $< 23\text{ kg/ha } P_2O_5$)* | **$10\text{--}25\text{ kg/ha}$**<br>*(equiv. $23\text{--}56\text{ kg/ha } P_2O_5$)* | **$> 25\text{ kg/ha}$**<br>*(equiv. $> 56\text{ kg/ha } P_2O_5$)* | Olsen's $0.5\text{M } \text{NaHCO}_3$ Spectrophotometry |
| **Available Potassium ($K$)** | **$< 140\text{ kg/ha}$**<br>*(equiv. $< 168\text{ kg/ha } K_2O$)* | **$140\text{--}280\text{ kg/ha}$**<br>*(equiv. $168\text{--}337\text{ kg/ha } K_2O$)* | **$> 280\text{ kg/ha}$**<br>*(equiv. $> 337\text{ kg/ha } K_2O$)* | Neutral $1\text{N } \text{NH}_4\text{OAc}$ Flame Photometry |
| **Soil Organic Carbon ($OC$)** | $< 0.50\%$ | $0.50\text{--}0.75\%$ | $> 0.75\%$ | Walkley-Black Wet Oxidation |

*(Note: Soil Health Card wet chemistry tests report elemental quantities for $P$ and $K$. For commercial fertilizer conversion, stoichiometric factors $P \times 2.29 = P_2O_5$ and $K \times 1.20 = K_2O$ are applied).*

#### Multi-Tier Validation Framework
1. **Random 5-Fold Cross-Validation:** Baseline pedometric assessment over 909 ground-truth samples.
2. **Spatial Block Cross-Validation (Tobler's Law Audit):** Partitions sample coordinates into 5 geographic clusters using $5\text{km} \times 5\text{km}$ spatial grids or administrative `Mandal_ID` clusters with `GroupKFold(n_splits=5)`. Entire spatial sectors are held out to eliminate autocorrelation leakage.
3. **Temporal Out-of-Time Cross-Cycle Test:** Trained on historical cycles 2023–24 and 2024–25 ($\approx 1,900$ points) and evaluated on the unseen 2025–26 cycle (938 points).

#### Pedometric & Agronomic Evaluation Metrics
$$\text{RPD} = \frac{\text{SD}(y)}{\text{RMSE}}, \quad \text{RPIQ} = \frac{\text{IQR}(y)}{\text{RMSE}} = \frac{Q_3 - Q_1}{\text{RMSE}} \tag{3.23}$$
$$\text{MBE} = \frac{1}{n} \sum_{i=1}^{n} (\hat{y}_i - y_i) \tag{3.24}$$
$$\text{CCC} = \frac{2 \cdot r \cdot \sigma_y \cdot \sigma_{\hat{y}}}{\sigma_y^2 + \sigma_{\hat{y}}^2 + (\mu_y - \mu_{\hat{y}})^2} \tag{3.25}$$
$$\text{Safe-Tier Agreement (\%)} = \frac{100}{n} \sum_{i=1}^{n} \mathbf{1}[|\hat{c}_i - c_i| \le 1]$$

> [!CAUTION]
> **Prohibition of MAPE in Soil Pedometrics:** Mean Absolute Percentage Error (MAPE) is strictly prohibited in soil nutrient evaluation. Near-zero laboratory values ($OC \le 0.3\%$, Olsen $P \le 5\text{ kg/ha}$) cause percentage error to diverge ($>400\%$) despite negligible absolute error ($\text{MAE} = 0.08\%$). Performance is rigorously audited using RMSE, MAE, RPIQ, and Lin's CCC.

---

### 3.2.5 Few-Shot Seasonal Calibration Engine
Inter-annual monsoon variability and sensor calibration drift cause systematic residual bias ($\text{MBE} = +19.74\text{ kg/ha}$ for $N$, $+80.82\text{ kg/ha}$ for $K$). To eliminate the cost of widespread re-sampling, AgriCare implements a few-shot adaptation engine using $N = 25$ randomly sampled anchor points from the new season:
$$\Delta = \frac{1}{K} \sum_{i=1}^{K} (y_{i, \text{true}} - \hat{y}_{i, \text{base}}) \tag{3.26}$$
$$\hat{y}_{\text{calibrated}} = \max\left(0, \, \hat{y}_{\text{base}} + \Delta\right) \tag{3.27}$$

This additive calibration requires no model retraining, avoids anchor overfitting, recovers Nitrogen $R^2$ from $0.3420$ back to $0.5840$, and reduces cross-season RMSE by $32.4\%$.

---

### 3.2.6 Prediction Uncertainty: Conformalized Quantile Regression (CQR)
Point forecasts provide insufficient risk quantification for smallholder farmers. Raw Quantile Random Forest (QRF) intervals suffer from empirical undercoverage ($73.56\%$ for $N$, $75.27\%$ for $K$, $77.19\%$ for $OC$) on out-of-time test data.

AgriCare implements **Conformalized Quantile Regression (CQR; Romano, Patterson & Candès, NeurIPS 2019)**. On a held-out $20\%$ calibration set ($N_{\text{calib}} \approx 180$), non-conformity scores are computed:
$$E_i = \max\left( \hat{q}_{\alpha/2}(x_i) - y_i, \; y_i - \hat{q}_{1-\alpha/2}(x_i) \right) \tag{3.28}$$

The empirical conformal correction quantile $\hat{q}_{\text{conf}}$ is calculated at level:
$$\text{Level} = \frac{\lceil (N_{\text{calib}} + 1)(1 - \alpha) \rceil}{N_{\text{calib}}}$$

Test intervals are adjusted by expanding raw quantiles by $\hat{q}_{\text{conf}}$:
$$\text{Interval}_{\text{calibrated}} = \left[ \max\left(0, \, \hat{q}_{\alpha/2}(x_{\text{test}}) - \hat{q}_{\text{conf}}\right), \; \hat{q}_{1-\alpha/2}(x_{\text{test}}) + \hat{q}_{\text{conf}} \right] \tag{3.29}$$

This provably guarantees empirical coverage $\text{PICP} \ge 90.0\%$ (achieving $95.10\%$ for $P$, $92.86\%$ for $OC$, and $\ge 90\%$ under seasonal drift).

#### Algorithm 8: Conformalized Quantile Regression (CQR) Calibration
```text
Input: Scaled training set (X, y), Test set X_test, Miscoverage alpha = 0.10 (90% nominal)
Output: Calibrated prediction intervals, PICP, MPIW
 1: Split (X, y) randomly (seed 42) into proper-training (80%) and calibration (20%, N_calib)
 2: for each target j in {N, P, K, OC} do
 3:     RF <- RandomForestRegressor(350 trees, depth 12).fit(proper-training, y_trans)
 4:     Extract tree predictions on calibration and test sets; invert log1p for P and K
 5:     (q_lo_cal, q_hi_cal) <- per-sample 5% and 95% quantiles on calibration set
 6:     (q_lo_te, q_hi_te)   <- per-sample 5% and 95% quantiles on test set
 7:     E_i <- max(q_lo_cal - y_cal, y_cal - q_hi_cal)                    # Non-conformity score, Eq. (3.28)
 8:     q_conf <- Quantile of {E_i} at ceil((1 - alpha) * (N_calib + 1)) / N_calib
 9:     Interval_te <- [max(0, q_lo_te - q_conf), q_hi_te + q_conf]       # Calibrated bounds, Eq. (3.29)
10:     PICP <- mean(y_test in Interval_te) * 100
11:     MPIW <- mean(Interval_te.upper - Interval_te.lower)
12: end for
13: return Interval_te, PICP, MPIW
```

---

### 3.2.7 Stage 5: ANGRAU Precision Fertilizer Advisory Engine
Predicted ICAR fertility ratings feed directly into Acharya N.G. Ranga Agricultural University (ANGRAU) Soil Test Crop Response (STCR) mass-balance equations, automating plot-specific commercial fertilizer prescriptions in kilograms per acre:

#### Table 3.4: ANGRAU Baseline Fertilizer Recommendations for Major Crops in SPSR Nellore
| Crop | Baseline N ($\text{kg/ha}$) | Baseline $\text{P}_2\text{O}_5$ ($\text{kg/ha}$) | Baseline $\text{K}_2\text{O}$ ($\text{kg/ha}$) | Target Yield ($\text{q/ha}$) |
| :--- | :---: | :---: | :---: | :---: |
| **Paddy (Irrigated Delta)** | 120 | 60 | 40 | 65 – 75 |
| **Maize (Kharif / Rabi)** | 150 | 60 | 50 | 70 – 80 |
| **Cotton (Rainfed / Irrigated)** | 120 | 60 | 60 | 25 – 30 |
| **Groundnut (Spanish Bunch)** | 20 | 40 | 50 | 25 – 35 |

Dosages are modulated by statutory tier factors $f \in \{1.25 \text{ (Low)}, \, 1.00 \text{ (Medium)}, \, 0.75 \text{ (High)}\}$:
$$R_N = N_{\text{base}} \cdot f_N, \quad R_P = P_2O_{5, \text{base}} \cdot f_P, \quad R_K = K_2O_{\text{base}} \cdot f_K \tag{3.30}$$

Commercial fertilizers supply fixed nutrient concentrations: Urea ($46\%\text{ N}$), Di-Ammonium Phosphate (DAP; $18\%\text{ N}, 46\%\text{ P}_2\text{O}_5$), and Muriate of Potash (MOP; $60\%\text{ K}_2\text{O}$). Because DAP simultaneously supplies nitrogen, DAP dosage is fixed first from phosphorus demand, and its nitrogen contribution is credited against Urea:
$$\text{DAP (kg/ha)} = \frac{R_P}{0.46}, \quad N_{\text{DAP}} = 0.18 \cdot \text{DAP} \tag{3.31}$$
$$\text{Urea (kg/ha)} = \frac{\max\left(0, \, R_N - N_{\text{DAP}}\right)}{0.46}, \quad \text{MOP (kg/ha)} = \frac{R_K}{0.60} \tag{3.32}$$
$$\text{Dose (kg/acre)} = \text{Dose (kg/ha)} \times 0.4047 \tag{3.33}$$

#### Algorithm 9: ANGRAU Fertilizer Advisory Engine
```text
Input: Crop name, Predicted ICAR tiers (t_N, t_P, t_K), Baseline Table 3.4
Output: Commercial Urea, DAP, and MOP recommendations (kg/acre)
 1: (N_b, P_b, K_b) <- BaselineTable[Crop]
 2: f(t) <- 1.25 if t == Low; 1.00 if t == Medium; 0.75 if t == High
 3: R_N <- N_b * f(t_N);  R_P <- P_b * f(t_P);  R_K <- K_b * f(t_K)       # Eq. (3.30)
 4: DAP_ha <- R_P / 0.46;  N_credit <- 0.18 * DAP_ha                      # Eq. (3.31)
 5: Urea_ha <- max(0, R_N - N_credit) / 0.46                              # Eq. (3.32)
 6: MOP_ha <- R_K / 0.60
 7: return (Urea_ha, DAP_ha, MOP_ha) * 0.4047                             # kg/acre, Eq. (3.33)
```

---

### 3.2.8 Future Multi-Sensor & Micronutrient Extensions
To address the optical sensing limitations for non-reflective phosphate ions and trace elements, three future extensions are integrated into the system roadmap:
1. **Sentinel-1 C-Band SAR Radar Fusion:** Ingesting dual-polarization backscatter ($\gamma^0_{VV}, \gamma^0_{VH}$ in dB) and radar indices ($\text{Ratio} = \text{VH}/\text{VV}$, $\text{RVI} = \frac{4 \cdot \text{VH}}{\text{VV} + \text{VH}}$) to penetrate dense canopies and directly sense dielectric topsoil moisture.
2. **Spaceborne Hyperspectral Ingestion (PRISMA & EnMAP):** Leveraging 240 contiguous spectral bands ($400\text{--}2500\text{ nm}$) to map narrow diagnostic absorption doublets for organic matter and carbonate minerals.
3. **12-Parameter Soil Health Card Expansion:** Extending classification heads to secondary ($S, Ca, Mg$) and micronutrients ($Zn, Fe, B, Cu, Mn$) to overcome yield ceilings governed by Liebig's Law of the Minimum.

---

## 3.3 Summary of Algorithmic Pipeline Mappings

#### Table 3.5: Summary of Algorithms in the AgriCare Framework
| Algorithm No. | Module & Lifecycle Stage | Primary Output | Core Computational Operations |
| :---: | :--- | :--- | :--- |
| **Alg 1** | Ground-Truth Digitization (Stage 1) | `Soil_Test_Results.xlsx` | Adaptive thresholding, CRAFT, EasyOCR, regex parsing, range validation |
| **Alg 2** | GEE Covariate Extraction (Stage 2) | 39 Baseline Covariates | QA60/SCL masking, NDVI/BSI bare-soil filters, temporal median compositing |
| **Alg 3** | SCORPAN Feature Assembly (Stage 3) | 47-D Scaled Matrix | Spectral indices, terrain aspect sin/cos, physical interactions, spatial polynomials |
| **Alg 4** | Feature Selection & Ablation (Stage 3) | Ablation curves, rankings | TreeSHAP, RF-MDI, RFE, 95% PCA, Zayani incremental ablation |
| **Alg 5** | Dual-Head Production Training (Stage 4) | Serialized models & preprocessors | Hybrid VotingRegressor (70ET+30GBDT) & ExtraTreesClassifier, $\ln(1+y)$ transform |
| **Alg 6** | Spatial & Temporal Validation (Stage 4) | Regional & out-of-time metrics | $5\text{km} \times 5\text{km}$ K-Means / Mandal `GroupKFold`, 2-year train to 1-year test |
| **Alg 7** | Few-Shot Seasonal Calibration (Stage 4) | Drift-calibrated predictions | Residual offset $\Delta$ from $K=25$ ground anchors |
| **Alg 8** | Conformalized Quantile Reg (Stage 4) | $90\%$ and $95\%$ Prediction Intervals | Quantile RF, finite-sample holdout conformal offset $\hat{q}_{\text{conf}}$ |
| **Alg 9** | ANGRAU Fertilizer Advisory (Stage 5) | Farmer dosage (kg/acre) | Tier factor scaling, DAP-first nitrogen mass balance crediting |
