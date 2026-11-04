# Kill test statistics

## Kill test B: continuation vs converged LM (correct root, paired)

| scene | samples | strict n | cont % | LM % | cont - LM (pp) | 95 % CI (Newcombe) | cont only / LM only | McNemar p |
|---|---|---|---|---|---|---|---|---|
| GreatCourt | 4736 | 919 | 11.8 | 15.9 | -4.1 | [-6.1, -2.2] | 21 / 59 | 2.5e-05 |
| KingsCollege | 4790 | 1446 | 17.0 | 24.5 | -7.5 | [-9.4, -5.6] | 47 / 155 | 1.1e-14 |
| OldHospital | 4383 | 959 | 11.9 | 17.8 | -5.9 | [-8.1, -3.8] | 26 / 83 | 4e-08 |
| ShopFacade | 4607 | 1180 | 14.8 | 20.8 | -6.0 | [-8.1, -4.0] | 41 / 112 | 8.3e-09 |
| StMarysChurch | 4668 | 1275 | 20.5 | 26.2 | -5.7 | [-7.7, -3.8] | 45 / 118 | 9.7e-09 |
| POOLED | 23184 | 5779 | 15.6 | 21.6 | -6.0 | [-6.9, -5.1] | 180 / 527 | 2.4e-40 |

- Pooled cont - LM = -6.0 pp; 95 % CI Newcombe [-6.9, -5.1], stratified bootstrap [-6.9, -5.1], two-level bootstrap [-7.2, -4.7] pp.
- LM ahead in 5 of 5 scenes; one-sided exact p that LM is better: 1.2e-40.
- Heterogeneity across scenes: Q = 6.04 (df 4, p = 0.2), I^2 = 34 %.
- The +5 pp target is outside every 95 % interval (decisive).
- Sensitivity, 'practical' success on all 15400 seeded samples: cont - LM = -0.2 pp [-0.3, -0.1], McNemar p = 1.4e-06.
- Continuation against each other method (strict, Holm over all of them): lm -6.0 pp [-6.9, -5.1], p_Holm = 7.3e-40; cont_retry -1.1 pp [-1.4, -0.8], p_Holm = 4.3e-19; newton_hom +7.6 pp [+6.9, +8.4], p_Holm = 3.8e-88; cont_off -0.8 pp [-1.4, -0.2], p_Holm = 0.0059; refine2 +15.6 pp [+14.7, +16.6], p_Holm = 8.9e-272; newton +10.5 pp [+9.6, +11.3], p_Holm = 3.2e-142.

KILL TEST B: cont - LM = -6.0 pp (needs >= +5), McNemar p = 2.4e-40 -> FAIL (target outside the 95 % intervals)

## Kill test A: 6pt+P3P vs the best re-fitted mean-point variant (AUC@10)

5/5 Cambridge scenes, triplets-features_superpoint_800_2048-LG, 3 run(s) (RANSAC seeds 0, 1, 2), triplets per scene GreatCourt 5000, KingsCollege 5000, OldHospital 5000, ShopFacade 5000, StMarysChurch 5000. Rows from crashed tasks (counted as failures): none.

| method | AUC@10 | gap to 6p3v | 95 % CI (stratified) |
|---|---|---|---|
| 6p3v | 54.81 | | |
| 4p3v(M) + ENM | 52.84 | +1.97 | [+1.80, +2.14] |
| 4p3v(M) + R + C + ENM | 52.61 | +2.20 | [+2.03, +2.37] |
| 4p3v(M) + R + ENM | 53.16 | +1.65 | [+1.49, +1.82] |
| 4p3v(M-D) + ENM | 53.36 | +1.45 | [+1.29, +1.62] |
| 4p3v(M-D) + R + C + ENM | 53.14 | +1.67 | [+1.50, +1.84] |
| 4p3v(M-D) + R + ENM | 53.67 | +1.14 | [+0.98, +1.30] |

- Best re-fitted variant: 4p3v(M-D) + R + ENM; gap +1.14 AUC@10.
- 95 % CI with the best re-selected in each replicate: stratified [+0.98, +1.30], two-level [+0.72, +1.54]; keeping 4p3v(M-D) + R + ENM fixed: stratified [+0.98, +1.30], two-level [+0.72, +1.54].
- Share of bootstrap replicates with gap >= 2.0: stratified 0.0 %, two-level 0.0 %.
- Gap per scene: GreatCourt +1.64, KingsCollege +0.43, OldHospital +1.14, ShopFacade +1.22, StMarysChurch +1.25.
- Leaving one scene out: without GreatCourt +1.01, without KingsCollege +1.31, without OldHospital +1.14, without ShopFacade +1.12, without StMarysChurch +1.11.
- Per run: seed 0 +1.07 (4p3v(M-D) + R + ENM), seed 1 +1.19 (4p3v(M-D) + R + ENM), seed 2 +1.15 (4p3v(M-D) + R + ENM).
- Refit effect (re-fitted minus the same variant without the refit, seed 0): 4p3v(M) + ENM +4.96 [+4.67, +5.25], 4p3v(M) + R + C + ENM +5.14 [+4.84, +5.44], 4p3v(M) + R + ENM +4.32 [+4.04, +4.60], 4p3v(M-D) + ENM +4.78 [+4.50, +5.08], 4p3v(M-D) + R + C + ENM +4.79 [+4.50, +5.09], 4p3v(M-D) + R + ENM +4.04 [+3.77, +4.31].

KILL TEST A (3 run(s)): 6p3v - best re-fitted = +1.14 AUC@10 (needs >= +2.0), 95 % CI [+0.98, +1.30] -> FAIL (target outside the 95 % intervals)
