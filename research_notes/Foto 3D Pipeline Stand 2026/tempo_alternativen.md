# Speed-ups and alternative open pipelines for photo-based 3D reconstruction of single buildings on an 8-GB GPU (state 2024-2026)

Research date: 2026-11-19. Reference workload: 1000-2000 images per building; features+matching 19 min; two global mapper runs + fixed-backbone completion 45-68 min; PatchMatch (photometric, 1600 px, window_step 2) 27 min for ~350 images; fusion 4.5 min; RTX 4060 8 GB, 15 GB RAM.

Reading aid: "MEASURED" = number published by the cited source; "CLAIM" = authors' own unverified statement; "SNIPPET" = seen only in a search-result excerpt, page itself not opened. Nothing here was measured on our own hardware.

## 1. COLMAP 4.0-4.3 release notes: what changed for speed, and which options matter on 8 GB

### Takeaway
There is no released COLMAP 4.3 as of this research (latest tagged release on the releases page is 4.2.1); the relevant speed items are Caspar GPU bundle adjustment (4.1.0, but NOT selectable in the global mapper and limited to SIMPLE_RADIAL/PINHOLE), a 4-6x matching slowdown bug fixed in 4.1.1, analytical Jacobians (4.2.0, 1.2-1.55x for incremental mapping) and multi-component global mapping (4.2.0). No release note in 4.0.3-4.2.1 changes PatchMatch speed; PatchMatch changes are bug fixes only.

