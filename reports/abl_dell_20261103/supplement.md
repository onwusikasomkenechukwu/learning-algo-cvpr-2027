# Supplement tables (draft v5)

## Table 1 per scene (default settings, mean over RANSAC seeds)

| Method | Scene | AUC@5 | AUC@10 | AUC@20 | pair (2,3) AUC@10 | median xi_f | focal mAA |
|---|---|---|---|---|---|---|---|
| 6pt+P3P | GreatCourt | 20.63 | 38.04 | 54.59 | 41.25 | 9.6% | 29.94 |
| 6pt+P3P | KingsCollege | 46.27 | 64.62 | 77.91 | 64.19 | 7.0% | 38.95 |
| 6pt+P3P | OldHospital | 30.20 | 47.92 | 63.41 | 49.60 | 7.2% | 38.79 |
| 6pt+P3P | ShopFacade | 46.81 | 65.08 | 77.81 | 64.28 | 6.7% | 39.72 |
| 6pt+P3P | StMarysChurch | 39.58 | 58.40 | 72.68 | 57.97 | 7.2% | 38.02 |
| 6pt+P3P | delivery_area | 54.46 | 68.19 | 79.16 | 64.67 | 4.0% | 52.85 |
| 6pt+P3P | electro | 70.06 | 79.71 | 86.27 | 76.78 | 1.2% | 77.84 |
| 6pt+P3P | kicker | 58.53 | 73.38 | 84.22 | 70.69 | 2.5% | 64.79 |
| 6pt+P3P | meadow | 41.25 | 59.79 | 72.08 | 63.33 | 5.5% | 43.75 |
| 6pt+P3P | office | 53.36 | 64.08 | 72.41 | 58.66 | 1.7% | 68.53 |
| 6pt+P3P | pipes | 75.85 | 85.63 | 91.63 | 86.37 | 0.9% | 76.67 |
| 6pt+P3P | playground | 25.21 | 35.99 | 48.10 | 36.92 | 10.3% | 34.41 |
| 6pt+P3P | relief | 82.00 | 89.00 | 93.27 | 89.34 | 1.9% | 73.53 |
| 6pt+P3P | relief_2 | 75.19 | 82.11 | 86.66 | 83.97 | 1.7% | 69.83 |
| 6pt+P3P | terrace | 80.39 | 87.13 | 92.17 | 83.49 | 0.7% | 90.16 |
| 6pt+P3P | terrains | 51.36 | 64.67 | 75.75 | 65.98 | 32.5% | 11.62 |
| Sequential, six points then P3P | GreatCourt | 15.86 | 30.19 | 45.32 | 30.88 | 13.2% | 24.14 |
| Sequential, six points then P3P | KingsCollege | 39.92 | 56.72 | 69.70 | 56.15 | 8.5% | 33.82 |
| Sequential, six points then P3P | OldHospital | 25.18 | 41.21 | 55.64 | 41.16 | 9.4% | 32.13 |
| Sequential, six points then P3P | ShopFacade | 38.03 | 55.24 | 68.71 | 54.18 | 8.9% | 32.29 |
| Sequential, six points then P3P | StMarysChurch | 33.37 | 50.66 | 64.68 | 49.56 | 8.9% | 32.37 |
| Sequential, six points then P3P | delivery_area | 35.01 | 46.57 | 58.28 | 40.41 | 11.3% | 36.20 |
| Sequential, six points then P3P | electro | 46.96 | 57.55 | 66.78 | 53.83 | 3.3% | 56.86 |
| Sequential, six points then P3P | kicker | 33.04 | 45.53 | 58.27 | 42.03 | 8.1% | 38.71 |
| Sequential, six points then P3P | meadow | 27.08 | 38.12 | 47.29 | 33.33 | 17.8% | 24.17 |
| Sequential, six points then P3P | office | 34.68 | 43.46 | 52.10 | 37.11 | 6.4% | 45.26 |
| Sequential, six points then P3P | pipes | 45.48 | 53.93 | 61.19 | 49.56 | 6.1% | 46.22 |
| Sequential, six points then P3P | playground | 13.28 | 20.10 | 29.29 | 16.84 | 23.9% | 18.50 |
| Sequential, six points then P3P | relief | 41.92 | 55.30 | 67.68 | 57.51 | 9.8% | 33.46 |
| Sequential, six points then P3P | relief_2 | 42.18 | 53.40 | 64.18 | 52.19 | 11.5% | 34.22 |
| Sequential, six points then P3P | terrace | 64.57 | 72.05 | 80.06 | 66.67 | 1.1% | 79.92 |
| Sequential, six points then P3P | terrains | 33.03 | 46.10 | 58.30 | 46.28 | 59.3% | 5.46 |
| 5pt+P3P+R+F at guessed f | GreatCourt | 19.78 | 36.98 | 54.44 | 40.85 | 9.4% | 31.23 |
| 5pt+P3P+R+F at guessed f | KingsCollege | 45.58 | 63.49 | 76.79 | 63.71 | 7.0% | 39.27 |
| 5pt+P3P+R+F at guessed f | OldHospital | 26.94 | 43.59 | 59.00 | 45.53 | 8.1% | 35.52 |
| 5pt+P3P+R+F at guessed f | ShopFacade | 43.36 | 60.87 | 73.65 | 60.54 | 7.2% | 38.12 |
| 5pt+P3P+R+F at guessed f | StMarysChurch | 38.80 | 57.37 | 71.49 | 57.37 | 7.0% | 38.92 |
| 5pt+P3P+R+F at guessed f | delivery_area | 7.56 | 13.90 | 22.42 | 15.68 | 87.4% | 1.16 |
| 5pt+P3P+R+F at guessed f | electro | 3.08 | 7.20 | 15.99 | 11.27 | 101.0% | 1.27 |
| 5pt+P3P+R+F at guessed f | kicker | 4.51 | 10.96 | 23.41 | 12.77 | 71.6% | 1.82 |
| 5pt+P3P+R+F at guessed f | meadow | 8.33 | 20.42 | 34.27 | 22.92 | 59.2% | 1.88 |
| 5pt+P3P+R+F at guessed f | office | 0.45 | 2.17 | 8.73 | 4.85 | 112.7% | 0.59 |
| 5pt+P3P+R+F at guessed f | pipes | 7.85 | 17.78 | 33.89 | 23.04 | 66.3% | 1.04 |
| 5pt+P3P+R+F at guessed f | playground | 1.05 | 3.71 | 10.29 | 2.88 | 115.9% | 0.63 |
| 5pt+P3P+R+F at guessed f | relief | 23.49 | 36.50 | 51.98 | 45.47 | 28.9% | 11.06 |
| 5pt+P3P+R+F at guessed f | relief_2 | 16.91 | 25.47 | 36.75 | 30.73 | 55.4% | 6.98 |
| 5pt+P3P+R+F at guessed f | terrace | 1.01 | 4.84 | 14.55 | 4.73 | 63.9% | 2.13 |
| 5pt+P3P+R+F at guessed f | terrains | 45.83 | 62.59 | 77.11 | 63.41 | 55.9% | 6.91 |
| 5pt+P3P+R+F at GeoCalib f | GreatCourt | 24.36 | 44.24 | 62.89 | 47.62 | 7.7% | 35.80 |
| 5pt+P3P+R+F at GeoCalib f | KingsCollege | 47.65 | 66.25 | 79.56 | 66.15 | 6.5% | 41.58 |
| 5pt+P3P+R+F at GeoCalib f | OldHospital | 30.51 | 48.88 | 64.86 | 50.70 | 6.6% | 41.85 |
| 5pt+P3P+R+F at GeoCalib f | ShopFacade | 46.22 | 64.82 | 77.92 | 64.33 | 6.7% | 40.18 |
| 5pt+P3P+R+F at GeoCalib f | StMarysChurch | 41.00 | 60.45 | 74.97 | 60.06 | 6.6% | 40.83 |
| 5pt+P3P+R+F at GeoCalib f | delivery_area | 50.54 | 64.12 | 75.94 | 62.65 | 4.6% | 51.50 |
| 5pt+P3P+R+F at GeoCalib f | electro | 60.16 | 74.42 | 83.90 | 73.08 | 2.5% | 70.74 |
| 5pt+P3P+R+F at GeoCalib f | kicker | 55.14 | 69.55 | 80.91 | 66.65 | 2.9% | 62.18 |
| 5pt+P3P+R+F at GeoCalib f | meadow | 43.75 | 64.58 | 78.33 | 70.62 | 7.5% | 41.67 |
| 5pt+P3P+R+F at GeoCalib f | office | 53.38 | 63.40 | 72.09 | 58.59 | 1.9% | 64.13 |
| 5pt+P3P+R+F at GeoCalib f | pipes | 62.52 | 76.37 | 87.15 | 82.44 | 4.0% | 60.00 |
| 5pt+P3P+R+F at GeoCalib f | playground | 16.69 | 26.49 | 37.82 | 26.59 | 11.8% | 31.58 |
| 5pt+P3P+R+F at GeoCalib f | relief | 76.05 | 84.92 | 90.81 | 85.40 | 2.9% | 63.55 |
| 5pt+P3P+R+F at GeoCalib f | relief_2 | 67.04 | 75.12 | 82.00 | 77.65 | 3.2% | 57.97 |
| 5pt+P3P+R+F at GeoCalib f | terrace | 81.01 | 87.56 | 92.60 | 81.24 | 1.1% | 87.91 |
| 5pt+P3P+R+F at GeoCalib f | terrains | 63.83 | 78.24 | 87.72 | 78.35 | 20.4% | 16.40 |
| 4p3vf(M) | GreatCourt | 15.21 | 28.73 | 42.51 | 32.19 | 13.4% | 24.04 |
| 4p3vf(M) | KingsCollege | 42.12 | 59.19 | 71.96 | 59.20 | 7.9% | 36.14 |
| 4p3vf(M) | OldHospital | 27.07 | 42.80 | 57.02 | 44.48 | 8.2% | 35.13 |
| 4p3vf(M) | ShopFacade | 41.42 | 58.44 | 70.92 | 58.14 | 7.8% | 35.91 |
| 4p3vf(M) | StMarysChurch | 34.33 | 50.93 | 64.36 | 50.63 | 8.5% | 33.35 |
| 4p3vf(M) | delivery_area | 41.64 | 54.79 | 66.39 | 51.93 | 6.0% | 44.63 |
| 4p3vf(M) | electro | 40.29 | 54.02 | 66.25 | 54.25 | 3.1% | 57.63 |
| 4p3vf(M) | kicker | 41.12 | 57.09 | 70.95 | 54.31 | 4.5% | 50.56 |
| 4p3vf(M) | meadow | 32.08 | 48.54 | 62.29 | 59.58 | 5.8% | 45.62 |
| 4p3vf(M) | office | 31.73 | 42.96 | 53.04 | 40.48 | 3.6% | 55.35 |
| 4p3vf(M) | pipes | 51.26 | 62.15 | 71.89 | 64.44 | 2.0% | 63.70 |
| 4p3vf(M) | playground | 9.82 | 16.74 | 26.23 | 17.12 | 21.5% | 21.68 |
| 4p3vf(M) | relief | 67.57 | 77.47 | 84.85 | 78.07 | 3.1% | 61.07 |
| 4p3vf(M) | relief_2 | 52.98 | 63.21 | 71.45 | 65.58 | 4.2% | 50.32 |
| 4p3vf(M) | terrace | 47.21 | 53.41 | 61.92 | 53.18 | 1.7% | 73.14 |
| 4p3vf(M) | terrains | 40.12 | 52.86 | 66.04 | 55.95 | 52.6% | 8.33 |
| 4p3vf(M)+R | GreatCourt | 15.67 | 29.73 | 43.90 | 33.47 | 12.9% | 24.60 |
| 4p3vf(M)+R | KingsCollege | 42.81 | 60.01 | 72.91 | 60.07 | 7.8% | 36.52 |
| 4p3vf(M)+R | OldHospital | 27.45 | 43.31 | 57.51 | 45.04 | 8.0% | 35.88 |
| 4p3vf(M)+R | ShopFacade | 42.53 | 59.63 | 71.98 | 59.07 | 7.6% | 36.44 |
| 4p3vf(M)+R | StMarysChurch | 35.26 | 52.05 | 65.45 | 51.79 | 8.3% | 33.76 |
| 4p3vf(M)+R | delivery_area | 44.44 | 57.91 | 69.34 | 54.25 | 5.4% | 46.11 |
| 4p3vf(M)+R | electro | 44.55 | 57.61 | 68.99 | 58.81 | 2.5% | 62.39 |
| 4p3vf(M)+R | kicker | 43.85 | 59.84 | 72.79 | 56.70 | 4.3% | 52.50 |
| 4p3vf(M)+R | meadow | 33.33 | 48.54 | 62.29 | 56.25 | 6.5% | 44.58 |
| 4p3vf(M)+R | office | 35.08 | 45.18 | 54.03 | 42.89 | 3.4% | 57.49 |
| 4p3vf(M)+R | pipes | 55.70 | 66.59 | 75.30 | 67.85 | 1.8% | 63.78 |
| 4p3vf(M)+R | playground | 11.13 | 18.92 | 29.10 | 19.85 | 18.5% | 23.61 |
| 4p3vf(M)+R | relief | 71.79 | 81.05 | 87.48 | 81.54 | 2.8% | 64.43 |
| 4p3vf(M)+R | relief_2 | 57.93 | 67.37 | 74.74 | 69.03 | 3.3% | 55.27 |
| 4p3vf(M)+R | terrace | 48.45 | 54.22 | 63.33 | 54.34 | 1.3% | 75.04 |
| 4p3vf(M)+R | terrains | 44.62 | 57.56 | 69.38 | 59.52 | 47.1% | 9.37 |
| 4p3vf(M) with refit | GreatCourt | 18.69 | 34.87 | 50.63 | 38.35 | 10.7% | 27.70 |
| 4p3vf(M) with refit | KingsCollege | 45.68 | 63.85 | 77.12 | 63.45 | 7.2% | 38.67 |
| 4p3vf(M) with refit | OldHospital | 29.09 | 46.16 | 61.29 | 47.87 | 7.6% | 37.57 |
| 4p3vf(M) with refit | ShopFacade | 45.17 | 63.18 | 75.91 | 62.48 | 7.0% | 38.60 |
| 4p3vf(M) with refit | StMarysChurch | 38.03 | 56.15 | 70.19 | 55.53 | 7.5% | 36.67 |
| 4p3vf(M) with refit | delivery_area | 45.52 | 59.02 | 70.95 | 56.00 | 5.4% | 46.88 |
| 4p3vf(M) with refit | electro | 45.90 | 59.71 | 71.52 | 61.06 | 2.6% | 61.65 |
| 4p3vf(M) with refit | kicker | 45.25 | 61.67 | 74.84 | 58.47 | 4.0% | 53.19 |
| 4p3vf(M) with refit | meadow | 42.50 | 60.00 | 72.50 | 63.96 | 5.7% | 47.29 |
| 4p3vf(M) with refit | office | 36.73 | 47.28 | 57.07 | 44.84 | 3.4% | 57.01 |
| 4p3vf(M) with refit | pipes | 54.52 | 66.67 | 77.81 | 68.44 | 1.7% | 68.44 |
| 4p3vf(M) with refit | playground | 11.58 | 19.72 | 29.86 | 20.85 | 19.2% | 24.11 |
| 4p3vf(M) with refit | relief | 73.49 | 82.37 | 88.10 | 81.85 | 2.5% | 65.95 |
| 4p3vf(M) with refit | relief_2 | 57.47 | 67.94 | 76.12 | 69.49 | 3.5% | 54.13 |
| 4p3vf(M) with refit | terrace | 50.85 | 57.21 | 67.09 | 57.29 | 1.2% | 76.28 |
| 4p3vf(M) with refit | terrains | 44.74 | 58.48 | 71.21 | 60.77 | 45.1% | 9.13 |
| 4p3vf(M±δ) with refit | GreatCourt | 19.27 | 35.90 | 52.05 | 39.34 | 10.5% | 28.27 |
| 4p3vf(M±δ) with refit | KingsCollege | 45.76 | 63.99 | 77.29 | 63.61 | 7.2% | 38.70 |
| 4p3vf(M±δ) with refit | OldHospital | 29.32 | 46.59 | 61.84 | 48.34 | 7.4% | 38.06 |
| 4p3vf(M±δ) with refit | ShopFacade | 45.59 | 63.73 | 76.45 | 62.89 | 6.9% | 38.92 |
| 4p3vf(M±δ) with refit | StMarysChurch | 38.25 | 56.56 | 70.69 | 55.95 | 7.4% | 37.01 |
| 4p3vf(M±δ) with refit | delivery_area | 46.15 | 59.94 | 71.97 | 56.82 | 5.1% | 47.59 |
| 4p3vf(M±δ) with refit | electro | 49.20 | 62.21 | 73.42 | 62.85 | 2.3% | 64.18 |
| 4p3vf(M±δ) with refit | kicker | 46.09 | 63.15 | 76.36 | 59.64 | 3.9% | 54.61 |
| 4p3vf(M±δ) with refit | meadow | 40.83 | 58.12 | 70.62 | 62.92 | 5.9% | 48.12 |
| 4p3vf(M±δ) with refit | office | 37.27 | 47.74 | 57.46 | 45.51 | 3.2% | 57.86 |
| 4p3vf(M±δ) with refit | pipes | 58.81 | 71.04 | 81.81 | 71.26 | 1.6% | 68.00 |
| 4p3vf(M±δ) with refit | playground | 12.93 | 22.16 | 31.99 | 23.06 | 14.2% | 27.04 |
| 4p3vf(M±δ) with refit | relief | 74.03 | 82.97 | 88.79 | 82.45 | 2.5% | 66.55 |
| 4p3vf(M±δ) with refit | relief_2 | 58.89 | 69.00 | 76.94 | 70.78 | 3.2% | 56.00 |
| 4p3vf(M±δ) with refit | terrace | 52.17 | 58.41 | 68.10 | 59.03 | 1.2% | 77.98 |
| 4p3vf(M±δ) with refit | terrains | 45.16 | 58.97 | 71.64 | 61.24 | 44.1% | 9.43 |
| 4p3vf(O), oracle | GreatCourt | 22.18 | 40.14 | 56.74 | 42.69 | 9.1% | 31.06 |
| 4p3vf(O), oracle | KingsCollege | 46.26 | 64.59 | 77.85 | 64.10 | 7.0% | 39.03 |
| 4p3vf(O), oracle | OldHospital | 30.68 | 48.72 | 64.38 | 50.06 | 7.2% | 39.03 |
| 4p3vf(O), oracle | ShopFacade | 46.77 | 65.05 | 77.66 | 64.11 | 6.8% | 39.78 |
| 4p3vf(O), oracle | StMarysChurch | 39.64 | 58.21 | 72.29 | 57.67 | 7.2% | 37.84 |
| 4p3vf(O), oracle | delivery_area | 53.88 | 67.34 | 77.51 | 62.98 | 3.9% | 52.96 |
| 4p3vf(O), oracle | electro | 70.42 | 80.54 | 87.21 | 76.36 | 1.3% | 79.04 |
| 4p3vf(O), oracle | kicker | 58.51 | 73.07 | 84.30 | 69.09 | 2.6% | 64.17 |
| 4p3vf(O), oracle | meadow | 48.75 | 66.46 | 79.79 | 72.50 | 6.1% | 45.21 |
| 4p3vf(O), oracle | office | 57.01 | 68.14 | 76.74 | 62.12 | 1.6% | 70.76 |
| 4p3vf(O), oracle | pipes | 77.48 | 87.70 | 93.85 | 88.07 | 1.2% | 77.78 |
| 4p3vf(O), oracle | playground | 32.88 | 44.81 | 55.93 | 41.60 | 6.5% | 42.81 |
| 4p3vf(O), oracle | relief | 82.92 | 89.78 | 93.97 | 90.34 | 1.8% | 74.61 |
| 4p3vf(O), oracle | relief_2 | 78.10 | 85.48 | 90.04 | 86.35 | 1.6% | 72.85 |
| 4p3vf(O), oracle | terrace | 88.76 | 93.10 | 95.89 | 88.18 | 0.7% | 94.50 |
| 4p3vf(O), oracle | terrains | 50.55 | 63.53 | 74.46 | 64.72 | 33.9% | 10.57 |
| VGGT, then three-view LO | GreatCourt | 27.75 | 48.00 | 66.88 | 50.65 | 7.0% | 39.07 |
| VGGT, then three-view LO | KingsCollege | 46.27 | 66.01 | 80.69 | 65.77 | 6.6% | 40.60 |
| VGGT, then three-view LO | OldHospital | 33.56 | 53.60 | 71.20 | 55.24 | 5.0% | 48.86 |
| VGGT, then three-view LO | ShopFacade | 49.96 | 69.06 | 82.38 | 68.37 | 5.4% | 46.33 |
| VGGT, then three-view LO | StMarysChurch | 44.53 | 63.81 | 78.56 | 62.72 | 5.6% | 45.90 |
| VGGT, then three-view LO | delivery_area | 52.12 | 67.53 | 80.55 | 65.78 | 3.6% | 54.81 |
| VGGT, then three-view LO | electro | 67.60 | 77.88 | 86.49 | 76.39 | 1.3% | 77.93 |
| VGGT, then three-view LO | kicker | 60.84 | 74.08 | 84.62 | 71.15 | 2.0% | 66.54 |
| VGGT, then three-view LO | meadow | 58.75 | 76.25 | 85.62 | 81.25 | 3.0% | 66.88 |
| VGGT, then three-view LO | office | 76.18 | 83.99 | 90.99 | 79.26 | 0.9% | 87.14 |
| VGGT, then three-view LO | pipes | 60.00 | 75.11 | 86.22 | 80.44 | 1.4% | 73.78 |
| VGGT, then three-view LO | playground | 85.11 | 88.57 | 91.47 | 84.81 | 0.8% | 85.71 |
| VGGT, then three-view LO | relief | 31.81 | 54.05 | 72.75 | 49.11 | 10.5% | 27.38 |
| VGGT, then three-view LO | relief_2 | 39.28 | 58.79 | 74.17 | 60.78 | 8.5% | 30.75 |
| VGGT, then three-view LO | terrace | 60.23 | 70.58 | 80.99 | 74.30 | 0.8% | 80.93 |
| VGGT, then three-view LO | terrains | 57.56 | 72.72 | 84.05 | 71.92 | 20.5% | 17.69 |

