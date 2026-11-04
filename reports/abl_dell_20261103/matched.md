# Matched runtime (draft v5)

Budgets (mean single-core ms of 6p at default settings): sift 186.06, splg 34.37

| Method | SIFT, w < 0.4 | SP+LG | RANSAC seeds (SIFT) |
|---|---|---|---|
| 6pt+P3P | 34.41 | 63.38 | [0, 1, 2] |
| Sequential, six points then P3P | 41.05 | 48.57 | [0, 1, 2] |
| 5pt+P3P+R+F at guessed f | 18.71 | 27.96 | [0] |
| 5pt+P3P+R+F at GeoCalib f | 45.94 | 64.38 | [0] |
| 4p3vf(M) | 25.02 | 45.40 | [0] |
| 4p3vf(M)+R | 24.96 | 47.29 | [0] |
| 4p3vf(M) with refit | 25.12 | 44.01 | [0, 1, 2] |
| 4p3vf(M±δ) with refit | 20.97 | 42.37 | [0] |
| 4p3vf(O), oracle | 51.49 | 68.31 | [0] |
| 6pt+P3P, PROSAC | 53.31 | - | [0] |
| Sequential, PROSAC | 47.03 | - | [0] |
| 4p3vf(M) with refit, PROSAC | 44.01 | - | [0] |
| 5pt+P3P+R+F at f from F (views 1-2) | 23.88 | - | [0] |

Primary test with labels at the second threshold (w < 0.4 at 4 px):
- vs 6pt+P3P: -9.31 AUC@10, 95% CI [-14.80, -4.01], one-sided p = 1, 13304 triplets
- vs Sequential, six points then P3P: -16.38 AUC@10, 95% CI [-21.62, -10.94], one-sided p = 1, 13304 triplets
- intersection-union p = 1

Budget x 0.25: 6pt+P3P 24.97, Sequential, six points then P3P 36.45, 5pt+P3P+R+F at guessed f 13.62, 5pt+P3P+R+F at GeoCalib f 35.15, 4p3vf(M) 15.12, 4p3vf(M)+R 14.81, 4p3vf(M) with refit 15.23, 4p3vf(M±δ) with refit 10.91, 4p3vf(O), oracle 39.90, 6pt+P3P, PROSAC 52.69, Sequential, PROSAC 46.85, 4p3vf(M) with refit, PROSAC 38.44, 5pt+P3P+R+F at f from F (views 1-2) 17.54
- primary vs 6pt+P3P: -9.74 AUC@10, 95% CI [-14.87, -5.30], one-sided p = 1, 13744 triplets
- primary vs Sequential, six points then P3P: -21.22 AUC@10, 95% CI [-26.73, -16.05], one-sided p = 1, 13744 triplets
- intersection-union p = 1

Budget x 4.0: 6pt+P3P 43.31, Sequential, six points then P3P 44.72, 5pt+P3P+R+F at guessed f 20.39, 5pt+P3P+R+F at GeoCalib f 51.38, 4p3vf(M) 35.02, 4p3vf(M)+R 33.98, 4p3vf(M) with refit 34.60, 4p3vf(M±δ) with refit 32.10, 4p3vf(O), oracle 59.71, 6pt+P3P, PROSAC 54.81, Sequential, PROSAC 47.11, 4p3vf(M) with refit, PROSAC 47.37, 5pt+P3P+R+F at f from F (views 1-2) 26.53
- primary vs 6pt+P3P: -8.70 AUC@10, 95% CI [-13.33, -4.05], one-sided p = 1, 13744 triplets
- primary vs Sequential, six points then P3P: -10.12 AUC@10, 95% CI [-15.17, -5.05], one-sided p = 1, 13744 triplets
- intersection-union p = 1

PROSAC minus uniform sampling, same method (SIFT, w < 0.4):
- 6pt+P3P: 18.90 AUC@10, 95% CI [14.07, 24.36], one-sided p = 0.0004998, 13744 triplets
- Sequential, six points then P3P: 5.98 AUC@10, 95% CI [3.02, 9.24], one-sided p = 0.0004998, 13744 triplets
- 4p3vf(M) with refit: 18.89 AUC@10, 95% CI [14.44, 23.96], one-sided p = 0.0004998, 13744 triplets

Primary test, 4p3vf(M) with refit minus each baseline on the guarded SIFT triplets with w < 0.4:
- vs 6pt+P3P: -9.29 AUC@10, 95% CI [-14.76, -3.88] (scene-stratified [-10.81, -7.92]), one-sided p = 0.9999, 13744 triplets in 16 scenes
- vs Sequential, six points then P3P: -15.93 AUC@10, 95% CI [-21.40, -10.70] (scene-stratified [-18.26, -13.78]), one-sided p = 1, 13744 triplets in 16 scenes
- intersection-union p = 1: not shown superior at 0.05

