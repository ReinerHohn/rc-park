# Monocular depth and surface-normal models (2024-2026) for facade relief

Context: we want facade relief (oriels ~0.5-1 m, cornices and window reveals 0.1-0.3 m) from street photos, to add to a noisy COLMAP dense cloud. Our cameras are calibrated and bundle-adjusted against LoD2. Hardware is an RTX 4060 with 8 GB VRAM. Commercial sale is planned, so the licence of the weights matters more than the code licence.
Research date: 2026-11-05. A research subagent wrote these notes. Every licence statement comes from the repo README, LICENSE file or HF model card as fetched. Where a README gives no licence for the weights, that is marked as a gap.

## 1. Depth models: licence, accuracy, sharpness, runtime and VRAM

### Takeaway
Models that are commercially usable and have strong geometry are MoGe-2 (MIT, gives normals too), Depth Anything 3 METRIC-LARGE and MONO-LARGE (Apache-2.0), DA3 BASE and SMALL (Apache), Depth Anything V2 Small only (Apache), Prompt Depth Anything (Apache, takes a low-resolution metric depth prompt) and Depth Pro (permissive Apple licence, sharpest boundaries in the MoGe-2 table). Non-commercial (NC) are DA V2 Base, Large and Giant, DA3 Large, Giant and Nested, UniDepth V1 and V2, and VGGT-1B (original weights). VGGT-1B-Commercial exists under a gated AUP licence.