## Single-core time per triplet at default settings (ms)

| Set | Method | n | mean | median | 90th | 99th |
|---|---|---|---|---|---|---|
| splg_time | 6pt+P3P | 100 | 34.37 | 9.06 | 83.29 | 233.97 |
| splg_time | Sequential, six points then P3P | 100 | 7.30 | 6.31 | 13.51 | 19.76 |
| splg_time | 5pt+P3P+R+F at guessed f | 100 | 61.93 | 15.25 | 199.07 | 344.42 |
| splg_time | 5pt+P3P+R+F at GeoCalib f | 100 | 26.76 | 12.09 | 55.07 | 197.18 |
| splg_time | 4p3vf(M) | 100 | 33.25 | 9.64 | 103.66 | 193.36 |
| splg_time | 4p3vf(M)+R | 100 | 35.71 | 10.06 | 100.42 | 222.01 |
| splg_time | 4p3vf(M) with refit | 100 | 56.37 | 19.55 | 137.57 | 404.61 |
| splg_time | 4p3vf(M±δ) with refit | 100 | 78.58 | 27.05 | 207.00 | 654.12 |
| splg_time | 4p3vf(O), oracle | 100 | 13.84 | 8.19 | 27.80 | 51.61 |
| splg_time | VGGT, then three-view LO | 100 | 1.95 | 1.55 | 4.05 | 8.67 |
| sift_time | 6pt+P3P | 104 | 186.06 | 178.23 | 215.31 | 308.91 |
| sift_time | Sequential, six points then P3P | 104 | 118.92 | 161.37 | 170.08 | 182.47 |
| sift_time | 5pt+P3P+R+F at guessed f | 104 | 108.46 | 94.98 | 172.67 | 258.36 |
| sift_time | 5pt+P3P+R+F at GeoCalib f | 104 | 97.26 | 86.00 | 154.19 | 228.03 |
| sift_time | 4p3vf(M) | 104 | 189.07 | 190.68 | 248.60 | 351.90 |
| sift_time | 4p3vf(M)+R | 104 | 199.80 | 201.59 | 275.67 | 366.71 |
| sift_time | 4p3vf(M) with refit | 104 | 339.38 | 237.87 | 542.66 | 1696.79 |
| sift_time | 4p3vf(M±δ) with refit | 104 | 680.86 | 588.91 | 1045.75 | 2174.89 |
| sift_time | 4p3vf(O), oracle | 104 | 169.40 | 177.98 | 226.44 | 265.53 |
| sift_time | VGGT, then three-view LO | 104 | 2.12 | 1.59 | 4.02 | 8.43 |
| sift_time | 6pt+P3P, PROSAC | 104 | 200.23 | 184.15 | 253.15 | 428.53 |
| sift_time | Sequential, PROSAC | 104 | 119.67 | 161.59 | 173.59 | 183.27 |
| sift_time | 4p3vf(M) with refit, PROSAC | 104 | 486.81 | 293.72 | 922.21 | 2167.43 |
| sift_time | 5pt+P3P+R+F at f from F (views 1-2) | 104 | 102.07 | 89.74 | 161.19 | 234.68 |