Real triplets by inlier ratio (Fig. 2a):

| w | triplets | SP+LG share | 6pt+P3P | Sequential, six points then P3P | 5pt+P3P+R+F at guessed f | 5pt+P3P+R+F at GeoCalib f | 4p3vf(M) | 4p3vf(M)+R | 4p3vf(M) with refit | 4p3vf(M±δ) with refit | 4p3vf(O), oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0-0.1 | 3958 | 0.03 | 2.51 | 10.82 | 1.63 | 3.29 | 1.59 | 1.85 | 1.70 | 0.87 | 6.72 |
| 0.1-0.2 | 4930 | 0.00 | 20.25 | 34.49 | 13.60 | 35.00 | 16.19 | 15.43 | 13.00 | 9.74 | 45.59 |
| 0.2-0.3 | 3144 | 0.00 | 54.27 | 55.69 | 24.95 | 70.69 | 35.65 | 36.14 | 38.74 | 34.36 | 76.17 |
| 0.3-0.4 | 1883 | 0.02 | 73.12 | 65.69 | 40.09 | 76.81 | 54.80 | 56.81 | 60.06 | 52.96 | 78.19 |
| 0.4-0.5 | 1104 | 0.04 | 77.69 | 68.66 | 44.65 | 77.89 | 68.66 | 68.11 | 72.23 | 68.60 | 79.29 |
| 0.5-0.6 | 652 | 0.12 | 68.45 | 61.35 | 47.54 | 69.81 | 63.82 | 65.71 | 66.15 | 65.58 | 69.50 |
| 0.6-0.7 | 437 | 0.44 | 60.83 | 53.49 | 44.56 | 61.53 | 55.50 | 54.83 | 57.49 | 56.93 | 68.93 |
| 0.7-0.8 | 664 | 0.85 | 65.27 | 58.50 | 48.89 | 63.11 | 56.45 | 56.65 | 55.23 | 54.35 | 69.53 |
| 0.8-0.9 | 1462 | 0.99 | 47.68 | 34.80 | 26.19 | 52.55 | 32.30 | 32.91 | 32.97 | 33.14 | 54.35 |
| 0.9-1.0 | 5538 | 1.00 | 66.69 | 52.39 | 29.27 | 67.39 | 48.71 | 50.80 | 47.32 | 45.59 | 70.84 |
- crossover vs 6pt+P3P: measured -, bootstrap {'share_with_crossing': 0.1755, 'ci95': [0.0677272004303115, 0.7295798440732384]}, predicted {'text': 'w = 0.399 (refit faster below)', 'w': [0.399]}
- crossover vs Sequential, six points then P3P: measured 0.705, bootstrap {'share_with_crossing': 0.9995, 'ci95': [0.6304045856731757, 0.949710220951031]}, predicted {'text': 'none: refit slower everywhere (ratio 23.06-4844.62)', 'w': []}

Semi-synthetic, whole-track outliers (Fig. 2):
- w = 0.25: 6pt+P3P 37.59, Sequential, six points then P3P 34.01, 5pt+P3P+R+F at guessed f 54.40, 5pt+P3P+R+F at GeoCalib f 59.42, 4p3vf(M) 41.81, 4p3vf(M)+R 42.88, 4p3vf(M) with refit 43.58, 4p3vf(M±δ) with refit 34.14, 4p3vf(O), oracle 57.50
- w = 0.35: 6pt+P3P 55.43, Sequential, six points then P3P 44.93, 5pt+P3P+R+F at guessed f 58.25, 5pt+P3P+R+F at GeoCalib f 63.55, 4p3vf(M) 52.31, 4p3vf(M)+R 53.42, 4p3vf(M) with refit 56.35, 4p3vf(M±δ) with refit 49.41, 4p3vf(O), oracle 62.28
- w = 0.5: 6pt+P3P 60.34, Sequential, six points then P3P 50.03, 5pt+P3P+R+F at guessed f 58.78, 5pt+P3P+R+F at GeoCalib f 63.98, 4p3vf(M) 55.61, 4p3vf(M)+R 55.99, 4p3vf(M) with refit 58.60, 4p3vf(M±δ) with refit 55.15, 4p3vf(O), oracle 62.42
- w = 0.75: 6pt+P3P 58.79, Sequential, six points then P3P 51.83, 5pt+P3P+R+F at guessed f 57.55, 5pt+P3P+R+F at GeoCalib f 63.07, 4p3vf(M) 49.04, 4p3vf(M)+R 50.48, 4p3vf(M) with refit 51.36, 4p3vf(M±δ) with refit 47.31, 4p3vf(O), oracle 60.94
- crossover vs_6p: gains {'0.25': 5.995561022170888, '0.35': 0.9141926072477744, '0.5': -1.7382079701626918, '0.75': -7.438207674003565}, measured 0.402, bootstrap {'share_with_crossing': 1.0, 'ci95': [0.3363860205910038, 0.5001938972501405]}, predicted {'text': 'w = 0.572 (refit faster below)', 'w': [0.572]}
- crossover vs_seq: gains {'0.25': 9.573145560624116, '0.35': 11.414622575217374, '0.5': 8.57204834911597, '0.75': -0.47372297181534057}, measured 0.737, bootstrap {'share_with_crossing': 0.654, 'ci95': [0.6792943866186936, 0.7484106722880064]}, predicted {'text': 'w = 0.173 (refit faster below)', 'w': [0.173]}

