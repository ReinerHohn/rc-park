# Faster SfM/MVS for the building-photo pipeline (state as of Nov 2026)

Context: COLMAP/pycolmap 4.2.1, SIFT-GPU, incremental mapper on CPU, LightGlue, 100-2000 photos per building, RTX 4060 Laptop 8 GB (optionally a rented 4090/5090). Models are meant for commercial sale.

## GLOMAP / global SfM (now inside COLMAP)

### Takeaway
GLOMAP is BSD-3 and now part of COLMAP. Since COLMAP 4.0 it runs as the `global_mapper`, so pycolmap 4.2.1 already has it with nothing extra to install. The authors claim it is "1-2 orders of magnitude" faster than incremental SfM. An independent table (InstantSfM paper) shows a more modest 4-8x on internet photo collections. On hard indoor data it fails more often than incremental COLMAP.

### Cited Findings
- The GLOMAP repo is BSD-3-Clause (ETH Zurich 2024). It was archived on 2026-03-09 and is "fully migrated to COLMAP" as the "global" mapper. The README claims it is "typically 1-2 orders of magnitude faster" than incremental COLMAP, with "on-par or superior" quality, but gives no numbers in the README itself. — [GLOMAP GitHub](https://github.com/colmap/glomap)
- COLMAP 4.0.0 (2026-03-14) integrates GLOMAP as a first-class global pipeline, run via `global_mapper` or `automatic_reconstructor --mapper GLOBAL`. It uses view-graph calibration, so intrinsics can differ from the incremental mapper's. — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- In COLMAP 4.2.0 (2026-08-31) the global mapper reconstructs all connected components and can return several models (a breaking change; `GlobalMapper.multiple_models`). The same release added a hierarchical mapper to pycolmap and a GUI selector (incremental/global/hierarchical). 4.2.1 (2026-09-29) restored the legacy global-mapper BA behaviour after a 4.2.0 regression. — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- COLMAP 4.1.0 gave the global mapper rotation-averaging options and `keep_max_num_tracks`. — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- Independent runtimes (InstantSfM paper, Table V):
  - Alamo: COLMAP 12855 s vs GLOMAP 1600 s (about 8x)
  - Madrid_Metropolis: 1662 s vs 441 s (about 3.8x)
  - Union_Square: 4697 s vs 966 s (about 4.9x)
  These are internet photo collections, which are similar to our web/street-level photos. — [InstantSfM arXiv v2](https://arxiv.org/html/2510.13310v2)
- Robustness: on ScanNet both COLMAP and GLOMAP report "FAILED" on average, and GLOMAP fails through Ceres divergence in ViewGraphCalibration. On DTU (NVS), GLOMAP's PSNR is 17.98 vs COLMAP's 25.00, so it is clearly worse there. On ScanNet++, GLOMAP's Chamfer is 3.80 vs COLMAP's 4.43, so it is slightly better. — [InstantSfM arXiv v2](https://arxiv.org/html/2510.13310v2)

### Inferences
- For 100-2000 images, the realistic expectation is a 3-8x shorter mapper time than incremental. "10-100x" is the authors' claim, not confirmed by independent measurement.
- The DTU failure and the ViewGraphCalibration divergence suggest a risk with few images, or with images that have similar but varying intrinsics (web photos from many cameras). We should test this per object against the incremental result, for example on reprojection error, registered images and the foto_diff overlay. We should not take either result over blindly.
- The 4.2 behaviour (several models per component) matters for our side separation of symmetric facades (see memory "SfM Seitentrennung"). Components that get split must be checked explicitly.

### Gaps
- No independent benchmark of GLOMAP vs incremental on street-level/Mapillary sequences with large viewpoint gaps.
- No figure on the hierarchical mapper's speedup in 4.2.

## COLMAP GPU bundle adjustment, InstantSfM, retrieval for pair selection

### Takeaway
The biggest single lever in our current version is Caspar, a GPU BA backend in COLMAP since 4.1 that pycolmap 4.2.1 already includes. The changelog reports it as "often 1-2 orders of magnitude faster than the Ceres CUDA backend" on medium and large problems. InstantSfM (PyTorch, GPU-global) measured 1.7-2.7x faster than GLOMAP, but on an H200, and its code license is unclear. MegaLoc (MIT) is a commercially usable retrieval model for pair selection. COLMAP's own vocabulary tree now also works with ALIKED.

### Cited Findings
- COLMAP 4.1.0 (2026-06-26) adds "Caspar", a GPU-accelerated BA backend you can select instead of Ceres. It supports rigs, GPU selection and pycolmap bindings, and is "often 1-2 orders of magnitude faster than the Ceres CUDA backend" for medium to large problems. Since 4.1.1 it needs CUDA architecture >= 7.0 (the RTX 4060 is sm_89, so that is fine). — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- BA falls back to the CPU solver if the GPU solver fails (4.0), or when CUDA is compiled in but no compatible GPU is present (4.2). — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- Other measured gains in our version range:
  - Analytical Jacobians make incremental mapping "approximately 1.2-1.55x faster" (4.2.0).
  - Ceres BA is about 10% faster (single pose block) and about 15% faster (SIMPLE_RADIAL) (4.0).
  - Image I/O via OpenImageIO is about 2.5x faster (4.0).
  - Undistortion warping is 4-7x faster (4.2).
  - A fix in 4.1 removed a 4-6x feature-matching slowdown (OpenMP critical section in RANSAC).
  — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- The exhaustive matcher was sped up via faiss `IndexIVFScalarQuantizer` (4.1; no figure given). 3.13 brought multi-GPU extraction/matching without a global mutex. — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- COLMAP 4.0 has ALIKED (N16Rot/N32) extraction via ONNX, LightGlue-ONNX matching for SIFT and ALIKED, and vocabulary-tree retrieval for ALIKED. 4.2 adds learned "LoMa" features/matching via ONNX (optional BF16). — [COLMAP Changelog](https://colmap.github.io/changelog.html)
- InstantSfM (arXiv 2510.13310) is a sparse, parallel global SfM with GPU BA in PyTorch. Its abstract claims "up to ~40x" over COLMAP, but Table V shows at most 21.5x over COLMAP and 1.7-2.7x over GLOMAP (Alamo 597 s vs GLOMAP 1600 s). Measured on an NVIDIA H200 (140 GB). Metric scale comes only from metric depth priors (ScanNet Chamfer 0.658 with depth vs 0.842 without). The code is at github.com/cre185/InstantSfM; the paper is CC BY-NC-SA, and the code license is not given in the paper. — [InstantSfM arXiv v2](https://arxiv.org/html/2510.13310v2), [Search summary v1/v2](https://arxiv.org/abs/2510.13310v1)
- The figures are inconsistent across versions: v1 says "~40x" generally, while v2 says "1.5x to 40x over COLMAP, up to 12x over GLOMAP for 100-5000 images". — [arXiv v1](https://arxiv.org/abs/2510.13310v1); the tabulated numbers in v2 are lower — [arXiv v2 HTML](https://arxiv.org/html/2510.13310v2)
- MegaLoc ("One Retrieval to Place Them All", arXiv 2502.17237) is a universal retrieval model, SOTA on most VPR datasets. The repo is MIT-licensed and loads via torch.hub; input is 322x322, output is an 8448-dim L2-normalised descriptor. — [MegaLoc GitHub](https://github.com/gmberton/MegaLoc), [arXiv](https://arxiv.org/html/2502.17237v3)
- A 2026 paper uses MegaLoc for k-NN pair graphs in SfM and criticises that pairs are chosen independently, without global consistency. — [Global-Aware Edge Prioritization, arXiv 2602.21963](https://arxiv.org/html/2602.21963). An alternative is SARA, which pre-selects pairs by overlap x parallax before matching. — [arXiv 2601.11930 / search result](https://arxiv.org/html/2601.11930v1)

### Inferences
- Immediately testable without a new install: `pycolmap` BA with the Caspar backend, plus the global mapper. This fits the existing user request "COLMAP GPU nutzen" (memory note). The "1-2 orders of magnitude" applies to BA only, not to the whole mapper. Measure it ourselves with aufwand_log.
- Exhaustive matching grows as O(n^2): 2000 images is about 2 million pairs. Retrieval with top-k (k about 30-50) is about 60-100k pairs, a 20-30x saving in matching. This is our own estimate, not a measured value.
- MegaLoc is MIT and therefore cleaner for commercial use than NetVLAD/ASMK variants with unclear weights.
- Do not use InstantSfM in production until the code license is checked. The H200 numbers cannot be transferred to 8 GB.

### Gaps
- No public benchmark figure for Caspar vs Ceres-CPU on 500-2000-image building datasets. No VRAM figure for Caspar with 8 GB.
- InstantSfM code license (LICENSE file not checked).
- No measured comparison of vocabulary tree vs MegaLoc vs exhaustive on facade photos (recall/time).

## Learned feed-forward reconstruction (VGGT, VGGT-Long, Pi3, MapAnything, MASt3R/DUSt3R, CUT3R, Fast3R)

### Takeaway
Licenses are the main filter. Only two are commercially clean:
- VGGT-1B-Commercial (new checkpoint, access by application form, code commercially usable except for military use)
- MapAnything Apache variant (`facebook/map-anything-apache`), which also outputs metric scale

MASt3R (and therefore MASt3R-SfM) is CC BY-NC-SA, and the Pi3/Pi3X weights are CC BY-NC. Both are test-only. None of the sources gives a solid accuracy figure against COLMAP on building photos.

### Cited Findings
- VGGT:
  - Since the 2025-07-29 update the code is under a license that permits commercial use except military use. Only the checkpoint VGGT-1B-Commercial is licensed for commercial use; the original stays NC. Access requires an application form.
  - Co3D AUC@30 is 90.37 (Commercial) vs 89.98 (original).
  - It reconstructs "typically in under 1 second". A 2026-05-15 fix allows about 2-3x more frames on the same VRAM.
  - The repo has a COLMAP export with optional BA. The README warns that reduced BA settings are less robust in complex scenes.
  - No VRAM table or COLMAP comparison in the README.
  — [VGGT GitHub](https://github.com/facebookresearch/vggt)
- MapAnything (Meta):
  - The code is Apache 2.0. Checkpoints `facebook/map-anything(-v1)` are CC BY-NC 4.0; `facebook/map-anything-apache(-v1)` are Apache 2.0 and recommended for commercial use.
  - It regresses "factored metric 3D geometry": metric points, depth, poses, intrinsics and `metric_scaling_factor`.
  - Memory-efficient mode reaches "up to 2000 views on 140 GB".
  - No quantitative accuracy figures in the README.
  — [MapAnything GitHub](https://github.com/facebookresearch/map-anything)
- Pi3 / Pi3X:
  - The code is BSD-3 (commercial use permitted). The weights of Pi3 and Pi3X are CC BY-NC 4.0, "strictly non-commercial", and the restriction carries over on redistribution.
  - Pi3X delivers "approximate" metric scale; Pi3 is scale-invariant.
  - No speed or VRAM figures in the README; paper arXiv 2507.13347.
  — [Pi3 GitHub](https://github.com/yyfz/Pi3)
- MASt3R / MASt3R-SfM:
  - The code is CC BY-NC-SA 4.0. The checkpoints additionally require agreeing to the licenses of all training datasets ("MapFree very restrictive").
  - MASt3R-SfM is retrieval (ASMK) plus `sparse_global_alignment`. `demo_glomap.py` and the kapture tools are untested "toys".
  - The main checkpoint is "metric" (trained with metric regression), but the units are not documented.
  — [MASt3R GitHub](https://github.com/naver/mast3r)
- VGGT-Long (chunk, loop, align, for km-scale sequences):
  - The license follows VGGT; for commercial use it points to the VGGT-1B-Commercial weights.
  - Backbones VGGT, Pi3 and MapAnything are selectable. Metric scale via MapAnything ("Map-Long").
  - Test machine was an RTX 4090 24 GB; VRAM is handled through chunking. No total runtime is given.
  — [VGGT-Long GitHub](https://github.com/DengKaiCQ/VGGT-Long), [arXiv 2507.16443](https://arxiv.org/abs/2507.16443)
- InstantSfM reports that learning-based methods like VGGSfM/VGGT run out of memory at about 5000 images. — [InstantSfM search summary](https://arxiv.org/abs/2510.13310v1)

### Inferences
- With the Pi3 backbone, VGGT-Long is NC because of the weights. Only VGGT-Commercial or MapAnything-Apache is clean. Note: the memory already lists VGGT-1B as NC; that needs updating, since there is now a commercial checkpoint.
- On 8 GB VRAM these models are realistic only on small chunks (my estimate, no source figure). For 2000 photos they serve as an initialisation or fallback for poorly connected images, not as a replacement for COLMAP. Full COLMAP BA should then follow.
- The "metric" output of MapAnything or Pi3X is learned, so it is an approximation. Under project rule 3d it does not replace the official anchors (LoD2/DOM1/DGM1). It may serve at most as a plausibility check.

### Gaps
- No reliable source checked for DUSt3R (presumably CC BY-NC-SA like MASt3R, same Naver group; unverified), CUT3R or Fast3R (licenses and VRAM unverified).
- No numeric accuracy comparison of VGGT/MapAnything vs COLMAP on building/street-level data found; the VGGT/MapAnything papers were not read in detail.
- VRAM per frame count for VGGT/MapAnything on 8 GB unknown.

## Dense MVS alternatives (OpenMVS, ACMMP, Gaussian splatting/2DGS/PGSR, MVSFormer)

### Takeaway
Hardly any of the well-known fast dense methods is commercially clean:
- OpenMVS is AGPL-3.0: copyleft, and the network clause applies to services.
- 2DGS uses the Inria/MPII Gaussian-Splatting license (non-commercial).
- PGSR has a ZJU licence for research/non-profit only.

gsplat (Apache-2.0) is the clean rasteriser base. COLMAP itself (PatchMatch, now also with ROCm and an advancing-front mesher) remains the safe option.

### Cited Findings
- OpenMVS: the COPYRIGHT file says AGPL; GitHub shows AGPL-3.0. Issue #524 asks for a GPL licence, outcome unknown. — [OpenMVS COPYRIGHT](https://github.com/cdcseacave/openMVS/blob/master/COPYRIGHT.md), [Issue #524](https://github.com/cdcseacave/openMVS/issues/524)
- 2DGS: "Gaussian-Splatting License" (Inria + MPII). Use only "non-commercially, i.e., for research and/or evaluation purposes"; commercial use requires consent from Inria. — [2DGS LICENSE](https://raw.githubusercontent.com/hbb1/2d-gaussian-splatting/main/LICENSE.md)
- PGSR:
  - Licence from ZJU 3D Vision Group, "educational, research and non-profit purposes only". Commercial use requires contacting the authors, and modifications may not be used commercially.
  - Training takes about 0.5-0.6 h on DTU and about 45 min to 1.2 h on Tanks and Temples (hardware not stated).
  - DTU Chamfer 0.47-0.53; TnT F1 0.50-0.51.
  — [PGSR LICENSE](https://raw.githubusercontent.com/zju3dv/PGSR/main/LICENSE.md), [PGSR GitHub](https://github.com/zju3dv/PGSR)
- gsplat (nerfstudio): Apache-2.0. Up to 4x less GPU memory and up to 15% less time than the official 3DGS implementation. The README does not mention 2DGS support or mesh extraction. — [gsplat GitHub](https://github.com/nerfstudio-project/gsplat)
- ACMMP: needs CUDA, tested on a GTX 1080 Ti, takes COLMAP SfM via `colmap2mvsnet_acm.py`. The licence type is not stated in the README (LICENSE file exists), and there is no speed comparison with COLMAP. — [ACMMP GitHub](https://github.com/GhiXu/ACMMP)
- COLMAP 4.2 added ROCm/HIP for `patch_match_stereo`, 4.1 an advancing-front mesher, and 4.0.3 fixed empty PatchMatch results on Blackwell (sm_100+). This matters for a rented RTX 5090. — [COLMAP Changelog](https://colmap.github.io/changelog.html)

### Inferences
- For sale: we must not ship the output of a 2DGS/PGSR/Inria-3DGS pipeline without a licence agreement. Whether generated meshes count as "use" is a legal question, but the licences rule out commercial use of the software. A gsplat-based surface variant (own code or Apache-licensed derivatives) would be the clean path.
- OpenMVS only as a separate process (CLI), never linked into the code. Even then the AGPL obligations should be checked before selling; the safest course is to use it only for testing.
- Our pipeline forms the shape mostly through the generator (STL) and uses points for colour and refinement (memory "Hybrid Generator+Bildpunkte"). Dense MVS speed may therefore matter less than SfM poses.

### Gaps
- ACMMP licence text not read.
- MVSFormer/MVSFormer++ not investigated (licence, VRAM).
- No source-backed speed figure for OpenMVS or ACMMP vs COLMAP PatchMatch.

## Feature matching (LightGlue fp16/flash, pruning, ALIKED/DISK/SuperPoint/XFeat)

### Takeaway
LightGlue's code and weights are Apache-2.0, and the ALIKED (BSD-3) and DISK paths are commercially usable. SuperPoint (Magic Leap licence, also covering `lightglue/superpoint.py` and its weights) is not. XFeat appears to be Apache-2.0, based on a badge and the Kornia port. Speed: about 150 FPS at 1024 keypoints and about 50 FPS at 4096 on an RTX 3080 with compile plus adaptivity.

### Cited Findings
- LightGlue:
  - Code and pretrained weights are Apache-2.0. DISK falls under the same licence; ALIKED is BSD-3. SuperPoint has a "different, restrictive" licence covering both the weights and the inference file `lightglue/superpoint.py`.
  - Speed on an RTX 3080 with compile and adaptivity: about 150 FPS at 1024 keypoints and about 50 FPS at 4096. That is 4-10x faster than SuperGlue. CPU (i7-10700K): about 20 FPS at 512 keypoints.
  - Mixed precision (`mp`) is off by default. FlashAttention is used automatically with torch >= 2.0 and does not affect accuracy (no figure given).
  - `depth_confidence` defaults to 0.95 and `width_confidence` to 0.99; setting either to -1 disables it.
  - `compile(mode='reduce-overhead')` disables pruning below 1536 keypoints. The pruning thresholds (`pruning_keypoint_thresholds['cuda']`) should be tuned with `benchmark.py`.
  — [LightGlue GitHub](https://github.com/cvg/LightGlue)
- XFeat (verlab/accelerated_features, CVPR 2024): the README badge says Apache-2.0, and Kornia's port names Apache 2.0 for the Verlab original. The LICENSE file itself was not read. — [XFeat GitHub](https://www.github.com:443/verlab/accelerated_features), [HF Space README](https://huggingface.co/spaces/qubvel-hf/xfeat/raw/main/README.md)
- COLMAP 4.0+ includes ALIKED and LightGlue as ONNX in C++ (no Python/torch needed), and 4.2 adds LoMa with BF16. — [COLMAP Changelog](https://colmap.github.io/changelog.html)

### Inferences
- If SuperPoint+LightGlue is used anywhere in the pipeline, that is an NC component and belongs in `LIZENZ_WERKZEUGE.md`. ALIKED+LightGlue is the clean replacement and runs natively in COLMAP 4.x via ONNX. That saves the Python glue code and the GPU contention between torch and COLMAP (CLAUDE.md: only one GPU job at a time).
- Quick tuning in our own code: `mp=True` (fp16), torch >= 2 for flash attention, check the pruning thresholds for 2048-4096 keypoints with `benchmark.py`. The expected speedup on the 4060 is unmeasured.
- The licence of the LoMa weights in COLMAP 4.2 was not checked. Clarify it before use.

### Gaps
- No measured fp16 speedup figure for LightGlue found.
- XFeat LICENSE file and LoMa weight licence not read directly.
- The SuperPoint licence text (Magic Leap) was not read; its "non-commercial" status rests on the LightGlue README and general knowledge.