## RANSAC threshold (Cambridge SP+LG, AUC@10, seed 0)

| Method | 3.0 px | 5.0 px | 10.0 px |
|---|---|---|---|
| 6pt+P3P | 53.20 | 54.82 | 56.13 |
| Sequential, six points then P3P | 40.89 | 46.77 | 50.97 |
| 4p3vf(M) | 45.50 | 47.98 | 49.64 |
| 4p3vf(M) with refit | 49.37 | 52.94 | 55.12 |
| 4p3vf(M±δ)+R with refit | 50.33 | - | 55.98 |

## Refit ablations (Cambridge SP+LG, AUC@10, mean of RANSAC seeds 0-2)

| Method | default (Cauchy, once, every root) | squared | reselect | newbest |
|---|---|---|---|---|
| 4p3vf(M) with refit | 52.84 | 52.80 | 54.09 | 49.55 |
| 4p3vf(M±δ)+R with refit | 53.67 | 53.66 | 54.85 | 50.80 |

## Choice of view 3: views 2 and 3 swapped minus original order (AUC@10, scene-equal, seed 0)

- splg: 6p 0.17 (8042), seq 3.78 (8042), M -0.30 (8042), Mrefit -0.85 (8042), MDRrefit 0.81 (8042)
- sift_low: 6p 1.54 (13744), seq 5.55 (13744), M -1.57 (13744), Mrefit -3.00 (13744), MDRrefit -1.33 (13744)

