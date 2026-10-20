# Research brief: learned solvers for calibrated relative pose (CVPR target)

*Prepared 2026-10-14, updated 2026-10-15 with a tested prototype. For choosing the research question.*

## The problem in one paragraph
Given matched points across 2 or 3 photos with known camera intrinsics, recover how the cameras moved (rotation + translation direction). RANSAC repeatedly picks a tiny random sample of matches, solves the geometry from it with a *minimal solver*, and keeps the answer most matches agree with. Two views need 5 points (the classic 5-point solver). Three views from 4 points (**4p3v**) is a notoriously hard polynomial problem (272 complex solutions), so practical methods approximate it. The project pitch is to make this faster or more reliable by combining the geometry with learning.

## The three seed papers

### Hruby et al., CVPR 2022: *Learning to Solve Hard Minimal Problems* (arXiv 2112.03424)
- **Idea:** do not compute all 272 solutions. Learn (MLP, 6x100) which precomputed "anchor" problem to start from, then track one real homotopy-continuation (HC) path to the answer ("pick & solve").
- **Numbers:** 4p3v solved in 16.3 µs per attempt, but only **26.3 %** of attempts succeed (61.6 µs per correct solution). For 5pt: 29 % success. Trained and tested on ETH3D (noise-free re-projections); the RANSAC experiment is 5pt only, on the CVPR 2020 tutorial data.
- **Weak spots:** low success rate; never evaluated 4p3v inside a full RANSAC on real noisy data; the classifier is tied to the training scene distribution; the released `sample_data.py` crashes (undefined variables).

### Tzamos et al., CVPR 2025: *Practical solutions to the relative pose of three calibrated cameras* (arXiv 2303.16078)
- **Idea:** turn 4p3v into 5pt + P3P by inventing a 5th match: the **mean point** of three of the four points in views 1 and 2 (exact under an affine camera, approximately right otherwise). Add-ons: ±δ variants (3 calls), early non-minimal refit (ENM), LM refinement on the 4 points (+R), filtering with the 4th point (+F).
- **Numbers** (PoseLib, 5 px, 12 PhotoTourism scenes, AUC@10): 4p3v(HC) [Hruby] 73.53 · 5pt+P3P 74.30 · 5pt+P3P+R+F+ENM 76.20 · **4p3v(M±δ)+R+F+ENM 77.14** (112.6 ms vs 33.8 ms for 5pt+P3P).
- **Read-through:** the best method gains about 2.8 AUC@10 over the plain baseline at 3.3x the runtime, and the baseline with the same add-ons gets within 1 point. The headroom for accuracy is small; speed at equal accuracy is the more credible axis.
- **Unpublished finding (from their code):** their PoseLib fork contains `4p3v(L)`, `(L-D)` and `(L-ID)` variants that replace the mean point with a **network-predicted 5th point** (`res/epoch28_sampson.pt`, shipped in `kocurvik/threeview`). It is not in the paper; their table script lists it only in commented-out "rebuttal" rows. So either it did not help enough, or it is their next paper. **That is the obvious "add learning to Tzamos" idea, and it is already taken or tested.**

### Barath, 2025: *SupeRANSAC* (arXiv 2506.04803)
- **Idea:** pipeline details (solver choice, degeneracy checks, local optimization, final IRLS) matter more than any single new component; a carefully built unified pipeline wins across tasks.
- **Numbers:** essential matrix with SuperPoint+LightGlue over 6 datasets: SupeRANSAC AUC@10 0.66 vs PoseLib 0.59 vs OpenCV MAGSAC++ 0.55.
- **Read-through:** any new solver should be judged inside a strong pipeline, or the gain may just be missing "bells and whistles".

## Where we are (all numbers from our own runs, 2026-10-14)
| Experiment | Our result | Paper |
|---|---|---|
| 2-view, RANSAC tutorial val (9,900 pairs), PoseLib 5pt, ratio 0.8 | mAA@10 0.767 | not reported in this form |
| 2-view, RANSAC tutorial test (9 scenes with public GT, 42,301 pairs) | mAA@10 0.709 | — |
| 3-view, Tzamos triplets, PhotoTourism 12 scenes, Python 5pt -> P3P | AUC@5/10/20 59.2 / 70.8 / 79.6 | 5pt+P3P 62.9 / 74.3 / 83.0 |
| 3-view, Aachen v1.1 | 39.5 / 55.6 / 68.7 | 43.4 / 56.7 / 68.3 |
| ETH3D pairs sharing >= 500 GT points | 1,969 pairs | SupeRANSAC: 1,969 |
| Hruby 4p3v data sampler (Python port) | rigidity / normalization exact to 1e-13 | — |