Semi-synthetic, view-3 outliers (Fig. 2):
- w = 0.25: 6pt+P3P 62.66, Sequential, six points then P3P 64.48, 5pt+P3P+R+F at guessed f 52.64, 5pt+P3P+R+F at GeoCalib f 60.43, 4p3vf(M) 46.24, 4p3vf(M)+R 44.28, 4p3vf(M) with refit 42.58, 4p3vf(M±δ) with refit 39.37, 4p3vf(O), oracle 60.05
- w = 0.35: 6pt+P3P 64.80, Sequential, six points then P3P 64.32, 5pt+P3P+R+F at guessed f 58.07, 5pt+P3P+R+F at GeoCalib f 63.27, 4p3vf(M) 56.94, 4p3vf(M)+R 55.83, 4p3vf(M) with refit 58.22, 4p3vf(M±δ) with refit 55.72, 4p3vf(O), oracle 63.84
- w = 0.5: 6pt+P3P 64.89, Sequential, six points then P3P 63.55, 5pt+P3P+R+F at guessed f 58.98, 5pt+P3P+R+F at GeoCalib f 64.26, 4p3vf(M) 58.92, 4p3vf(M)+R 58.42, 4p3vf(M) with refit 59.85, 4p3vf(M±δ) with refit 59.19, 4p3vf(O), oracle 64.30
- w = 0.75: 6pt+P3P 62.44, Sequential, six points then P3P 62.22, 5pt+P3P+R+F at guessed f 59.19, 5pt+P3P+R+F at GeoCalib f 63.82, 4p3vf(M) 52.78, 4p3vf(M)+R 51.72, 4p3vf(M) with refit 51.74, 4p3vf(M±δ) with refit 50.72, 4p3vf(O), oracle 62.79
- crossover vs_6p: gains {'0.25': -20.07601797067052, '0.35': -6.580171724125567, '0.5': -5.038275242014214, '0.75': -10.702380093988866}, measured -, bootstrap {'share_with_crossing': 0.0, 'ci95': None}, predicted {'text': 'none: refit slower everywhere (ratio 3.06-3.06)', 'w': []}
- crossover vs_seq: gains {'0.25': -21.903901693186263, '0.35': -6.097333659138591, '0.5': -3.6957299709714078, '0.75': -10.474198123933675}, measured -, bootstrap {'share_with_crossing': 0.0, 'ci95': None}, predicted {'text': 'none: refit slower everywhere (ratio 23.06-75.20)', 'w': []}