## 5pt+P3P+R+F at f from the fundamental matrix (default settings, seed 0): Cambridge 53.76, ETH3D 28.22 AUC@10

## Test B: where the samples go

23184 samples; 7784 without a mean-point seed that passes; of the 15400 seeded: ok 5779, ambiguous 9367, not_real 254.

| Method | strict % (usable correct root) | practical % (all seeded) |
|---|---|---|
| cont | 15.6 | 0.2 |
| cont_off | 16.4 | 0.3 |
| cont_retry | 16.7 | 0.2 |
| lm | 21.6 | 0.4 |
| newton | 5.2 | 0.1 |
| newton_hom | 8.0 | 0.2 |
| refine2 | 0.0 | 0.1 |

The correct root itself meets the practical criterion on 3.3% of the usable samples.

Exclusions (% ambiguous / % no real root) by quartile:
- planarity: [-, 0.012) n 3850: 67.1 / 1.2; [0.012, 0.036) n 3850: 63.0 / 1.9; [0.036, 0.086) n 3850: 59.4 / 1.7; [0.086, -) n 3850: 53.7 / 1.8
- reprojection: [-, 0.781) n 3850: 61.5 / 1.6; [0.781, 0.903) n 3850: 60.5 / 1.5; [0.903, 1.031) n 3850: 62.5 / 1.9; [1.031, -) n 3850: 58.8 / 1.6