The 3-view gap on PhotoTourism (~3.5 AUC) is expected: our Python baseline runs two separate RANSACs, while theirs scores all three views jointly and refines jointly. Their fork (bundled, builds on the cluster) is needed for an exact reproduction.

## Prototype: learned sample triage, tested (2026-10-15)
**Question.** In three-view RANSAC (5pt+P3P), can a cheap classifier look at a minimal sample *before solving* and predict whether it will lead to a good pose, so RANSAC can draw better samples first?

**Setup.** Tzamos et al.'s released PhotoTourism triplets (real SuperPoint+LightGlue tracks, ground-truth poses). 40 random 5-track samples per triplet; trained on 6 scenes, tested on 6 other scenes (~230k samples each side). Features use only what RANSAC sees before solving (positions, LightGlue scores, spread, near-collinearity). A sample is "good" if its pose error is under 5°, measured three ways. Metric: mean number of draws until the first good sample (lower is better).

| What counts as "good" | Random | Match confidence | Min-distance rule | Learned |
|---|---|---|---|---|
| Raw solver output (any candidate) | 10.05 | 11.01 | 5.77 | **5.50** |
| Raw, best-scoring candidate | 10.20 | 11.22 | 5.80 | **5.52** |
| **After refinement (what matters)** | 3.87 | 4.37 | **2.90** | **2.88** |

**Findings.**
1. **Outliers are not the bottleneck.** About 98% of samples contain no outlier, yet only 4–20% give a good raw pose. Failures come from poorly conditioned samples (points too close together), so ranking by match confidence is no better than random.
2. **Refinement is the great equaliser.** After the standard local refinement, 27–52% of samples end up good, and every ranking needs only about 3–4 draws.
3. **Learning does not beat a one-line rule where it counts.** After refinement, the learned ranker (2.88 draws) ties "prefer well-spread samples" (2.90), although it ranks better overall (AUC 0.67 vs 0.62). The real but modest effect, about 1.3x fewer draws than random, is a sampling heuristic, not a learning contribution.

**Conclusion.** Learned *pre-solve* sample triage (the earlier direction A) is not a strong CVPR contribution on its own. The data points at refinement and scoring, where Tzamos's runtime goes (34–112 ms per triplet), as the place where learning could pay off.

## Candidate research directions (revised, ranked for a ~1-month deadline)

**1. Learned hypothesis triage before refinement (recommended to test next).** After solving and before the expensive refinement and scoring, predict which hypotheses are worth refining, or which refined result will win, from cheap signals (partial inlier counts, solution geometry, sample features). Skip refinement on the rest.
- *Why:* refinement turns 4–20% good raw samples into 27–52% good final poses, and it dominates runtime, so this is where both speed and accuracy live. Labels come free from the same pipeline.
- *Risk:* untested. The gain depends on how much of RANSAC's time is refinement in their fork, and that needs the timing breakdown on the cluster.

**2. Measure, then extend Tzamos's unpublished learned 5th point.** Their weights ship with the code, so week 1 can say whether `(L)` beats the mean point. If it does, extend it (predict several candidate 5th points instead of their fixed three).
- *Risk:* high overlap with that group's own work; they may publish first.

**3. Conditioning-aware sampling as a short analysis contribution.** Write up finding 1 (outliers are not the bottleneck; geometry is) with a simple spread-aware sampler. Solid and cheap, but probably a workshop paper, not a main-track contribution.

**4. Make Hruby's HC solver competitive.** Tzamos shows HC losing to 5pt+P3P (73.5 vs 74.3 AUC@10). Research-heavy; a month is too little.

**5. Three-view in a SupeRANSAC-grade pipeline.** Likely gains, but mostly engineering, so a weak fit for the "geometry + learning" pitch.

## Proposed plan
1. **Days 1–2 (CPU, no cluster needed):** prototype direction 1 with the existing data. Label each hypothesis by whether refining it yields the final good pose, train a cheap predictor, and count refinements saved at equal accuracy. Go or no-go.
2. **Week 1 (cluster):** build the threeview PoseLib fork; reproduce Tzamos Table 3 and measure their unpublished `(L)` variant; get the RANSAC timing breakdown.
3. **Weeks 2–3:** implement the chosen direction inside the fork; evaluate on PhotoTourism, Aachen and Cambridge (now downloaded) at matched runtime; ablations.
4. **Week 4:** write-up.

## Decisions needed (Dr. Aryal)
1. Direction 1, 2 or another, given the negative prototype result for pre-solve triage and the overlap risk in 2.
2. The exact CVPR 2027 deadline.
3. Cluster access: is `g++` available, and can an admin install Boost/OpenCV dev packages? Without a compiler, none of the seed code builds, including Tzamos's fork that every exact reproduction depends on.