Semi-synthetic, single-view outliers (Fig. 2):
- w = 0.25: 6pt+P3P 57.69, Sequential, six points then P3P 62.96, 5pt+P3P+R+F at guessed f 55.60, 5pt+P3P+R+F at GeoCalib f 62.39, 4p3vf(M) 47.05, 4p3vf(M)+R 45.28, 4p3vf(M) with refit 47.57, 4p3vf(M±δ) with refit 40.76, 4p3vf(O), oracle 61.97
- w = 0.35: 6pt+P3P 63.20, Sequential, six points then P3P 62.25, 5pt+P3P+R+F at guessed f 58.56, 5pt+P3P+R+F at GeoCalib f 63.50, 4p3vf(M) 55.92, 4p3vf(M)+R 55.07, 4p3vf(M) with refit 58.55, 4p3vf(M±δ) with refit 55.14, 4p3vf(O), oracle 64.18
- w = 0.5: 6pt+P3P 63.31, Sequential, six points then P3P 61.36, 5pt+P3P+R+F at guessed f 58.77, 5pt+P3P+R+F at GeoCalib f 63.93, 4p3vf(M) 56.21, 4p3vf(M)+R 56.22, 4p3vf(M) with refit 60.02, 4p3vf(M±δ) with refit 56.97, 4p3vf(O), oracle 64.56
- w = 0.75: 6pt+P3P 60.63, Sequential, six points then P3P 58.84, 5pt+P3P+R+F at guessed f 58.21, 5pt+P3P+R+F at GeoCalib f 62.94, 4p3vf(M) 49.19, 4p3vf(M)+R 48.98, 4p3vf(M) with refit 49.26, 4p3vf(M±δ) with refit 46.59, 4p3vf(O), oracle 62.57
- crossover vs_6p: gains {'0.25': -10.121408816637803, '0.35': -4.64682692162566, '0.5': -3.2882678056190398, '0.75': -11.36763763952415}, measured -, bootstrap {'share_with_crossing': 0.0, 'ci95': None}, predicted {'text': 'w = 0.358 (refit faster below)', 'w': [0.358]}
- crossover vs_seq: gains {'0.25': -15.393608204422065, '0.35': -3.6971692596139043, '0.5': -1.3406755770944156, '0.75': -9.58236787388191}, measured -, bootstrap {'share_with_crossing': 0.143, 'ci95': [0.5004510156760873, 0.5457027253718632]}, predicted {'text': 'none: refit slower everywhere (ratio 23.06-4165.07)', 'w': []}

Semi-synthetic, measured mixture outliers (Fig. 2):
- w = 0.25: 6pt+P3P 56.97, Sequential, six points then P3P 62.67, 5pt+P3P+R+F at guessed f 56.16, 5pt+P3P+R+F at GeoCalib f 61.94, 4p3vf(M) 47.73, 4p3vf(M)+R 45.99, 4p3vf(M) with refit 48.66, 4p3vf(M±δ) with refit 38.69, 4p3vf(O), oracle 61.78
- w = 0.35: 6pt+P3P 62.48, Sequential, six points then P3P 61.99, 5pt+P3P+R+F at guessed f 59.04, 5pt+P3P+R+F at GeoCalib f 63.97, 4p3vf(M) 54.69, 4p3vf(M)+R 55.31, 4p3vf(M) with refit 59.23, 4p3vf(M±δ) with refit 54.71, 4p3vf(O), oracle 64.04
- w = 0.5: 6pt+P3P 63.32, Sequential, six points then P3P 61.62, 5pt+P3P+R+F at guessed f 59.25, 5pt+P3P+R+F at GeoCalib f 63.92, 4p3vf(M) 57.70, 4p3vf(M)+R 57.41, 4p3vf(M) with refit 59.94, 4p3vf(M±δ) with refit 56.91, 4p3vf(O), oracle 64.19
- w = 0.75: 6pt+P3P 60.75, Sequential, six points then P3P 58.61, 5pt+P3P+R+F at guessed f 57.92, 5pt+P3P+R+F at GeoCalib f 63.40, 4p3vf(M) 51.16, 4p3vf(M)+R 51.47, 4p3vf(M) with refit 50.71, 4p3vf(M±δ) with refit 47.86, 4p3vf(O), oracle 62.32
- crossover vs_6p: gains {'0.25': -8.30241952492383, '0.35': -3.241798048934969, '0.5': -3.374056402246549, '0.75': -10.036273189482081}, measured -, bootstrap {'share_with_crossing': 0.001, 'ci95': [0.35272184177416616, 0.3541284729524942]}, predicted {'text': 'w = 0.399 (refit faster below)', 'w': [0.399]}
- crossover vs_seq: gains {'0.25': -14.004822266175182, '0.35': -2.758343899231485, '0.5': -1.6798733341280119, '0.75': -7.898951613099634}, measured -, bootstrap {'share_with_crossing': 0.07, 'ci95': [0.5005737859579412, 0.5450472828825621]}, predicted {'text': 'none: refit slower everywhere (ratio 23.06-4844.62)', 'w': []}

Calibrated, sift_low (budget 43.94 ms): 5pt+P3P 43.68, Sequential, 5pt then P3P 64.47, 4p3v(M)+ENM 36.29, 4p3v(A)+R+F+ENM 32.49, 4p3v(M±δ)+R+F+ENM 25.64, 4p3v(HC) 29.55
Calibrated, whole_0.25 (budget 27.96 ms): 5pt+P3P 51.66, Sequential, 5pt then P3P 60.68, 4p3v(M)+ENM 43.76, 4p3v(A)+R+F+ENM 32.58, 4p3v(M±δ)+R+F+ENM 27.93, 4p3v(HC) 19.00