Strict success by the free point's path length (px at 800 px):
- 0-25 (n 4056): cont 17.9, cont_off 18.5, cont_retry 19.0, lm 22.1, newton 6.0, newton_hom 9.3, refine2 0.0
- 25-50 (n 846): cont 11.1, cont_off 12.4, cont_retry 11.6, lm 20.4, newton 3.2, newton_hom 5.0, refine2 0.0
- 50-100 (n 475): cont 10.7, cont_off 10.9, cont_retry 11.8, lm 21.1, newton 3.8, newton_hom 5.5, refine2 0.0
- 100-200 (n 293): cont 9.2, cont_off 11.6, cont_retry 11.6, lm 21.8, newton 3.4, newton_hom 5.1, refine2 0.0
- 200-400 (n 83): cont 7.2, cont_off 8.4, cont_retry 7.2, lm 13.3, newton 1.2, newton_hom 1.2, refine2 0.0
- 400-inf (n 26): cont 3.8, cont_off 7.7, cont_retry 3.8, lm 19.2, newton 0.0, newton_hom 0.0, refine2 0.0

## Correct-root tool against a full solve

- KingsCollege500: 500 samples, reference {'ok': 238, 'ambiguous': 255, 'not_real': 7}, tool root in the full solve [0.9831932773109243, 238]
- KingsCollege: 100 samples, reference {'ok': 46, 'ambiguous': 53, 'not_real': 1}, tool root in the full solve [0.9565217391304348, 46]
- random: 100 samples, reference {'ok': 63, 'ambiguous': 36, 'not_real': 1}, tool root in the full solve [1.0, 63]