### Cited Findings
- 4.0.0: GLOMAP integrated into COLMAP as a first-class alternative to incremental/hierarchical mappers (SNIPPET from changelog mirror); GLOMAP development now happens in the COLMAP repository — [SourceForge mirror 4.0.0](https://sourceforge.net/projects/colmap.mirror/files/4.0.0); [radiancefields.com on 4.0](https://radiancefields.com/colmap-4.0-introduces-major-performance-and-infrastructure-updates)
- 4.0.3: fixed handling of bundle-adjustment and rotation-averaging options in the global mapper; fixed empty PatchMatch results on Blackwell GPUs (sm_100+); reduced thread oversubscription in the hierarchical mapper — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.0.4: fixed a crash in AdjustGlobalBundle after aggressive frame filtering — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.1.0: Caspar added as GPU-accelerated alternative to Ceres; release note CLAIM: "Caspar is often 1-2 orders of magnitude faster than the Ceres CUDA backend for medium- to large-scale problems"; Caspar includes rig support — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.1.0: global mapper now inherits all bundle-adjustment options and has rotation-averaging options; fixes for NaN failures from non-PD Cholesky; exhaustive matcher uses IndexIVFScalarQuantizer instead of IndexIVFFlat; color extraction parallelised; SIFT+LightGlue integration fix and ALIKED keypoint filtering fix; forced copy avoided in mvs::Image::SetBitmap — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.1.1: fixed a feature-matching slowdown of ~4-6x caused by a process-global OpenMP critical section in RANSAC/LORANSAC; Caspar build fails early on CUDA architectures below 7.0 — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.2.0: analytical reprojection Jacobians for every camera model and fixed-pose BA; release note MEASURED claim "approximately 1.2-1.55x faster incremental mapping" for common pinhole/OpenCV setups; image warping for modest downscales 4-7x faster in common undistortion cases; selectable std/Boost hash-map backends ("Recent Boost versions can improve incremental-mapping performance") — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.2.0: BREAKING: "The global mapper now reconstructs every connected component by default" (previously only the largest component was kept); optional match-count weighting for rotation averaging; fixed-rotation stage of global BA fixed; Ceres falls back to CPU when no compatible GPU is found — [COLMAP releases](https://github.com/colmap/colmap/releases); [radiancefields.com on 4.2.0](https://radiancefields.com/colmap-4.2.0-adds-multi-component-global-mapping-and-loma-learned-matching)
- 4.2.0: LoMa ONNX feature extraction and matching added; ROCm/HIP acceleration added for patch_match_stereo; antialiased triangle-filter downscaling; fixed corrupted-texture bug in PatchMatch with differing image widths — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.2.1: "Restore legacy bundle-adjustment behavior in the global mapper, fixing a regression introduced in 4.2.0"; retriangulation refinement now optimises only 3D points; GPU memory leak in LoMa matching fixed (ONNX Runtime 1.30.0); unbounded memory growth in Delaunay meshing fixed; CUDA illegal memory access in rotate/transpose/flip kernels for large images fixed; hash-map ABI mismatch that could corrupt memory fixed — [COLMAP releases](https://github.com/colmap/colmap/releases)
- No 4.3 release appears on the releases page; newest non-version assets are ONNX Runtime 1.32.0 binaries (18 Nov) and an ETH3D undistorted dataset (9 Nov) — [COLMAP releases](https://github.com/colmap/colmap/releases)
- Ceres GPU solver: `--Mapper.ba_use_gpu 1` (or `--BundleAdjustmentCeres.use_gpu 1`), example with `--Mapper.ba_max_num_images_direct_sparse_gpu_solver 2000`; needs a Ceres build with CUDA/cuDSS support — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Caspar: experimental, requires build flag `-DCASPAR_ENABLED=ON`; selected with `--Mapper.ba_local_backend CASPAR` / `--Mapper.ba_global_backend CASPAR` / `--BundleAdjustment.backend CASPAR`; supports only `SIMPLE_RADIAL` and `PINHOLE` camera models; the global mapper does not expose a Caspar backend selector — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Other documented BA levers: `--Mapper.ba_global_ignore_redundant_points3D 1`, fewer iterations (`ba_global_max_num_iterations`), looser `ba_global_function_tolerance`, rarer global BA (`ba_global_frames_freq/_ratio`, `ba_global_points_freq/_ratio`), smaller problem via `--FeatureMatching.max_num_matches`, `--SiftExtraction.max_num_features` — [COLMAP FAQ](https://colmap.github.io/faq.html)
- A third-party commercial product advertises a custom COLMAP build with GLOMAP, GPU BA through Caspar and cuDSS and CUDA Ceres (indicates this combination is buildable; no numbers) — [radiancefields.com on Laskos](https://radiancefields.com/laskos-releases-360-gaussian-pro-with-a-rebuilt-colmap)

### Inferences
- Release dates on the page carry no year; 4.0.3 (6 Apr) to 4.2.1 (29 Sep) are presumably 2026. The project's "own build 4.3.dev" mapper is therefore a development snapshot beyond the last release; its changes are not covered by any release note found.
- For our chain (global mapper + fixed-backbone completion): Caspar cannot speed up the global mapper's own BA (no selector), but could apply to the standalone `bundle_adjuster` / incremental completion step IF camera models are SIMPLE_RADIAL or PINHOLE. Internet photos normally need at least SIMPLE_RADIAL, which is supported; OPENCV/RADIAL models are not. Expected gain: unknown on 8 GB (the "1-2 orders of magnitude" is versus Ceres-CUDA and unqualified by hardware). Effort: rebuild with CASPAR_ENABLED, half a day.
- Ceres + cuDSS (`ba_use_gpu`) is the lever that does reach the global mapper, since it "inherits all bundle-adjustment options" since 4.1.0. Whether our build links cuDSS should be checked first (cheap: look for the CPU-fallback message that 4.2.0 introduced).
- Anyone on 4.1.0 exactly should make sure the 4.1.1 matching fix (4-6x) is in; with pycolmap 4.2.1 for matching this is already the case.
- 4.2.0 multi-component default changes outputs of the global mapper (several models instead of one); relevant for our "two mapper runs + side detection" logic. 4.2.0 itself has a global-mapper BA regression; use 4.2.1 or later.

### Gaps
- No official release notes for 4.0.0-4.0.2 were readable on the first releases page (only via mirror snippet); exact 4.0.0 performance items ("improved BA and image I/O performance") are from a secondary article, unquantified.
- No published VRAM requirement for Caspar or cuDSS BA at 1000-2000 images; no independent benchmark of Caspar vs. Ceres-cuDSS on a consumer card found.
- No PR numbers were present in the release notes.
- Nothing found on new PatchMatch speed features in 4.x (only bug fixes and ROCm port).

## 2. PatchMatch stereo and fusion: speed levers and faster alternatives

### Takeaway
COLMAP's own documentation lists the levers but gives almost no numbers; the only explicit values are `__auto__, 30` -> `__auto__, 10` source images, `window_step 2`, and cache sizes as large as RAM permits. Published third-party numbers show OpenMVS roughly 5x faster than COLMAP on a Strecha scene (snippet only) at the price of noisier, more complete clouds, and OpenMVS is AGPL-3.0, which matters for a sold product only if software is distributed, not for sold output.

### Cited Findings
- Documented speed levers: `--PatchMatchStereo.geom_consistency false` together with `--PatchMatchStereo.filter true`; reduce `max_image_size` (stereo and fusion); `window_step 2`; reduce `window_radius`, `num_iterations`, `num_samples`; fewer source images; multiple GPUs via `gpu_index`; interrupted runs resume and skip finished views — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Source images are set in `stereo/patch-match.cfg`: `__auto__, N` picks the N most-overlapping images; FAQ's memory advice is to go from `__auto__, 30` to `__auto__, 10`; `geom_consistency` increases GPU memory use — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Cache: raise `--PatchMatchStereo.cache_size` and `--StereoFusion.cache_size` (GB) as far as RAM allows, "mainly speeds up fusion"; too-low values make processing very slow with heavy disk load — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Large scenes: split into clusters (CMVS, default 100 images per cluster; FAQ recommends as large as resources allow, e.g. 500) — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Insufficient GPU memory can crash patch_match_stereo ungracefully — [COLMAP tutorial](https://colmap.github.io/tutorial.html)
- Anecdote (not controlled): user on a V100 saw COLMAP PatchMatch at ~4-6 s per image step and reports OpenMVS DensifyPointCloud finishing the whole dense step in ~3 min — [COLMAP issue 1734](https://github.com/colmap/colmap/issues/1734)
- SNIPPET: MVP-Stereo paper (Remote Sensing 2024) tables list COLMAP 1046.88 s vs OpenMVS 191.13 s on one Strecha scene, and claims MVP-Stereo gives higher quality than COLMAP in about one third of the time (page returned HTTP 403, numbers not verified in context) — [MVP-Stereo, MDPI](https://www.mdpi.com/2072-4292/16/6/964)
- Quality trade-off: in the ACMP paper's ETH3D comparison OpenMVS has much higher completeness than COLMAP but lower accuracy, attributed to a relaxed consistency requirement in fusion (noisier clouds) (SNIPPET) — [ACMP, arXiv 1912.11744](https://arxiv.org/pdf/1912.11744)
- OpenMVS: license AGPL-3.0; provides dense point cloud, mesh reconstruction, mesh refinement, mesh texturing; `MvsScalablePipeline.py` splits scenes exceeding memory into sub-scenes and merges — [OpenMVS repository](https://github.com/cdcseacave/openMVS)
- An unreviewed COLMAP-based fork claims near-parity dense throughput with OpenMVS DensifyPointCloud (0.95x) (SNIPPET, self-reported) — [mmsp repository](https://github.com/RyanAraaful/mmsp)

### Inferences
- Our current rate is 27 min / ~350 images = ~4.6 s per image at 1600 px, photometric only, window_step 2. That is already the "fast" configuration from the FAQ. The remaining documented levers are: source images (if still at the default of `__auto__, 20`-30, going to 8-10 should scale cost roughly linearly with N, since each source image adds one cost evaluation per hypothesis: plausible 1.5-2.5x, NOT measured), `num_iterations` 5 -> 3 (roughly linear, plausible 1.6x), `num_samples` 15 -> 8-10, `window_radius` 5 -> 4 (cost ~ quadratic in radius with step 2). All are assumptions until timed on one 20-image subset; effort: one hour for an A/B grid with the existing `dicht_modell.py` options.
- A two-stage cascade (photometric pass at 800 px for all images, 1600 px only where the facade image needs it) is the cheapest structural gain for our use, because the dense cloud is only a position veto / height / cross-check under the project's core method. Quarter pixel count gives roughly 4x less PatchMatch time (assumption: cost linear in pixels).
- Fusion at 4.5 min is not a bottleneck; the only relevant lever is `StereoFusion.cache_size` within 15 GB RAM.
- OpenMVS as replacement: plausible 3-5x faster dense step, but noisier cloud and AGPL-3.0. Selling reconstruction RESULTS made with AGPL software does not trigger the AGPL's source-disclosure duty (that applies to distributing/serving the software); this is a legal reading, not a cited finding - have it confirmed if OpenMVS becomes part of a delivered tool.
- ACMMP/ACMM/ACMP family: quality leaders among classical PatchMatch on ETH3D, but no runtime numbers on 8-GB cards and no licence were verified in this research; do not adopt without checking the repository licence.

### Gaps
- No published measurement of COLMAP PatchMatch time as a function of number of source images, num_iterations, num_samples or window_radius was found; COLMAP docs give directions only.
- MVP-Stereo page was not readable (403): GPU model, image resolution, code licence and full tables unverified.
- ACMMP, Gipuma successors: licence and 8-GB runtime not verified. OpenMVS CUDA densification status/speed in current `develop` not stated on the repo front page.
- No source found on running several smaller PatchMatch workspaces in parallel on one 8-GB GPU.

## 3. Global SfM: GLOMAP numbers, failure modes, options, and alternatives

### Takeaway
GLOMAP's published advantage over incremental COLMAP is 1.6x-28x depending on dataset (8x on IMC 2023 phototourism-type data) with equal or better pose AUC; its documented weak points are symmetric/repetitive structure and wrong two-view geometries - exactly the building case. Of the 2025 challengers only FastMap has a verified permissive licence (MIT), but it explicitly trades robustness for speed and is "prone to catastrophic failures" on sparse coverage and poor matches, i.e. on internet photos; InstantSfM reports 2-3x over GLOMAP on 1DSfM scenes but was measured on a 140-GB GPU and its licence could not be confirmed.

### Cited Findings
- GLOMAP vs COLMAP average runtimes (MEASURED, paper tables): ETH3D SLAM 133.5 s vs 1115.4 s; ETH3D MVS rig 793.8 vs 2857.0; ETH3D MVS DSLR 16.5 vs 27.5; LaMAR 12405.3 vs 354660.4; IMC 2023 497.3 vs 4051.0; MIP360 221.0 vs 345.7. Hardware not specified in the retrieved text — [GLOMAP paper](https://arxiv.org/html/2407.20219)
- GLOMAP accuracy (MEASURED): IMC 2023 AUC@3/5/10 deg 69.6/74.6/79.4 vs COLMAP 65.3/70.4/75.1; MIP360 97.5/98.5/99.2 vs 96.5/97.9/98.9; ETH3D DSLR AUC@1/3/5 deg 80.8/88.5/90.3 vs 79.2/86.5/88.1 — [GLOMAP paper](https://arxiv.org/html/2407.20219)
- GLOMAP failure modes stated by the authors: rotation averaging can collapse on symmetric structures (ETH3D exhibition_hall), suggested remedy Doppelgangers; wrong two-view geometries or unmatched pairs under strong appearance/viewpoint change can cause catastrophic failure; repetitive facades + day/night changes hurt all methods on LaMAR CAB; structure refinement skipped on LaMAR LIN due to memory limits — [GLOMAP paper](https://arxiv.org/html/2407.20219)
- GLOMAP pipeline: view graph calibration -> relative pose -> rotation averaging (Chatterjee-Govindu) with angular filtering -> track establishment -> global positioning (random init, Huber, unknown-intrinsics terms down-weighted by 2) -> multi-round global BA (rotations fixed first; stop when filtered-track ratio < 0.1%) -> optional retriangulation + BA; the paper states no track-length or track-count limit — [GLOMAP paper](https://arxiv.org/html/2407.20219)
- Documented speed options (SNIPPET of GLOMAP getting-started doc): cap points with `--TrackEstablishment.max_num_tracks`, rule of thumb ~1000 tracks per image; limit `--GlobalPositioning.max_num_iterations` and `--BundleAdjustment.max_num_iterations`; `--skip_retriangulation` — [GLOMAP getting_started.md](https://github.com/colmap/glomap/blob/main/docs/getting_started.md)
- Global mapper depends on good focal-length priors; with unreliable intrinsics run `view_graph_calibrator` first (optional but recommended; it modifies the database in place, so run on a copy); global mapper "can be faster on large datasets with good matching graphs, but it is less robust to matching outliers" — [COLMAP FAQ](https://colmap.github.io/faq.html)
- InstantSfM (MEASURED by authors, GPU runtime, 1DSfM): Alamo COLMAP 12855.4 s / GLOMAP 1599.5 s / InstantSfM 597.0 s; Madrid_Metropolis 1661.5 / 440.7 / 222.9; Union_Square 4696.7 / 966.4 / 571.3. Hardware: Xeon Platinum 8480C + NVIDIA H200 with 140.4 GB — [InstantSfM paper](https://arxiv.org/html/2510.13310v1)
- InstantSfM accuracy: Tanks and Temples AUC@3 51.28 vs COLMAP 55.00 / GLOMAP 55.38 (worse); MipNeRF360 PSNR 28.43 vs 26.92 / 27.24 (better); authors attribute the T&T gap to intrinsics-translation ambiguity; triangulation not yet GPU-accelerated; own peak GPU memory not reported; abstract CLAIM "up to ~40x over COLMAP" — [InstantSfM paper](https://arxiv.org/html/2510.13310v1)
- InstantSfM code is public; needs NVIDIA GPU, COLMAP on PATH for default features, separate `bae` package, cuDSS headers; tested Ubuntu 20.04 / CUDA 12.1 / PyTorch 2.3.1; "still under active development"; licence type not visible on the page (LICENSE file exists); paper promised "a community friendly license" — [InstantSfM repository](https://github.com/cre185/InstantSfM); [InstantSfM paper](https://arxiv.org/html/2510.13310v1)
- FastMap: global SfM using only first-order optimisers; abstract CLAIM "up to 10 times faster than COLMAP and GLOMAP with GPU acceleration" with comparable pose accuracy (an earlier version of the abstract said one to two orders of magnitude) — [FastMap arXiv 2505.04612](https://arxiv.org/abs/2505.04612)
- FastMap code: MIT licence; Linux only; single GPU; input is a COLMAP database with matches; output COLMAP `sparse/0`; unregistered images are dropped; stated limits: works best on high-quality dense-coverage captures, "does not carefully handle outlier matches", less robust than COLMAP/GLOMAP with sparse coverage, low-quality matching or degenerate motion, "prone to catastrophic failures" there; GPU memory not stated — [FastMap repository](https://github.com/pals-ttic/fastmap)
- VGGSfM runs out of memory on a 24-GB RTX 4090 beyond ~50 images (InstantSfM authors); a community repo reports ~90 images on an RTX 4090 for VGGSfM and trouble beyond ~30 for MASt3R (informal) — [InstantSfM paper](https://arxiv.org/html/2510.13310v1); [Radiance-Fields-from-VGGSfM-Mast3r](https://github.com/hwanhuh/Radiance-Fields-from-VGGSfM-Mast3r)
- Light3R-SfM authors: their method is less accurate than GLOMAP, COLMAP and MASt3R-SfM, especially above 200 images; in their largest-subset table row MASt3R-SfM runtime ~2723 vs Light3R-SfM ~63 (units not visible in the excerpt) — [Light3R-SfM, CVPR 2025](https://arxiv.org/pdf/2501.14914)
- MASt3R (and thus MASt3R-SfM, which lives in the naver/mast3r repo) is CC BY-NC-SA 4.0, checkpoints governed by DUSt3R licence terms plus training-dataset licences — [mast3r LICENSE](https://github.com/naver/mast3r/blob/main/LICENSE); [mast3r CHECKPOINTS_NOTICE](https://github.com/naver/mast3r/blob/mast3r_sfm/CHECKPOINTS_NOTICE)
- GLOMAP paper also compares against OpenMVG and Theia and reports outperforming both while matching COLMAP on ETH3D (SNIPPET) — [GLOMAP paper v2](https://arxiv.org/html/2407.20219v2)

### Inferences
- Our 45-68 min for "two global runs + completion" on 1000-2000 images is in the range of GLOMAP's published IMC-2023 average (497 s) scaled up; the documented levers that have NOT necessarily been used yet are `max_num_tracks` (~1000 x number of images) and iteration caps for global positioning/BA. Expected gain unknown; plausible 1.5-3x on the BA part because BA cost grows with point count. Effort: one option, one A/B run; gate with the existing photo F1 / GPS / plumb checks.
- Skipping view graph calibration is only safe with trustworthy focal lengths (EXIF or previously calibrated cameras). For internet photos without EXIF this is the wrong place to save time; the project memory already records a false rejection of the global mapper due to missing focal lengths, consistent with the FAQ statement.
- 4.2.0's match-count weighting in rotation averaging and multi-component output directly address the two failure modes we see on towers (front/back confusion, disconnected sides). Doppelgangers-style pair filtering is the authors' own recommended remedy for symmetry.
- FastMap (MIT) is trivially cheap to try because it reads the COLMAP database we already have (effort: 1-2 h), but by its own description it is unsuited to internet photos; reasonable only as a fast pre-check on our dense phone/video subsets. InstantSfM is the more interesting candidate for robustness, but 8-GB feasibility is unproven (measured on 140 GB) and the licence must be read from the LICENSE file before any use.
- MASt3R-SfM, VGGSfM, Light3R-SfM and Detector-free SfM are not options for 1000+ unordered images on 8 GB: either non-commercial licence (MASt3R family), memory (VGGSfM), or accuracy above 200 images (Light3R-SfM).

### Gaps
- GLOMAP paper hardware not retrieved; no per-step time breakdown (rotation averaging vs global positioning vs BA) found.
- Could not confirm a `skip_view_graph_calibration` flag name in COLMAP 4.x global_mapper; check `colmap global_mapper --help` locally.
- Licences not verified: InstantSfM (LICENSE file not opened), VGGSfM, Light3R-SfM (code release status unknown), Detector-free SfM, Theia (commonly BSD - unverified here). OpenMVG is MPL-2.0 per secondary source only — [libhunt](https://www.libhunt.com/compare-openMVG-vs-ODM).
- Image counts for the three 1DSfM scenes in the InstantSfM table are not given in the paper text retrieved; FastMap repository gives no runtime table or VRAM figure.

## 4. Feed-forward 3D models: licences (code AND weights), VRAM, use as initialisation

### Takeaway
Commercially usable as of November 2026 (verified on primary pages): VGGT code + the separate gated checkpoint `VGGT-1B-Commercial` (custom licence, military use excluded), MapAnything code + `facebook/map-anything-apache` / `-apache-v1` (Apache-2.0), Depth Anything 3 only in the BASE/SMALL (and reportedly METRIC-LARGE/MONO-LARGE) checkpoints (Apache-2.0), and MoGe/MoGe-2 (MIT code; weights described as MIT but queried in an open issue). NOT usable for sold output: DUSt3R, MASt3R, MASt3R-SfM, MASt3R-SLAM (via MASt3R weights), original VGGT-1B, default MapAnything, DA3 Giant/Large/Nested, Pi3 weights, Fast3R, CUT3R.

### Cited Findings
- VGGT: on 29 July 2025 the repository licence was changed to permit commercial use excluding military applications ("All code in this repository is now under a commercial-use-friendly license"); "only the newly released checkpoint VGGT-1B-Commercial is licensed for commercial usage"; the original VGGT-1B stays non-commercial; access to the checkpoint requires an automatically processed application form — [VGGT repository](https://github.com/facebookresearch/vggt)
- `facebook/VGGT-1B-Commercial` on Hugging Face is gated; licence tag "vggt-aup-license"; reported Co3D AUC@30 90.37 vs 89.98 for the original (SNIPPET) — [HF VGGT-1B-Commercial](https://huggingface.co/facebook/VGGT-1B-Commercial)
- VGGT -> COLMAP: `python demo_colmap.py --scene_dir=...` writes `sparse/cameras.bin, images.bin, points3D.bin`; `--use_ba` adds bundle adjustment; reduced settings `--max_query_pts=2048 --query_frame_num=5` (defaults 4096 and 8) with a robustness warning; output usable directly with gsplat (1.3.0 recommended); a 15 May 2026 update states that after a fix VGGT runs on "roughly 2-3x more input frames" with the same GPU memory; the front page gives no VRAM table or frame maximum — [VGGT repository](https://github.com/facebookresearch/vggt)
- MapAnything: code Apache-2.0; checkpoints `facebook/map-anything` and `facebook/map-anything-v1` are CC BY-NC 4.0; `facebook/map-anything-apache` and `facebook/map-anything-apache-v1` are Apache-2.0; variants share the API and differ in training-data composition — [MapAnything repository](https://github.com/facebookresearch/map-anything); [HF map-anything-apache](https://huggingface.co/facebook/map-anything-apache)
- Caveat: a commit in the history of the Apache model card shows a line `license: cc-by-nc-4.0`; current card reads apache-2.0 (SNIPPET; state of history unclear) — [HF commit](https://huggingface.co/facebook/map-anything-apache/commit/0e6deca2ea78d673b504d270e53161a95f0bad98)
- MapAnything memory: `memory_efficient_inference=True` supports "up to 2000 views on 140 GB"; `minibatch_size` auto from free GPU memory, 1 = lowest; bf16 mixed precision; no figures for small GPUs — [MapAnything repository](https://github.com/facebookresearch/map-anything)
- MapAnything and COLMAP: `scripts/demo_colmap.py` exports COLMAP format (flag `--apache` selects the Apache model); `scripts/demo_inference_on_colmap_outputs.py` runs it in MVS mode on COLMAP calibration + poses as input priors (`--ignore_calibration_inputs`, `--ignore_pose_inputs` to disable); no bundle adjustment of its own is described; wrappers for external models (VGGT, DUSt3R, MASt3R, MUSt3R, Pi3-X, Pow3R, DA3, MoGe) are included and keep their own licences — [MapAnything repository](https://github.com/facebookresearch/map-anything)
- Depth Anything 3: CC BY-NC 4.0 for DA3NESTED-GIANT-LARGE, DA3-GIANT, DA3-GIANT-1.1, DA3-LARGE, DA3-LARGE-1.1; Apache-2.0 for DA3-BASE and DA3-SMALL — [PyPI depth-anything-3](https://pypi.org/project/depth-anything-3/); [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- DA3METRIC-LARGE and DA3MONO-LARGE listed as Apache-2.0 on a mirror / third-party ONNX export (secondary sources; verify on the official model cards) — [Gitee mirror](https://gitee.com/ayang2019/Depth-Anything-v3); [HF da3metric-large-onnx](https://huggingface.co/Heliosoph/da3metric-large-onnx)
- DUSt3R: CC BY-NC-SA 4.0, non-commercial only; MASt3R: CC BY-NC-SA 4.0; checkpoints additionally bound by training-dataset licences — [DUSt3R repository](https://github.com/naver/dust3r); [mast3r LICENSE](https://github.com/naver/mast3r/blob/main/LICENSE); [mast3r CHECKPOINTS_NOTICE](https://github.com/naver/mast3r/blob/mast3r_sfm/CHECKPOINTS_NOTICE)
- MASt3R-SLAM: own LICENSE.md; README points to a separate notice for checkpoint licences; parts of the GPU Gauss-Newton kernels derive from DROID-SLAM and follow its licence; depends on MASt3R weights (CC BY-NC-SA) — [MASt3R-SLAM repository](https://github.com/rmurai0610/MASt3R-SLAM); [Dependencies.md](https://github.com/rmurai0610/MASt3R-SLAM/blob/main/Dependencies.md)
- Pi3 (π³, ICLR 2026): code BSD-3-Clause, weights CC BY-NC 4.0 (non-commercial research/education; restriction must be kept on redistribution); the authors' HF card says to contact them for commercial use — [Pi3 repository](https://github.com/yyfz/Pi3); [HF Pi3](https://huggingface.co/yyfz233/Pi3)
- Fast3R: code and models under the FAIR NC Research License (non-commercial); repository archived — [Fast3R LICENSE](https://github.com/facebookresearch/fast3r/blob/main/LICENSE); [Fast3R repository](https://github.com/facebookresearch/fast3r)
- CUT3R: stated as CC BY-NC-SA 4.0 by NVIDIA's derivative repo and by a comparison list (secondary) — [NVlabs/scal3r](https://github.com/NVlabs/scal3r); [awesome-3D-vision](https://github.com/gmberton/awesome-3D-vision)
- MoGe / MoGe-2: code MIT except bundled DINOv2 code (Apache-2.0); third-party model cards say code and weights are MIT; an open issue (July 2026) notes the repo does not explicitly state the weights' licence — [MoGe repository](https://github.com/microsoft/MoGe); [MoGe issue 98](https://github.com/microsoft/MoGe/issues/98)

### Inferences
- Practical commercial shortlist for "initialisation or cross-check": (1) MapAnything Apache with COLMAP poses as priors = dense metric depth per image as an independent cross-check of PatchMatch depth, no new SfM needed; (2) VGGT-1B-Commercial on subsets (per wall / per side) with `demo_colmap.py --use_ba` as a second opinion on relative camera pose where the global mapper splits front/back; (3) DA3-BASE or MoGe-2 as monocular/any-view depth prior for the wall-relief step (`relief_aus_fotos_mono.py` type use).
- 8-GB feasibility is NOT documented by any of the primary pages. Indirect scale: MapAnything quotes 2000 views on 140 GB (~70 MB/view in memory-efficient mode, so 50-100 views would be 3.5-7 GB if scaling were linear - an extrapolation, not a measurement); VGGT's own 2026 fix claims 2-3x more frames per GB. Plan on 30-60 frames at reduced resolution (518 px class) on 8 GB and test with a 20-frame dummy first.
- Feed-forward output is low resolution (roughly 0.5 megapixel class inputs) and therefore cannot replace 1-cm facade images or edge triangulation; under the project's core method it can only serve as position veto / cross-check, like the dense cloud.
- The VGGT commercial licence is a custom acceptable-use licence, not Apache; the military exclusion and any attribution duties must be read in the repo LICENSE before first sale. For MapAnything, pin the exact Hugging Face revision whose card reads apache-2.0 and archive the card, because of the cc-by-nc commit seen in history.
- MoGe-2 weights: treat as "probably MIT, unconfirmed by maintainers" until issue 98 is answered.

### Gaps
- No VRAM-vs-frames table retrieved for VGGT (the README table was not on the fetched page), MapAnything, DA3 or Pi3 on 8-GB cards.
- Spann3R licence: LICENSE file exists but text not retrieved — [Spann3R repository](https://github.com/HengyiWang/spann3r). CUT3R upstream LICENSE text not opened (secondary sources only). MASt3R-SLAM LICENSE.md text not retrieved.
- No published study found that quantifies COLMAP bundle adjustment initialised from VGGT/MapAnything/DA3 versus plain GLOMAP on 1000+ unordered images; only the demo scripts exist.
- "VGGT-Omega" and "Pi3-X" are named as integrated external models on the MapAnything page; their licences were not researched.
- Exact text of the VGGT licence (attribution, redistribution of outputs) not read.

## 5. Comparable open pipelines: what they do differently

### Takeaway
No 2023-2026 benchmark comparing these pipelines specifically on building facades or phototourism data was found beyond the GLOMAP paper itself (IMC 2023); available cross-tool comparisons are older and on other subjects. The licence picture is clearer than the performance picture: OpenSfM BSD-2, OpenMVG MPL-2.0, OpenMVS and ODM AGPL-3.0, RealityScan free below 1 million USD annual gross revenue.

### Cited Findings
- RealityScan (desktop, renamed from RealityCapture with 2.0 in June 2025): free for students, educators, and individuals and companies with annual gross revenue below 1 million USD; above that 1250 USD per seat per year (1850 USD in a bundle with Unreal Engine and Twinmotion); 2.0 requires accepting a new EULA and download through the Epic Games Launcher or Dev Portal — [RealityScan licence page](https://www.realityscan.com/license); [RealityScan download](https://www.realityscan.com/en-US/download); [RealityScan 2.0 announcement](https://www.realityscan.com/news/realityscan-20-new-release-brings-powerful-new-features-to-a-rebranded-realitycapture)
- ODM is AGPLv3 and uses OpenSfM for features/matching/SfM and OpenMVS for the dense cloud — [Wikipedia OpenDroneMap](https://en.wikipedia.org/wiki/OpenDroneMap)
- OpenSfM: BSD 2-clause; OpenMVG: MPL-2.0 (secondary source) — [libhunt comparison](https://www.libhunt.com/compare-OpenSfM-vs-openMVG)
- OpenMVS: AGPL-3.0; includes mesh reconstruction, refinement and texturing, and a scalable pipeline script that splits large scenes — [OpenMVS repository](https://github.com/cdcseacave/openMVS)
- GLOMAP paper's pipeline uses COLMAP RootSIFT + bag-of-words retrieval for pairing, i.e. the published numbers are for retrieval-based pairing on unordered sets — [GLOMAP paper](https://arxiv.org/html/2407.20219)
- IMC 2023 (phototourism-type) result: GLOMAP 497.3 s and AUC@10 79.4 vs COLMAP 4051.0 s and 75.1 — [GLOMAP paper](https://arxiv.org/html/2407.20219)
- Older comparison (maize roots, 2023): COLMAP produced on average 94x the points of Meshroom but took ~29x longer than the fastest pipeline (OpenMVG+MVE) — [Liu et al. 2023, Plant Phenome Journal](https://acsess.onlinelibrary.wiley.com/doi/full/10.1002/ppj2.20068)
- Older comparison (rebar progress, ISPRS 2022): RealityCapture, Meshroom and Photomodeler had the lowest computation time including meshing — [ISPRS Archives 2022](https://isprs-archives.copernicus.org/articles/XLIII-B2-2022/141/2022/isprs-archives-XLIII-B2-2022-141-2022.pdf)
- VGGT and MapAnything COLMAP exports are documented as direct input for gsplat (1.3.0) — [VGGT repository](https://github.com/facebookresearch/vggt); [MapAnything repository](https://github.com/facebookresearch/map-anything)

### Inferences
- Structural differences worth copying are in pairing rather than mapping: hloc-style pipelines pair by global-descriptor retrieval (top-k per image) instead of exhaustive/vocab-tree matching, and use learned features; our chain already uses ALIKED+LightGlue, so the remaining difference is the retrieval step and pair verification against symmetric structure (Doppelgangers-type classifier, as the GLOMAP authors suggest).
- RealityScan is a legitimate free cross-check for a small business under the 1 million USD threshold (whether measured per calendar year or trailing 12 months is worded differently across pages - read the EULA), but it is closed source and Windows-centric, so only a manual comparison tool, not a pipeline component on our Linux machine.
- AGPL tools (OpenMVS, ODM) are usable for producing sold models; the constraint is on distributing or hosting modified software, which does not apply while the pipeline stays in-house (legal reading, unverified).
- nerfstudio/gsplat pipelines consume COLMAP poses and produce view-synthesis representations, not metric edges; they do not replace the facade-image/edge method but could give a quick visual plausibility check of poses.

### Gaps
- No readable 2023-2026 source for Meshroom/AliceVision 2025 release features and licence (commonly MPL-2.0 - unverified here), hloc licence (commonly Apache-2.0 - unverified here), nerfstudio/gsplat licences (commonly Apache-2.0 - unverified here).
- No published facade- or phototourism-specific comparison across hloc+COLMAP, OpenSfM, Meshroom, OpenMVG+OpenMVS, ODM and RealityScan found; one web page with facade timings was judged unreliable (no sources) and is not reported.
- Differences in texturing between the pipelines (AliceVision texturing, OpenMVS TextureMesh, ODM mvs-texturing) were not researched to source level.
- RealityScan EULA text itself not opened; threshold definition (gross revenue period) and terms on output ownership unverified.

## 6. Mesh/texture output for inspection

### Takeaway
For closing holes in an inspection view the lowest-effort, permissive option is screened Poisson on the fused cloud via Open3D (MIT) or COLMAP's built-in `poisson_mesher`; COLMAP also ships `delaunay_mesher`, a mesh simplifier and a mesh texturer, while OpenMVS ReconstructMesh/TextureMesh are AGPL-3.0.

### Cited Findings
- COLMAP dense workflow optionally ends with `poisson_mesher` / `delaunay_mesher`; the automatic workspace writes `dense/0/fused.ply`, `meshed-poisson.ply`, `meshed-delaunay.ply` and `meshed-advancing-front.ply`; `mesh_simplifier` (quadric error decimation) and `mesh_texturer` (texture atlas, per-face UVs) exist; meshes must be viewed in external software — [COLMAP tutorial](https://colmap.github.io/tutorial.html)
- 4.2.1 fixed unbounded memory growth in Delaunay meshing (relevant with 15 GB RAM) — [COLMAP releases](https://github.com/colmap/colmap/releases)
- Open3D is MIT-licensed; its Poisson reconstruction code is a fork of Kazhdan's PoissonRecon, also MIT — [Open3D](https://www.open3d.org/); [Open3D-PoissonRecon](https://github.com/isl-org/Open3D-PoissonRecon)
- CGAL's Poisson surface reconstruction package is GPL — [CGAL manual](https://doc.cgal.org/latest/Poisson_surface_reconstruction_3/group__PkgPoissonSurfaceReconstruction3Ref.html)
- OpenMVS (mesh reconstruction, refinement, texturing) is AGPL-3.0 — [OpenMVS repository](https://github.com/cdcseacave/openMVS)

### Inferences
- Poisson closes holes by construction, which is what the inspection view needs, but it also invents surface where no photo saw anything; for our rule "never invent an unseen side" the viewer mesh should be trimmed by point density (Open3D returns per-vertex densities) and labelled as inspection aid, never used as a source for form.
- COLMAP's Delaunay mesher uses visibility from the fusion step and respects free space better than Poisson (less ballooning at open facades), but binaries with it depend on CGAL, whose relevant packages are GPL - again only a distribution concern.
- Expected cost on a 1-2 million point cloud: minutes on CPU for Poisson depth 9-10 (assumption from general experience, not a cited number). Effort: a few lines with Open3D in the existing venv.

### Gaps
- No timing or quality numbers found for Open3D Poisson vs COLMAP Delaunay vs OpenMVS ReconstructMesh on building data.
- COLMAP's CGAL requirement and licence implications for `delaunay_mesher`, and the `fused.ply.vis` input requirement, are not stated on the tutorial page fetched; verify in the install docs.
- Licence and speed of COLMAP's new `mesh_texturer` vs OpenMVS TextureMesh / mvs-texturing not researched.