### Cited Findings
**Depth Anything V2**
- Small (24.8M) is Apache-2.0. Base (97.5M), Large (335.3M) and Giant (1.3B, not released) are CC-BY-NC-4.0. Default input is 518 px, and a larger input gives finer detail — [DA-V2 GitHub](https://github.com/DepthAnything/Depth-Anything-V2)
- The README does not state a licence for the metric models (built on Small and Base). The Base-based one probably inherits NC (inference, unconfirmed) — [DA-V2 GitHub](https://github.com/DepthAnything/Depth-Anything-V2)
- In the MoGe-2 table, DA V2-L (335M, 518²) runs at 24 ms FP16 / 86 ms FP32 and 0.91 / 1.8 GB on an A100. Boundary F1 is 13.9 on iBims-1, 4.74 on HAMMER, 32.5 on Sintel and 6.10 on Spring — [MoGe-2 arXiv 2507.02546](https://arxiv.org/html/2507.02546v1)

**Depth Anything 3 (ByteDance-Seed)**
- Licences by model:
  - CC BY-NC 4.0: DA3NESTED-GIANT-LARGE(-1.1) (1.40B), DA3-GIANT(-1.1) (1.15B) and DA3-LARGE(-1.1) (0.35B).
  - Apache 2.0: DA3-BASE (0.12B), DA3-SMALL (0.08B), DA3METRIC-LARGE (0.35B, monocular metric) and DA3MONO-LARGE (0.35B, monocular relative).
  - Source: [DA3 GitHub](https://github.com/ByteDance-Seed/Depth-Anything-3)
- DA3METRIC converts to meters with `metric_depth = focal * net_output / 300`, using the focal length in pixels. With our calibrated focal lengths this applies directly. DA3MONO predicts depth directly rather than disparity, which the authors say gives "better geometric accuracy". The -1.1 models were retrained after a bug fix and are "much better on street scenes". The README gives no VRAM figures and no fine-detail metrics. DA3-Streaming runs in under 12 GB — [DA3 GitHub](https://github.com/ByteDance-Seed/Depth-Anything-3)
- Licence caveat: the Apache-licensed DA3 models are the non-1.1 variants or the METRIC and MONO models, so the street-scene improvement of -1.1 applies to DA3-LARGE-1.1, which is NC. The README table does not show whether METRIC and MONO were retrained — [DA3 GitHub](https://github.com/ByteDance-Seed/Depth-Anything-3)

**MoGe / MoGe-2 / MoGe-3 (Microsoft)**
- The code is MIT, and the DINOv2 part is Apache 2.0. The HF card for `Ruicheng/moge-2-vitl-normal` lists the licence as MIT — [MoGe GitHub](https://github.com/microsoft/MoGe), [HF moge-2-vitl-normal](https://huggingface.co/Ruicheng/moge-2-vitl-normal)
- Variants:
  - MoGe-2: vitl (326M), vitl-normal (331M), vitb-normal (104M) and vits-normal (35M). All are metric, and the -normal variants also output normals.
  - MoGe-3: vitg (1.25B) and vitl (370M), described as "Fine-Detail" (qualitative only).
  - Latency is about 60 ms on an A100 or RTX 3090 (FP16, ViT-L).
  - Source: [MoGe GitHub](https://github.com/microsoft/MoGe)
- In the MoGe-2 paper, MoGe-2 has the best average rank for relative geometry (2.05), metric geometry (1.95; metric depth Reld 15.7 / δ1 76.8 vs UniDepth V2 21.3 / 75.3 and Depth Pro 27.6 / 54.4). Boundary F1 is 17.9 on iBims-1, 5.42 on HAMMER, 35.2 on Sintel and 8.63 on Spring, for a rank of 1.75. On the 10-dataset average for scale-invariant points, MoGe-1 is better than MoGe-2 (Relp 7.46 vs 10.8). MoGe-2 wins only on local points (5.33 vs 5.50) — [MoGe-2 arXiv](https://arxiv.org/html/2507.02546v1)
- MoGe-2 memory on an A100 (FP16 / FP32):
  - 484²: 0.96 / 1.7 GB, 29 / 82 ms
  - 840²: 1.3 / 2.5 GB, 55 / 238 ms
  - 1188²: 1.9 / 3.8 GB, 108 / 565 ms
  - Source: [MoGe-2 arXiv](https://arxiv.org/html/2507.02546v1)

**Depth Pro (Apple)**
- The code and weights are released "under the LICENSE terms". The LICENSE is a permissive Apple licence ("use, reproduce, modify and redistribute ... with or without modifications"), with no commercial restriction found, keeping the notice and no use of Apple trademarks. Third-party parts are covered by ACKNOWLEDGEMENTS — [ml-depth-pro GitHub](https://github.com/apple/ml-depth-pro), [LICENSE](https://raw.githubusercontent.com/apple/ml-depth-pro/main/LICENSE)
- It produces a metric 2.25 MP depth map in 0.3 s on a "standard GPU". The repo includes boundary metrics (SI_boundary_F1/Recall). The released model is a retrained reference model and does not match the paper exactly — [ml-depth-pro GitHub](https://github.com/apple/ml-depth-pro)
- In the MoGe-2 table, Depth Pro has the best boundary average rank (1.50; Sintel 41.6, Spring 11.0). Its metric accuracy is weaker (depth δ1 54.4). It has 504M parameters, runs at 1536², takes 139 ms FP16 / 906 ms FP32, and uses 3.7 GB FP16 / 8.0 GB FP32 on an A100 — [MoGe-2 arXiv](https://arxiv.org/html/2507.02546v1)

**Metric3D v2**
- The code is BSD-2-Clause. The README states no licence for the weights. Variants are ViT-S, ViT-L and ViT-g2. It outputs normals with a confidence channel (`prediction_normal`, channel 3 = confidence) — [Metric3D GitHub](https://github.com/YvanYin/Metric3D)
- Accuracy:
  - Affine-invariant ETH3D (the closest benchmark to facades, outdoor and building scenes): AbsRel 0.042 / δ1 0.987 (ViT-L)
  - Metric KITTI: AbsRel 0.044 (ViT-L) / 0.039 (ViT-g)
  - Source: [Metric3D GitHub](https://github.com/YvanYin/Metric3D)
- Boundary F1 is the weakest in the MoGe-2 table (iBims 7.36, HAMMER 1.40). It has 412M parameters, runs at 1064×616 and uses 1.4 / 2.3 GB — [MoGe-2 arXiv](https://arxiv.org/html/2507.02546v1)

**UniDepth V1 / V2**
- The software is CC BY-NC 4.0, which is NC. Backbones are ViT-S, ViT-B and ViT-L. V2 reaches ETH3D d1 85.2 (V1: 18.5) and iBims-1 94.5 (author figures) — [UniDepth GitHub](https://github.com/lpiccinelli-eth/UniDepth)

**Marigold (prs-eth)**
- The code is Apache 2.0. The models are under the "RAIL++-M License" (LICENSE-MODEL.txt). Checkpoints: Depth v1-0, Depth LCM v1-0, Depth v1-1 (2025-05, 1 step / ensemble 10), Normals v1-1 (4 steps) and IID. SD runs best at 768²; `--processing_res 0` uses the native resolution — [Marigold GitHub](https://github.com/prs-eth/Marigold)

**Lotus**
- The code is Apache-2.0, and the README states no licence for the weights. Depth (g/d, v1 plus v2 disparity) and normal (g/d v1-1) models are available. The README claims "SoTA with minimal training data" without numbers — [Lotus GitHub](https://github.com/EnVision-Research/Lotus)

**Prompt Depth Anything (PromptDA)**
- The code is Apache-2.0, and the HF weights `prompt-depth-anything-vitl` are also Apache-2.0. Large is 340M and Small 25.1M. The example prompt is 192×256 metric LiDAR depth (ARKit), and output is at the image resolution ("4K") — [PromptDA GitHub](https://github.com/DepthAnything/PromptDA), [HF PromptDA-L](https://huggingface.co/depth-anything/prompt-depth-anything-vitl)

**VGGT / MapAnything**
- VGGT-1B is CC-BY-NC-4.0. VGGT-1B-Commercial is gated under a "vggt-aup-license" (according to a mirror README, commercial use is allowed except military use; the text was not readable) — [HF VGGT-1B-Commercial](https://huggingface.co/facebook/VGGT-1B-Commercial), [Mirror README](https://github.com/HardingPan/VGGT)
- MapAnything:
  - Code is Apache 2.0. `facebook/map-anything` is CC-BY-NC, and `facebook/map-anything-apache` is Apache 2.0 ("recommended for commercial use").
  - Inputs can include `intrinsics`, `camera_poses`, `depth_z` (requires intrinsics) and `is_metric_scale`.
  - Outputs are `depth_z`, `pts3d` and `conf`. Whether sparse depth is accepted is not clearly documented.
  - Source: [MapAnything GitHub](https://github.com/facebookresearch/map-anything)

### Inferences
- For our RTX 4060 (8 GB), all the ViT-L class models (DA3-METRIC/MONO-L, MoGe-2-L, Depth Pro FP16, PromptDA-L) should fit, judging by the A100 memory figures (≤ 3.7 GB FP16). Depth Pro FP32 at 8.0 GB does not fit, so run it in FP16. Speed will be roughly 2-4x slower than on an A100 (estimate).
- An oriel at 0.5-1 m relief seen from 15-30 m is about 2-5 % of depth. A cornice or reveal at 0.1-0.3 m is about 0.5-2 %. The best global AbsRel values (about 4 %, Metric3D on ETH3D) are larger than that. Global depth accuracy is therefore not enough for cornices; only local or relative accuracy (MoGe-2 "local points" Relp 5.3 %, still coarse) and edge sharpness help. Oriels should be visible after a scale and shift fit; cornices and reveals are more likely to come from normals and edges than from depth values (inference).
- Ranking for facade relief by boundary F1 plus local geometry, commercially usable: Depth Pro (sharpest), then MoGe-2 (best overall and gives normals, MIT), then DA3-MONO-L. PromptDA is special because it can take a prompt.

### Gaps
- Unconfirmed weight licences: Metric3D v2, Lotus, StableNormal, DA V2 metric, DA3-METRIC/MONO-1.1 (whether they exist).
- I found no Marigold-LCM numbers and no DepthCrafter details (video model, not researched).
- I found no exact VRAM figures for DA3 or PromptDA.

## 2. Normal models: licence and quality on architecture

### Takeaway
For commercial use, MoGe-2-normal (MIT) and StableNormal (Apache code; weights unconfirmed) stand out. Marigold Normals v1-1 is RAIL++-M, which is a use-restricted licence and probably allows commercial use (check the text). GeoWizard is CC BY 4.0, which allows commercial use with attribution. Metric3D v2 has BSD code and normals with confidence, but the weights licence is unclear. DSINE is non-commercial (Imperial College licence) and therefore ruled out for sale.

### Cited Findings
- DSINE's licence is the "Imperial College London Software Licence Agreement (Excluding BSD Components)", a non-commercial research licence. The README describes predictions as "crisp — yet, piecewise smooth" and does not discuss outdoor scenes — [DSINE LICENSE](https://raw.githubusercontent.com/baegwangbin/DSINE/main/LICENSE), [DSINE GitHub](https://github.com/baegwangbin/DSINE)
- StableNormal:
  - Code is Apache-2.0. StableNormal-turbo is about 10x faster.
  - Mean angular error: DIODE-indoor 13.70°, iBims-1 17.25°, ScanNet (turbo) 17.43°.
  - Only indoor benchmarks are reported, with no building or outdoor notes.
  - Source: [StableNormal GitHub](https://github.com/Stable-X/StableNormal)
- Marigold Normals v1-1 (2025-05-15) uses 4 steps with an ensemble of 10, under the RAIL++-M model licence — [Marigold GitHub](https://github.com/prs-eth/Marigold)
- GeoWizard:
  - "released under the CC BY 4.0 License", with no separate licence for the weights.
  - Outputs depth and normals together; offers `--domain outdoor`.
  - Defaults are ensemble 3 with 10 steps (academic setting: 10/50).
  - Normals can be integrated with BiNI.
  - Source: [GeoWizard GitHub](https://github.com/fuxiao0719/GeoWizard)
- Metric3D v2 normals come with a confidence channel — [Metric3D GitHub](https://github.com/YvanYin/Metric3D)
- MoGe-2 vits/vitb/vitl "-normal" variants (35M-331M) are MIT — [MoGe GitHub](https://github.com/microsoft/MoGe), [HF](https://huggingface.co/Ruicheng/moge-2-vitl-normal)
- Lotus normal g/d v1-1: code Apache, weights licence not stated — [Lotus GitHub](https://github.com/EnVision-Research/Lotus)

### Inferences
- Normals are the better signal for cornices and reveals. A cornice is a 45-90° change in normal over a few pixels, whereas in depth it is only a 0.5-2 % change. A workable approach: fix the wall plane from LoD2 (known normal), then segment pixels whose normal deviates strongly from it (soffits, reveal side faces) and turn them into relief depth by integrating normals (BiNI-like) between depth anchors (the wall plane and SfM points).
- Diffusion normal models (Marigold, StableNormal, GeoWizard) are slower but sharp. Feed-forward models (MoGe-2-normal, Metric3D) are fast. Run several and compare normals per pixel. Disagreement is a source conflict and should not be averaged (CLAUDE.md rule 5).

### Gaps
- I found no normal benchmark on outdoor building facades (all tables are indoor: NYUv2, ScanNet, iBims, DIODE-indoor).
- I did not check the Omnidata licence or quality.
- I did not read the RAIL++-M text to see whether it allows commercial use and which use restrictions apply.
- I could not confirm the licence of the StableNormal weights (it builds on SD; the base licence probably applies).

## 3. Fusing monocular depth with SfM points and the LoD2 plane

### Takeaway
There are three ways to do this:
- **Scale and shift fit** of the relative depth per image against SfM points or LoD2 plane depth. This is simple and robust, but it inherits the noise of the SfM cloud.
- **Prompt depth / depth completion**: PromptDA (Apache), which takes a low-resolution metric depth map such as rendered LoD2 plus SfM points; Marigold-DC (Apache code, Marigold weights RAIL++-M), which takes sparse points without training; Prior Depth Anything (licence unclear).
- **Multi-view models with known poses**: MapAnything-apache with intrinsics, poses and depth input.

### Cited Findings
- Marigold-DC (ICCV 2025) does zero-shot depth completion. Sparse depth guides the denoising at test time, with no training needed; the example uses 100 points. It takes 10.7 s (bf16, 50 steps) or 3.7 s (Tiny VAE, compiled) on an A100, and the code is Apache-2.0. Only NYUv2 numbers are given (MAE 0.066 m, RMSE 0.171 m on 100 samples) — [Marigold-DC GitHub](https://github.com/prs-eth/Marigold-DC)
- PromptDA takes a low-resolution metric depth prompt (192×256 LiDAR in the example) and produces up to 4K metric depth. Both code and weights are Apache — [PromptDA GitHub](https://github.com/DepthAnything/PromptDA)
- Prior Depth Anything ("Depth Anything with Any Prior", arXiv 2505.10565) handles completion, super-resolution and inpainting from mixed depth priors. I could not confirm its licence (an aggregator says CC BY-SA 4.0, probably the paper licence) — [Project page](https://prior-depth-anything.github.io), [arXiv](https://arxiv.org/abs/2505.10565v1)
- MapAnything accepts intrinsics, poses and `depth_z` as conditioning, and the Apache weights variant is available — [MapAnything GitHub](https://github.com/facebookresearch/map-anything)
- DA3METRIC uses the focal length directly to get meters, so our calibrated focal lengths fit — [DA3 GitHub](https://github.com/ByteDance-Seed/Depth-Anything-3)
- BetterDepth (a diffusion refiner) measures depth-boundary completeness and accuracy plus edge precision and recall, because GT labels are often sparse or noisy. This is a usable template for a facade edge metric — [BetterDepth arXiv](https://arxiv.org/pdf/2407.17952)

### Inferences
- Proposed pipeline (unverified):
  1. Render LoD2 depth per calibrated camera (we already have the camera bridge).
  2. Fit scale and shift (or depth versus disparity, depending on the model) by robust RANSAC against the LoD2 wall-plane pixels, which are large and free of occluders. This anchors to official geometry rather than circularly to the model.
  3. Residual = mono depth − LoD2 plane = relief map.
  4. Check against SfM points: is the residual consistent with the dense cloud?
  5. Fuse across several photos, and accept relief only where it is consistent across views.
- PromptDA with the rendered LoD2 depth as prompt is attractive because it is Apache and its output is metric at high resolution. However, the prompt carries no relief, so the relief would come from the image prior alone. Test whether the model then "hallucinates the prompt flat".
- With PromptDA or Marigold-DC, do not feed the SfM points that serve as the check (hold-out); otherwise the evaluation is circular, in the spirit of register CB.
- For counting features (windows), the existing rule still applies: count only on the photo; depth and normals give geometry, not counts.

### Gaps
- I found no published accuracy gains for SfM plus mono fusion specifically on facades.
- The Marigold-DC licence situation is mixed: Apache code but RAIL++-M base weights.
- MapAnything's accuracy with given poses and depth on outdoor scenes was not researched.

## 4. Evaluations on building facades and architectural detail

### Takeaway
I found no dedicated facade or relief benchmark for monocular depth. The closest data are ETH3D (outdoor and buildings, in the MoGe-2 and Metric3D tables) and boundary F1 on iBims-1, Sintel and Spring. We will have to evaluate ourselves: LoD2 plane plus SfM hold-out points plus a profile laser or photo measurement on a known facade, for example the Martinstor.

### Cited Findings
- ETH3D is part of the relative and metric averages in MoGe-2, but the averages hide per-dataset values — [MoGe-2 arXiv](https://arxiv.org/html/2507.02546v1)
- Metric3D v2 ETH3D affine-invariant: AbsRel 0.042, δ1 0.987 — [Metric3D GitHub](https://github.com/YvanYin/Metric3D)
- UniDepth V2 ETH3D d1 85.2 (metric, author figure) — [UniDepth GitHub](https://github.com/lpiccinelli-eth/UniDepth)
- BS3D (2023) is a building-scale RGB-D dataset. Fine-tuning LeReS on it improved results on BS3D and iBims-1 — [BS3D arXiv](https://arxiv.org/pdf/2301.01057)
- The 4th Monocular Depth Estimation Challenge (SYNS-Patches) includes urban scenes but has no facade focus — search result, [arXiv 2504.17787](https://arxiv.org/abs/2504.17787v1)
- MonoDeMB (KDD 2025) is a general benchmark with no facade detail found — [AIRI](https://airi.net/articles/monodemb-comprehensive-monocular-depthmap-benchmark)

### Inferences
- Our own test bed would use the Martinstor:
  - Measure cornice and oriel depth by `foto_mass.py` or a document as the reference value.
  - Compare the relief maps from MoGe-2, DA3-MONO, Depth Pro and PromptDA (Apache/MIT only), plus NC models for testing only, entered in LIZENZ_WERKZEUGE.md.
  - Use an edge metric like BetterDepth's.
- Expectation without proof: oriels (0.5-1 m) are detectable, while 0.1-0.3 m cornices come out reliably only through normals and edges, with depth from the LoD2 plus SfM anchor.

### Gaps
- I found no published facade-relief accuracy (cm error on cornices or reveals) for any model.
- I did not read the ETH3D per-dataset values in the MoGe-2 appendix.