## Tzamos et al. Table 2 with the fixed fork

```

PhotoTourism: 12/12 scenes
method                       ours AUC@5/10/20     ms      paper AUC@5/10/20        diff @5/10/20
4p(HC)                    65.48  76.27  84.13   29.0    62.41  73.53  81.94   +3.07 +2.74 +2.19
5p3v                      66.20  77.16  85.12   26.4    62.93  74.30  83.00   +3.27 +2.86 +2.12
5p3v + ENM                66.27  77.24  85.18   37.9    63.77  75.03  83.50   +2.50 +2.21 +1.68
4p3v(A)                   26.97  32.98  39.34   10.9    22.91  28.59  35.16   +4.06 +4.39 +4.18
4p3v(A) + ENM             66.18  77.07  84.99   28.5    65.49  76.47  84.53   +0.69 +0.60 +0.46
4p3v(A) + R               29.83  36.25  42.74   13.1    25.86  32.22  39.16   +3.97 +4.03 +3.58
4p3v(A) + R + C           27.60  33.74  40.14    8.9    23.99  29.97  36.64   +3.61 +3.77 +3.50
4p3v(A) + R + C + ENM     66.22  77.13  85.02   26.6    65.62  76.56  84.55   +0.60 +0.57 +0.47
4p3v(M)                   65.81  76.75  84.71   27.5    60.86  72.56  81.73   +4.95 +4.19 +2.98
4p3v(M) + ENM             66.28  77.22  85.16   37.8    63.61  74.96  83.46   +2.67 +2.26 +1.70
4p3v(M) + R               66.01  76.95  84.89   33.9    63.66  74.88  83.37   +2.35 +2.07 +1.52
4p3v(M) + R + C           65.93  76.87  84.80   25.1    63.99  75.14  83.51   +1.94 +1.73 +1.29
4p3v(M) + R + C + ENM     66.29  77.25  85.18   36.1    65.18  76.16  84.28   +1.11 +1.09 +0.90
4p3v(M-D)                 66.12  77.10  85.07   64.7    61.86  73.73  82.78   +4.26 +3.37 +2.29
4p3v(M-D) + ENM           66.40  77.37  85.33   96.9    64.02  75.51  84.01   +2.38 +1.86 +1.32
4p3v(M-D) + R             66.23  77.20  85.14   82.3    65.97  77.00  85.01   +0.26 +0.20 +0.13
4p3v(M-D) + R + C         66.20  77.17  85.11   58.1    65.85  76.87  84.90   +0.35 +0.30 +0.21
4p3v(M-D) + R + C + ENM   66.38  77.36  85.32   91.4    66.12  77.14  85.15   +0.26 +0.22 +0.17
4p3v(A) + R + ENM         66.23  77.14  85.02   34.7         (not in paper)
4p3v(M) + R + ENM         66.29  77.23  85.17   44.6         (not in paper)
4p3v(M-D) + R + ENM       66.38  77.35  85.32  116.0         (not in paper)

Aachen: 1/1 scenes
method                       ours AUC@5/10/20     ms      paper AUC@5/10/20        diff @5/10/20
4p(HC)                    47.64  63.82  75.45   26.2    42.28  55.20  66.55   +5.36 +8.62 +8.90
5p3v                      48.32  64.70  76.52   16.6    43.43  56.73  68.28   +4.89 +7.97 +8.23
5p3v + ENM                48.48  64.75  76.61   23.8    43.32  56.64  68.06   +5.16 +8.11 +8.55
4p3v(A)                   15.45  21.69  27.80   12.0    24.41  31.73  39.24   -8.96 -10.04 -11.44
4p3v(A) + ENM             48.24  64.56  76.34   17.7    43.62  56.99  68.55   +4.62 +7.57 +7.79
4p3v(A) + R               17.76  24.91  31.66   15.8    25.27  32.77  40.29   -7.51 -7.86 -8.63
4p3v(A) + R + C           16.99  23.65  30.15    8.5    23.94  31.23  38.58   -6.95 -7.58 -8.43
4p3v(A) + R + C + ENM     48.26  64.59  76.45   15.8    43.57  56.95  68.56   +4.69 +7.64 +7.89
4p3v(M)                   47.29  63.59  75.59   16.8    41.78  55.06  66.67   +5.51 +8.53 +8.92
4p3v(M) + ENM             48.34  64.65  76.45   23.5    43.31  56.61  68.08   +5.03 +8.04 +8.37
4p3v(M) + R               47.80  64.12  76.01   21.7    43.28  56.39  67.88   +4.52 +7.73 +8.13
4p3v(M) + R + C           47.38  63.78  75.77   14.6    43.04  56.28  67.73   +4.34 +7.50 +8.04
4p3v(M) + R + C + ENM     48.36  64.67  76.50   21.9    43.74  57.21  68.80   +4.62 +7.46 +7.70
4p3v(M-D)                 48.23  64.54  76.50   39.2    42.74  56.11  67.74   +5.49 +8.43 +8.76
4p3v(M-D) + ENM           48.52  64.81  76.59   60.0    43.66  56.99  68.55   +4.86 +7.82 +8.04
4p3v(M-D) + R             48.30  64.62  76.57   53.2    43.93  57.26  68.82   +4.37 +7.36 +7.75
4p3v(M-D) + R + C         48.09  64.40  76.39   33.8    43.79  57.17  68.73   +4.30 +7.23 +7.66
4p3v(M-D) + R + C + ENM   48.57  64.91  76.75   55.0    44.02  57.42  68.97   +4.55 +7.49 +7.78
4p3v(A) + R + ENM         48.35  64.69  76.55   22.5         (not in paper)
4p3v(M) + R + ENM         48.37  64.65  76.45   28.9         (not in paper)
4p3v(M-D) + R + ENM       48.56  64.90  76.72   75.4         (not in paper)
```

