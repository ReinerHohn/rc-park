# Image selection and pair generation for SfM on mixed image sets (internet photos, phone photos, video frames) - state Nov 2026

Method note: licenses marked "(LICENSE file read 19.11.2026)" were read directly from the repository's LICENSE file via raw.githubusercontent.com or the GitHub API on that day; the URL given is the repository. Everything else is from the cited page. Items I could not source are in "Gaps", not in "Cited Findings".

## 1. Global descriptors for retrieval (pair list instead of near-exhaustive matching)

### Takeaway
Retrieval-based pair lists are the standard in every reference pipeline (hloc: top 20 for SfM mapping; COLMAP vocab tree: top 100; IMC 2025 winner: top 10-25 per retrieval method), and the commercially clean candidates are MegaLoc, BoQ, CosPlace, EigenPlaces (all MIT) and AnyLoc (BSD-3); SALAD is GPL-3.0, MixVPR and the common PyTorch NetVLAD port have no license file. A controlled 2024-2026 ablation "top-k versus exhaustive on reconstruction completeness" for landmark photo collections was NOT found; the strongest evidence is challenge practice (IMC 2025), where VPR-type global descriptors were consistently used with loose thresholds/large k and were beaten by MASt3R-ASMK (non-commercial).

### Cited Findings
Licenses (code repository; weights are normally distributed from the same repo/torch.hub without a separate license statement):
- MegaLoc: MIT (LICENSE file read 19.11.2026), descriptor dimension 8448, evaluation at 322x322 px, loaded with `torch.hub.load("gmberton/MegaLoc", "get_trained_model")`; weights on Hugging Face `gberton/MegaLoc`, no separate weights license stated on the repo page — [MegaLoc repo](https://github.com/gmberton/MegaLoc)
- MegaLoc paper (Berton & Masone, Feb 2025) claims state of the art "on most VPR datasets, including indoor and outdoor ones"; framed as one retrieval model for localization/VPR/landmark retrieval — [arXiv 2502.17237](https://arxiv.org/abs/2502.17237v1)
- CosPlace: MIT; EigenPlaces: MIT; BoQ (Bag-of-Queries): MIT; AnyLoc: BSD-3-Clause; SALAD (DINOv2-SALAD): GPL-3.0; AP-GeM/DIR (naver/deep-image-retrieval): BSD-3-Clause (all GitHub API license field, read 19.11.2026) — [CosPlace](https://github.com/gmberton/CosPlace), [EigenPlaces](https://github.com/gmberton/EigenPlaces), [BoQ](https://github.com/amaralibey/Bag-of-Queries), [AnyLoc](https://github.com/AnyLoc/AnyLoc), [SALAD](https://github.com/serizba/salad), [deep-image-retrieval](https://github.com/naver/deep-image-retrieval)
- MixVPR: no LICENSE file found in the repository (checked main/master, 19.11.2026) -> legally "all rights reserved" by default; Nanne/pytorch-NetVlad: also no LICENSE file — [MixVPR](https://github.com/amaralibey/MixVPR), [pytorch-NetVlad](https://github.com/Nanne/pytorch-NetVlad)
- A single MIT-licensed wrapper exposes NetVLAD, AP-GeM, SFRS, CosPlace, Conv-AP, MixVPR, EigenPlaces, AnyLoc, SALAD and others by changing one parameter (each wrapped model keeps its own license) — [VPR-methods-evaluation](https://github.com/gmberton/VPR-methods-evaluation)

Neighbours per image in reference pipelines:
- hloc Aachen pipeline defaults: `num_covis = 20` pairs per image for SfM triangulation/mapping, `num_loc = 50` retrieved images per query for localization; retrieval NetVLAD, features SuperPoint (aachen), matcher SuperGlue — [hloc Aachen pipeline.py](https://raw.githubusercontent.com/cvg/Hierarchical-Localization/master/hloc/pipelines/Aachen/pipeline.py)
- hloc benchmark settings: Aachen "NetVLAD top 50" with SuperPoint+SuperGlue, "NetVLAD top 30" for nearest-neighbour matchers; InLoc top 40 / top 20 — [hloc README](https://github.com/cvg/Hierarchical-Localization)
- hloc supports NetVLAD, AP-GeM/DIR, OpenIBL, MegaLoc (and CosPlace since v1.4) as retrieval front ends; license of hloc itself Apache-2.0 — [hloc README](https://github.com/cvg/Hierarchical-Localization)
- COLMAP vocabulary-tree matching uses top-100 candidates by default (as reported by a paper that ran COLMAP on 1DSfM with different retrievers; that learned retriever gave about 10 % fewer pairs than BoW at comparable results) — [Matchable Image Retrieval, arXiv 1811.10343](https://arxiv.org/html/1811.10343)
- IMC 2025 1st place (MASt3R-based): retrieval with MASt3R-ASMK (n=10, k=25) plus MASt3R-SPoC top-k=10; exhaustive MASt3R matching was too expensive, so retrieval builds the shortlist; MASt3R at size 512 — [Kaggle 1st place write-up](https://www.kaggle.com/competitions/image-matching-challenge-2025/writeups/ns64-1st-place-solution)
- IMC 2025 overview: most teams used DINOv2-based global retrieval "with fairly loose settings (lower similarity thresholds, larger top-k) to favor recall"; 5th place reported MASt3R-ASMK retrieval as much stronger than DINOv2 and other models; 2nd and 6th place instead used exhaustive pairs followed by progressive filtering by inlier count of a lightweight matcher; 4th place trained a same-scene classifier, which over-filtered and had to be backed up with NetVLAD pairs; 10th place adapted top-k dynamically from the DINOv2 score distribution — [Zenn summary of IMC 2025 top solutions](https://zenn.dev/yume_neko/articles/bee802ebf8b4d0)
- IMC 2025 8th place: CLIP global features + cosine similarity threshold for candidate pairs, public code — [yangyefd/IMC2025](https://github.com/yangyefd/IMC2025)
- MASt3R-SfM builds a sparse scene graph from ASMK retrieval over frozen MASt3R encoder tokens (farthest-point-sampled key images + nearest-neighbour connections) instead of a complete graph, and has a scene-graph ablation (Table 4) — [MASt3R-SfM, arXiv 2409.19152](https://arxiv.org/pdf/2409.19152)
- MASt3R and DUSt3R (code and checkpoints): CC BY-NC-SA 4.0, i.e. NON-COMMERCIAL (LICENSE files read 19.11.2026) — [naver/mast3r](https://github.com/naver/mast3r), [naver/dust3r](https://github.com/naver/dust3r)
- Trade-off statement from a 2025 pair-retrieval benchmark (UAV images): "A large retrieval number decreases the efficiency of match pair retrieval and subsequent feature matching, while a small retrieval number may lead to the loss of too many correct matching pairs" and failing reconstruction — [UAVPairs, arXiv 2505.22098](https://arxiv.org/html/2505.22098)
- A global-SfM system with deep front end combines NetVLAD top-k pairs with additional sequential pairs for ordered data — [Distributed Global SfM with a Deep Front-End, arXiv 2311.18801](https://arxiv.org/pdf/2311.18801)

### Inferences
- Pair budget: 2000 images x top-20..50 gives at most 40,000-100,000 directed pairs (fewer after removing symmetric duplicates) versus today's 293,000 -> a 3-7x reduction in matching work is plausible; not measured on this data.
- Commercially safest first try: MegaLoc (MIT, DINOv2 backbone under Apache-2.0, already wired into hloc) with top-k 30-50 plus sequential neighbours for video frames. MegaLoc at 322 px with a ViT-B backbone should fit easily in 8 GB (inference only, batch of a few images); no GPU-memory figure is published, so this is an estimate.
- Because the winning IMC teams combined two retrieval signals or used exhaustive-then-filter, a cheap safety net is plausible: retrieval top-k UNION (a) temporal neighbours inside each video, (b) COLMAP transitive matching afterwards, (c) a low-resolution cheap matcher pass for images that ended up with few verified pairs.
- VPR descriptors are trained on street-level place recognition; black-and-white historic photos and drone views are out of that distribution. The IMC observation (loose thresholds, larger k) suggests giving such images a larger k (e.g. 2-3x) than video frames. Plausible, not demonstrated.
- MASt3R-ASMK is the best demonstrated retrieval for this kind of data but is excluded for sold results (NC license).

### Gaps
- No published recall numbers on landmark/phototourism data were retrieved for the individual models (NetVLAD, AP-GeM, CosPlace, EigenPlaces, MixVPR, SALAD, AnyLoc, BoQ, MegaLoc); the MegaLoc paper has such tables but I did not read them in this pass. Do not quote numbers without checking arXiv 2502.17237.
- No explicit license statement for pretrained WEIGHTS separate from the code license was found for MegaLoc, CosPlace, EigenPlaces, BoQ, AnyLoc; training data of these models (e.g. street-view datasets) may carry their own terms - not examined.
- License of the original NetVLAD weights used by hloc, and of OpenIBL, not checked.
- No controlled 2024-2026 study varying k against exhaustive matching and measuring registered images/completeness on internet photo collections was found.
- GPU memory per model: no published figures found.
- "Newer than MegaLoc" retrieval models (2026): not searched systematically.

## 2. What COLMAP 4.x offers natively (state per release notes up to Nov 2026)

### Takeaway
COLMAP 4.x now covers most of the wish list natively: ALIKED and LightGlue (4.0), GLOMAP as built-in global mapper (4.0), the learned LoMa extractor/matcher family (4.2.0), a descriptor-free FlexGlue matcher with a built-in covisibility rejection score (documented in the current features page), AnyCalib for intrinsics (model release Sep 2026) and a loop-detection index-distance option (4.2.0). Retrieval is still the SIFT-era vocabulary tree; there is no learned global-descriptor retrieval in COLMAP itself, so a MegaLoc/hloc pair list has to be imported as custom pairs.

### Cited Findings
- COLMAP 4.0: ALIKED extraction through ONNX, LightGlue matching for SIFT and ALIKED, integration of GLOMAP as global SfM pipeline; needs build with ONNX enabled — [radiancefields.com on COLMAP 4.0](https://radiancefields.com/colmap-4.0-introduces-major-performance-and-infrastructure-updates)
- 4.1.0 (26 Jun): exhaustive matcher accelerated via faiss `IndexIVFScalarQuantizer`; "Added support for extracting gravity pose priors from EXIF orientation tags"; "Estimate separate fx/fy in the p4pf solver"; fixes: "Fix broken integration of SIFT features with the LightGlue matcher", "Fix sequential matching hang with loop detection verification", ALIKED `min_score` with pycolmap; `GlobalMapper.keep_max_num_tracks` — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.1.1 (17 Jul): "Fix feature matching slowdown (~4-6x) caused by a process-global OpenMP critical section in RANSAC/LORANSAC" — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.2.0 (01 Sep): "Added LoMa learned feature extraction and matching through ONNX"; "Added `SequentialMatching.loop_detection_min_index_distance`" to exclude nearby frames from loop detection; "Added 6-point shared-focal and one-sided-focal relative-pose solvers"; "Refine fundamental matrices with Sampson error by default and use MSAC"; global mapper reconstructs every connected component by default; optional match-count weighting in rotation averaging — [COLMAP releases](https://github.com/colmap/colmap/releases)
- 4.2.1 (29 Sep): "Fix GPU memory leak in LoMa matching by upgrading ONNX Runtime to 1.30.0"; restores legacy bundle-adjustment behaviour in the global mapper (regression in 4.2.0); skips UNDEFINED/DEGENERATE pairs when loading the database cache — [COLMAP releases](https://github.com/colmap/colmap/releases)
- "AnyCalib model v1.0.0" (07 Sep): "Static ONNX export for COLMAP's AnyCalib camera calibration backend", "AnyCalib is licensed under Apache-2.0" — [COLMAP releases](https://github.com/colmap/colmap/releases)
- Feature types in current docs: SIFT (default), ALIKED (`aliked-n16rot`: faster, some viewpoint/rotation invariance; `aliked-n32`: more expensive), LOMA_B (256-dim, frozen DINOv2 + conv features) and LOMA_B128; matchers SIFT_BRUTEFORCE, SIFT_LIGHTGLUE, ALIKED_BRUTEFORCE, ALIKED_LIGHTGLUE, LOMA_* (B, R with rotation augmentation, L, G progressively larger/more accurate, B128 fastest), and FLEXGLUE — [COLMAP features doc](https://colmap.github.io/features.html)
- FLEXGLUE "works with keypoints from any extractor and ignores descriptors", reads the images during matching, has `--FlexGlueMatching.min_covisibility` (default 0.5; 0 disables) that rejects pairs with low covisibility score; fp16 by default on CUDA; feature cache about 4 MB per image on GPU; `num_inferences_per_gpu` (default 2) can be lowered to 1 to reduce GPU memory; no guided matching — [COLMAP features doc](https://colmap.github.io/features.html)
- "Do not mix different feature extractor types (e.g., SIFT and ALIKED) in the same database" — [COLMAP features doc](https://colmap.github.io/features.html)
- Re-matching: pairs that already have two-view geometry are skipped; to force, `database_cleaner --type two_view_geometries --type matches` — [COLMAP features doc](https://colmap.github.io/features.html)
- Matching modes: exhaustive for "up to several hundreds" of images; vocabulary tree "is the recommended matching mode for large image collections (several thousands)", with spatial re-ranking; sequential for video with vocabulary-tree loop detection every N-th image (`loop_detection_period`, `loop_detection_num_images`, `loop_detection_min_index_distance`), file names must be ordered; spatial (GPS from EXIF); transitive ("If an image A matches to an image B and B matches to C, then this matcher attempts to match A to C directly"); custom pair list or import of raw/verified matches — [COLMAP tutorial](https://colmap.github.io/tutorial.html)
- "COLMAP only matches image pairs that have not been matched previously" (pair lists can be extended incrementally) — [COLMAP tutorial](https://colmap.github.io/tutorial.html)
- FAQ: "LightGlue typically produces higher inlier ratios"; incremental mapper "is the most robust and well-tested pipeline"; global mapper faster on large sets with good matching graphs but "may be less robust to outliers in the matching"; GPU matching memory errors -> decrease `--FeatureMatching.max_num_matches` — [COLMAP FAQ](https://colmap.github.io/faq.html)
- LoMa (ECCV 2026 oral) versus ALIKED+LightGlue: +18.6 mAA on HardMatch (1000 hard internet pairs with manual ground truth), +29.5 mAA on WxBS, +21.4 on InLoc (1 m, 10 deg), +24.2 AUC on RUBIK, +12.4 mAA on IMC 2022 — [LoMa, arXiv 2604.04931](https://arxiv.org/abs/2604.04931)
- LoMa code MIT (LICENSE file read 19.11.2026); README: all code except the matcher is MIT, matcher inherits LightGlue's Apache-2.0 — [davnords/LoMa](https://github.com/davnords/LoMa)
- FlexGlue: MIT (LICENSE file read 19.11.2026) — [cvg/FlexGlue](https://github.com/cvg/FlexGlue)
- ALIKED: BSD-3-Clause; LightGlue code and its pretrained weights: Apache-2.0 (SuperPoint variant excluded) — [Shiaoming/ALIKED](https://github.com/Shiaoming/ALIKED), [cvg/LightGlue](https://github.com/cvg/lightglue)
- GLOMAP standalone repository: BSD-style ETH license (LICENSE file read 19.11.2026) — [colmap/glomap](https://github.com/colmap/glomap)

### Inferences
- The project's own mapper build "4.3.dev" and pycolmap 4.2.1 (per project notes) already contain LoMa and (per current docs) FlexGlue; trying `LOMA_B` + `LOMA_L/G` or `FLEXGLUE` on the existing ALIKED keypoints is a configuration change, not an integration project. The WxBS gain (+29.5 mAA) is the benchmark most relevant to era/illumination change, so LoMa is the most promising commercially usable upgrade for historic-vs-modern pairs. Demonstrated on benchmarks, not on this data.
- FlexGlue's `min_covisibility` is effectively a learned pair filter inside COLMAP: a generous retrieval list (large k) can be pruned cheaply before geometric verification. Plausible use, not benchmarked here.
- 4.1.1's RANSAC fix (4-6x matching slowdown) and 4.2.1's LoMa memory-leak fix mean versions before these should not be used for timing comparisons.
- `loop_detection_min_index_distance` (4.2.0) addresses exactly the "key frames matched against everything" pattern: sequential overlap for neighbours, retrieval only for far frames.

### Gaps
- Exact release that introduced FlexGlue in COLMAP (not in the release notes captured up to 4.2.1; documented on the live features page, so probably in the development branch/4.3) - not verified.
- Defaults of vocab-tree `num_nearest_neighbors`, `loop_detection_num_images`, ALIKED `max_num_features` were not shown on the pages fetched (only the secondary "top-100 default" statement above).
- Licenses of the ONNX model files that COLMAP auto-downloads (ALIKED, LightGlue, LoMa, FlexGlue exports) are not stated in the COLMAP docs/FAQ; only the upstream repo licenses above were verified. LoMa's training-data mixture and any restriction following from it were not examined; one third-party Hugging Face card (fastforks/loma) lists LoMa-B weights as MIT with commercial use allowed, which is second-hand.
- GPU memory of LoMa L/G matchers on 8 GB: no figures found.
- 2025 release notes (3.12/3.13/4.0 details) were on later pages of the release list and not read.

## 3. hloc (Hierarchical-Localization) as reference pipeline

### Takeaway
hloc is Apache-2.0 and remains the reference for "retrieval top-k -> learned features -> learned matcher -> COLMAP/pycolmap"; its own defaults are 20 retrieved pairs per image for mapping and 50 for localization. Its historical default feature (SuperPoint + SuperGlue) is not commercially usable; the clean substitution is ALIKED or DISK + LightGlue.

### Cited Findings
- License Apache-2.0; supported retrieval: NetVLAD, AP-GeM/DIR, OpenIBL, MegaLoc (CosPlace added in v1.4); local features SuperPoint, DISK, D2-Net, SIFT, R2D2 (+SOSNet, HardNet); matchers SuperGlue, LightGlue, NN with ratio/distance/mutual check, AdaLAM; dense matching with LoFTR — [hloc README](https://github.com/cvg/Hierarchical-Localization)
- Defaults `num_covis=20`, `num_loc=50` with NetVLAD + SuperPoint + SuperGlue — [hloc Aachen pipeline.py](https://raw.githubusercontent.com/cvg/Hierarchical-Localization/master/hloc/pipelines/Aachen/pipeline.py)
- SuperPoint (Magic Leap) pretrained network: licensed only for non-commercial research by academic/non-profit organisations — [SuperPointPretrainedNetwork LICENSE](https://github.com/magicleap/SuperPointPretrainedNetwork/blob/master/LICENSE)
- LightGlue README: "The pre-trained weights of LightGlue and the code provided in this repository are released under the Apache-2.0 license. DISK follows this license as well but SuperPoint follows a different, restrictive license (this includes its pre-trained weights and its inference file)" — [cvg/LightGlue](https://github.com/cvg/lightglue)
- rpautrat/SuperPoint is an MIT-licensed reimplementation with its own retrained weights usable with a PyTorch model file (LICENSE file read 19.11.2026) — [rpautrat/SuperPoint](https://github.com/rpautrat/SuperPoint)
- deep-image-matching (3DOM-FBK) is a BSD-3 toolbox wrapping many extractors/matchers for multi-view SfM with COLMAP export; its license explicitly does not cover the individual wrapped features and matchers — [deep-image-matching](https://github.com/3DOM-FBK/deep-image-matching)

### Inferences
- For internet-photo collections with hloc: `pairs_from_retrieval` with MegaLoc, num_matched 20-50, ALIKED/DISK + LightGlue, then pycolmap. The pair file can equally be fed to COLMAP's custom-pair matcher, so hloc is needed only for the retrieval step.
- LightGlue-for-SuperPoint weights were trained against the original SuperPoint; using them with the MIT reimplementation's keypoints is technically possible but the quality and the legal status of the "SuperPoint variant" of LightGlue weights are both unclear - ALIKED/DISK avoid the question entirely.

### Gaps
- hloc has no documented "recommended configuration for internet photo collections" beyond the SfM notebook and the Aachen numbers; the notebooks were not read.
- Whether hloc's MegaLoc integration exposes image size/batch options was not checked.

## 4. Video keyframe selection for SfM

### Takeaway
Public, maintained tooling for geometry-aware keyframe selection is thin: simple tools use sharpness + correlation + optical flow without geometry, GRIC-based homography-versus-fundamental selection exists in Blender's libmv, and the first full offline video-SfM system with a built-in keyframing stage on top of COLMAP's global mapper is VidMap (ECCV 2026, Apache-2.0). "N sharpest frames of the whole clip" has no support in the literature; the documented criteria are overlap plus sufficient parallax, with sharpness as a local tie-breaker.

### Cited Findings
- Goal definition: selected frames must overlap enough and have enough parallax for accurate 3D point computation (frame-selection paper from ISTI-CNR/ETH group) — [CNR IRIS paper](https://iris.cnr.it/retrieve/1f18b2fb-9a78-46a1-8e1b-21666b62cedd/prod_465907-doc_191167.pdf)
- GRIC-based selection in Blender's libmv: a candidate keyframe needs a fundamental matrix that explains the motion better than a homography (F-GRIC smaller than H-GRIC) — [libmv C API in Blender source](https://demo.gitea.com/sandey/blender/src/commit/3daa153d745766d119f5095baeef55ae570aed03/extern/libmv/libmv-capi.h)
- COLMAP's own paper lists GRIC as an option to decide the geometric relation of image pairs (COLMAP itself classifies pairs via inlier ratios of H/E/F) — [Schoenberger & Frahm, CVPR 2016](https://openaccess.thecvf.com/content_cvpr_2016/papers/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.pdf)
- `njzhangyifei/keyframe`: selects SfM keyframes with sharpness, correlation and optical-flow filters in fixed order; README says it is fast but does no geometric estimation and may be inaccurate — [keyframe](https://www.github.com/njzhangyifei/keyframe)
- `morishuz/adaptive-frame-extractor`: C++ desktop tool for COLMAP/3DGS workflows that chooses keyframes from camera motion (optical flow) instead of fixed intervals — [adaptive-frame-extractor](https://github.com/morishuz/adaptive-frame-extractor)
- `davidj-brewster/video-to-keyframes`: Python library/CLI selecting keyframes from motion, quality and differential signals, with a mode that estimates parameters for a target number of keyframes — [video-to-keyframes](https://github.com/davidj-brewster/video-to-keyframes)
- VidMap (Pataki, Sarlin, Pollefeys, ECCV 2026): offline SfM for video combining temporal tracks, loop closures, metric depth and global optimization on COLMAP's global mapping; Apache-2.0; keyframing controlled by a keypoint-drift threshold (`max_normalized_keypoint_drift`, example 0.09) with a `coarse_only` option; default matcher FlexGlue, RoMaV2 selectable; needs COLMAP/pycolmap built from source (last tested commit b1972bc2); first run downloads about 9 GB of checkpoints; reported WATE-AUC 97.98 CroCoDL, 99.57 Oxford Spires, 97.93 Hilti, 89.93 LaMAR — [cvg/vidmap](https://github.com/cvg/vidmap)
- nerfstudio `ns-process-data video`: per a GitHub issue it "just randomly samples --num-frames-target images from the video" (issue requests sharpness/difference-based selection); docs rule of thumb for 360 video is about 3 frames per second of video; nerfstudio is Apache-2.0 — [nerfstudio issue 3408](https://github.com/nerfstudio-project/nerfstudio/issues/3408), [nerfstudio custom data docs](https://docs.nerf.studio/quickstart/custom_dataset.html)
- Laplacian variance: used e.g. by Nerfies to filter blurry frames (about 600 kept per capture) — [Nerfies, arXiv 2011.12948](https://arxiv.org/pdf/2011.12948)
- Laplacian-variance weakness: gets confused by bokeh/shallow depth of field (marks frames blurry although the subject is sharp) and needs a per-dataset threshold — [radiancefields.com on FocusFrameFinder](https://radiancefields.com/focusframefinder-auto-culls-blurry-images-for-nerf-datasets)
- COLMAP sequential matching with loop detection and (4.2.0) `loop_detection_min_index_distance` is the native way to match video frames without all-against-all — [COLMAP tutorial](https://colmap.github.io/tutorial.html), [COLMAP releases](https://github.com/colmap/colmap/releases)

### Inferences
- Laplacian variance is content dependent (a frame full of sky or plain plaster scores "blurry", a frame full of foliage or cobblestones scores "sharp"), so a global top-N over a whole clip concentrates the selection on textured segments and ignores coverage and baseline. Correct use is local: pick the sharpest frame inside each short window (e.g. 0.3-1 s) AFTER windows were defined by motion/parallax. This follows from the documented weaknesses above; not benchmarked.
- A practical, license-free recipe consistent with the cited criteria: (1) decode at 2-5 fps; (2) track ALIKED/KLT features from the last keyframe; (3) accept a new keyframe when median feature displacement exceeds a fraction of the image width (VidMap uses a normalized keypoint drift of 0.09 as example) or the tracked-overlap drops below about 50-70 %; (4) among neighbouring candidates take the locally sharpest; (5) reject pure-rotation/zoom segments via H-vs-F model selection (GRIC or COLMAP's own two-view config: `PLANAR_OR_PANORAMIC`); threshold values other than 0.09 are my assumption.
- Restricting extraction to segments where the object is visible: embed low-rate frames (1 fps) with the same global descriptor used for retrieval (MegaLoc) and keep only time segments whose frames have high similarity to, or verified matches with, a small set of trusted reference photos of the building; FlexGlue's covisibility score could serve as verification. This reuses components already needed; no published tool that does exactly this was found.
- VidMap is aimed at single videos/sequences; using it per clip and merging with the photo collection would be a separate integration and the 9 GB checkpoint set makes 8-GB feasibility uncertain.

### Gaps
- sharp-frames and Katna were not verified in this pass (license, method); no statement about them is made.
- Default `--num-frames-target` and default matching method of nerfstudio for video not confirmed.
- No maintained stand-alone GRIC keyframe selector for COLMAP pipelines was found; licenses of the three small GitHub tools above were not checked.
- VidMap's keyframe criterion in detail, its internal pretrained components' licenses (metric depth model, RoMaV2/DINOv3) and its GPU memory need were not established.
- No quantitative study "keyframe strategy versus SfM/MVS quality" for walking-tour or drone video was found.

## 5. Near-duplicate removal and its effect on BA/MVS

### Takeaway
No SfM-specific, quantitative source on near-duplicate removal was found in this pass; only generic tools (perceptual hash, SSIM/MSE). The related, well-evidenced problem is the opposite one - visually similar but different facades (doppelgangers) creating false pairs - for which Doppelgangers++ offers a pair classifier integrated with COLMAP and MASt3R-SfM, but its repository has no license file.

### Cited Findings
- Doppelgangers++ is a pairwise classifier that removes incorrect edges between look-alike image pairs from the match graph before SfM; authors integrate it into COLMAP and MASt3R-SfM — [Doppelgangers++, arXiv 2412.05826](https://arxiv.org/html/2412.05826v1)
- Doppelgangers++ repository: no LICENSE file found (checked 19.11.2026) — [doppelgangers-plusplus](https://github.com/RuojinCai/doppelgangers-plusplus)
- Generic near-duplicate tools: imgdupes (perceptual hashing, MIT), duplicate-image-remover (SSIM + MSE) — [imgdupes](https://github.com/knjcode/imgdupes), [duplicate-image-remover](https://github.com/EllangoK/duplicate-image-remover)
- COLMAP 4.1.0 added `GlobalMapper.keep_max_num_tracks` "to bound the number of established tracks" (a native lever against track explosion from redundant frames) — [COLMAP releases](https://github.com/colmap/colmap/releases)

### Inferences
- With 84 % video frames, near-duplicates are mostly a keyframe-selection problem: a parallax/drift criterion (section 4) removes them at the source. Zero-baseline pairs contribute many matches but no triangulation angle; they inflate matching time, track counts and BA size, and in MVS they add source views without depth information. This is standard multi-view-geometry reasoning, not a cited measurement.
- A historic four-sided gate tower is a typical doppelganger case (similar opposite facades); the project already saw north/south separation issues, so pair filtering by a covisibility/doppelganger score is more valuable than classic duplicate removal. Doppelgangers++ depends on MASt3R features (NC) and has no license -> not usable for sold results as is.
- Cheap near-duplicate test with existing components: global-descriptor cosine similarity above a high threshold AND homography inlier ratio near 1 with small displacement -> drop the blurrier image.

### Gaps
- No source quantifying the effect of near-duplicates on bundle adjustment conditioning or MVS quality was found.
- No study on internet-photo near-duplicates (re-uploads, crops of the same photograph) in SfM was found; crops of the same photo are a real risk for era-mixed sets (same negative, different scans) and produce pure-homography pairs.

## 6. Matchers robust to large appearance/era/viewpoint change (licenses, 8 GB, evidence)

### Takeaway
Commercially usable and already inside COLMAP: ALIKED+LightGlue (BSD-3 / Apache-2.0) and the stronger LoMa family (MIT/Apache-2.0; +29.5 mAA over ALIKED+LightGlue on WxBS). Dense matchers with clean code licenses are RoMa (MIT, DINOv2 Apache-2.0) and GIM (MIT); RoMa v2 is MIT but depends on DINOv3 under Meta's custom license; MASt3R/DUSt3R are CC BY-NC-SA; Efficient LoFTR and MatchAnything now carry a "Project Registration License" whose free grant is headed "Research, Educational, and Personal Use"; SuperPoint weights are non-commercial. For ground-to-aerial pairs off-the-shelf matchers largely fail unless specifically trained (AerialMegaDepth), and that fine-tuned model is MASt3R-based (NC).

### Cited Findings
Licenses (LICENSE files read 19.11.2026 unless another source is given):
- ALIKED BSD-3-Clause; LightGlue code + weights Apache-2.0; DISK Apache-2.0 (LightGlue README: "DISK follows this license as well") — [ALIKED](https://github.com/Shiaoming/ALIKED), [LightGlue](https://github.com/cvg/lightglue), [DISK](https://github.com/cvlab-epfl/disk)
- SuperPoint (Magic Leap) weights and inference file: non-commercial research only — [SuperPoint LICENSE](https://github.com/magicleap/SuperPointPretrainedNetwork/blob/master/LICENSE)
- XFeat (accelerated_features): Apache-2.0 — [verlab/accelerated_features](https://github.com/verlab/accelerated_features)
- RoMa: MIT; README: "code except DINOv2 is MIT license", DINOv2 is Apache-2.0 — [Parskatt/RoMa](https://github.com/Parskatt/roma)
- RoMa v2: MIT for own code; "All our code except DINOv3 is MIT license", "DINOv3 has a custom license" (Meta DINOv3 License, last updated 19 Aug 2025) — [Parskatt/romav2](https://github.com/Parskatt/romav2), [DINOv3 LICENSE](https://github.com/facebookresearch/dinov3)
- RoMa v2 reproduced results: MegaDepth-1500 62.8 / 76.8 / 86.5, ScanNet-1500 34.0 / 56.5 / 73.9 (three AUC thresholds, not labelled on the page) — [Parskatt/romav2](https://github.com/Parskatt/romav2)
- DKM: LICENSE states that models trained on the synthetic dataset use non-commercially licensed data and cannot be provided under MIT; only models trained on MegaDepth alone are MIT — [Parskatt/DKM](https://github.com/Parskatt/DKM)
- MASt3R, DUSt3R: CC BY-NC-SA 4.0 (NON-COMMERCIAL) — [naver/mast3r](https://github.com/naver/mast3r)
- LoFTR: Apache-2.0 — [zju3dv/LoFTR](https://github.com/zju3dv/LoFTR)
- Efficient LoFTR and MatchAnything: repository LICENSE is now "Project Registration License (PRL) v1.0, Copyright (c) 2026 ZJU3DV Group", with the permission section headed "Research, Educational, and Personal Use" — [zju3dv/EfficientLoFTR](https://github.com/zju3dv/EfficientLoFTR), [zju3dv/MatchAnything](https://github.com/zju3dv/MatchAnything); contradicted in part by the Hugging Face card of the transformers port, which lists Apache 2.0 for `matchanything_eloftr` — [HF zju-community/matchanything_eloftr](https://huggingface.co/zju-community/matchanything_eloftr)
- GIM: MIT — [xuelunshen/gim](https://github.com/xuelunshen/gim)
- OmniGlue: Apache-2.0 — [google-research/omniglue](https://github.com/google-research/omniglue)
- LoMa: MIT (matcher part Apache-2.0 from LightGlue); FlexGlue: MIT — [davnords/LoMa](https://github.com/davnords/LoMa), [cvg/FlexGlue](https://github.com/cvg/FlexGlue)
- RDD: Apache-2.0 — [xtcpete/rdd](https://github.com/xtcpete/rdd)
- VGGT: custom "VGGT License v1" (research materials with acceptable-use policy) — [facebookresearch/vggt](https://github.com/facebookresearch/vggt)

Evidence on appearance/era change:
- LoMa versus ALIKED+LightGlue: +29.5 mAA on WxBS (wide-baseline with illumination/season/sensor change), +18.6 mAA on HardMatch, +12.4 mAA on IMC 2022 — [LoMa, arXiv 2604.04931](https://arxiv.org/abs/2604.04931)
- RoMa reported a new state of the art on WxBS "where most previous methods fail" — [RoMa, arXiv 2305.15404](https://arxiv.org/html/2305.15404v2)
- Historical images: in the deep-image-matching toolbox paper (ISPRS 2024), SuperPoint+SuperGlue was the combination used on the challenging historical datasets (Bel, Opera house, Nadar portrait, Castle); "DL-based matching algorithms, such as SuperGlue and LightGlue, are effective in discriminating the valid matches even with a very difficult input" — [DIM toolbox paper](https://air.uniud.it/retrieve/2161d849-393f-4b76-b47c-9f22c1cf712f/isprs-archives-XLVIII-2-W4-2024-309-2024.pdf)
- Historical terrestrial photos with COLMAP: SuperGlue produced the only valid reconstruction for the Crowngate benchmark dataset — [Maiwald et al., IJGI 2021](https://doi.org/10.3390/ijgi10110748)
- EuroSDR TIME benchmark tests tie-point extraction on historical aerial images with hand-crafted and learned methods (LoFTR, KeyNet, D2Net, RoRD) — [EuroSDR TIME benchmark](https://www.researchgate.net/publication/360963600_THE_EUROSDR_TIME_BENCHMARK_FOR_HISTORICAL_AERIAL_IMAGES)
- Cross-modal caution: in a SAR/optical review, SuperGlue and LightGlue stayed consistent across scenes while RoMa and DKM produced more mismatches under significant feature change (different domain, indirect) — [arXiv 2502.01002](https://arxiv.org/pdf/2502.01002)
- IMC 2025: ALIKED+LightGlue remained the mainstream sparse approach; 2nd and 8th place used LightGlue retrained with GIM (with SuperPoint); 3rd place matched 4 tiles + a half-resolution copy per image (25 combinations per pair) with LightGlue; MASt3R (1st, 5th) and RDD appeared in top solutions; cropping/tiling was common except with MASt3R — [Zenn summary](https://zenn.dev/yume_neko/articles/bee802ebf8b4d0)
- IMC 2025 1st place: sparse ALIKED/SuperPoint keypoints matched through MASt3R alone were worse than including MASt3R's dense matches — [Kaggle 1st place write-up](https://www.kaggle.com/competitions/image-matching-challenge-2025/writeups/ns64-1st-place-solution)
- "No single matcher wins everywhere": MASt3R was best on some IMC scenes and worst on others — [smly talk slides](https://speakerdeck.com/smly/imc-noxi-kasugiruhua-2025)

Evidence on ground-to-aerial:
- AerialMegaDepth (CVPR 2025): off-the-shelf DUSt3R recovers only 5.20 % of ground-aerial pairs within 5 deg rotation error; fine-tuning on the hybrid MegaDepth + geospatial-mesh-render data raises this to 55.96 % (MASt3R + hybrid: 49.54 on a main metric); fine-tuned DUSt3R/MASt3R checkpoints released and compatible with MASt3R-SfM — [AerialMegaDepth, arXiv 2504.13157](https://arxiv.org/pdf/2504.13157), [project page](https://aerial-megadepth.github.io)
- aerial-megadepth repository: no LICENSE file found (19.11.2026); base models are CC BY-NC-SA — [aerial-megadepth](https://github.com/kvuong2711/aerial-megadepth)
- RDD (CVPR 2025) Air-to-Ground benchmark: RoMa 71.3 AUC@5 deg, DKM 65.0 — [RDD supplemental](https://openaccess.thecvf.com/content/CVPR2025/supplemental/Chen_RDD_Robust_Feature_CVPR_2025_supplemental.pdf)
- Newer aerial/ground/satellite benchmarks exist: Sky2Ground (MASt3R, DUSt3R, MapAnything, VGGT) and VGA (CVPR 2026) — [Sky2Ground, arXiv 2603.13740](https://arxiv.org/pdf/2603.13740), [VGA supplemental](https://openaccess.thecvf.com/content/CVPR2026/supplemental/Lin_VGA_Empowering_Aerial-Ground_CVPR_2026_supplemental.pdf)

### Inferences
- Ranking for sold results on one 8-GB GPU: (1) LoMa inside COLMAP (lowest effort, strongest demonstrated gain on WxBS-type change); (2) FlexGlue on existing keypoints; (3) RoMa (v1, MIT + DINOv2 Apache) as dense matcher only for the difficult subset - historic photos against a few best modern neighbours, aerial against street - with matches imported into COLMAP; (4) GIM-trained LightGlue weights (MIT repo) if they exist for a non-SuperPoint detector - IMC teams used the SuperPoint variant, which is blocked by the SuperPoint license.
- Dense matchers on 2000 images are only affordable on a retrieval-restricted pair list; applying them to the few hundred non-video images x top-k neighbours is a realistic budget. RoMa at its default resolution is commonly run on 8-12 GB cards; 8-GB feasibility likely needs reduced upsampling resolution/fp16 - my estimate, no cited figure.
- Tiling/cropping (IMC 3rd place) is a matcher-agnostic, license-free way to handle large focal-length/scale differences (drone overview versus telephoto detail): match the overview against tiles or a covisible crop of the detail image. Demonstrated in the challenge, cost multiplies pair time.
- For black-and-white historic photos, converting the modern images to grayscale for matching removes one domain gap at no cost (ALIKED/LoMa take RGB; SIFT is gray anyway). Plausible, not found as a benchmarked result.
- Ground-to-aerial: the only demonstrated large gains come from NC-licensed fine-tuned DUSt3R/MASt3R. Commercially clean route is indirect bridging: oblique low-altitude drone frames and walking-tour frames taken from intermediate heights connect the two sets through chains of moderate viewpoint change, so retrieval + transitive matching matters more than a special matcher. Plausible, not demonstrated.
- Efficient LoFTR / MatchAnything: treat as NOT cleared for commercial use until the PRL text has been read in full; the Apache-2.0 tag on the Hugging Face port conflicts with the 2026 repository license.
- DINOv3 license must be read before using RoMa v2 commercially; the notes above only establish that it is a custom Meta license, not what it permits.

### Gaps
- No benchmark comparing LoMa, RoMa (v1/v2), MASt3R and ALIKED+LightGlue specifically on terrestrial historic (black-and-white) versus modern photographs was found; the historic evidence is for SuperGlue-era methods.
- The LoMa abstract gives no comparison against RoMa/MASt3R and no speed/memory figures; the paper body was not read.
- GPU memory/runtime figures for RoMa, RoMa v2, GIM-DKM, MatchAnything, OmniGlue on 8 GB: none retrieved.
- Full text of PRL v1.0 (EfficientLoFTR/MatchAnything) and of the DINOv3 license not read; commercial terms unknown.
- Whether GIM publishes LightGlue weights for ALIKED/DISK (not only SuperPoint), and the license status of GIM's internet-video training data, were not checked. OmniGlue's public pipeline is built on SuperPoint + DINOv2 as far as I recall, which would import the SuperPoint restriction - not verified in this pass.
- XFeat evidence on era/viewpoint robustness not searched (a 2026 reproducibility paper, arXiv 2608.09519, exists but was not read).

## 7. Unknown intrinsics of scanned historic photos and cropped images (COLMAP/GLOMAP)

### Takeaway
COLMAP's documented handling is: one camera per image unless truly the same camera and zoom, focal from EXIF where present, otherwise the guess 1.25 x max(width, height) flagged as GUESS; the global mapper "depends on good focal length priors" and should be preceded by `view_graph_calibrator` when intrinsics are unreliable. New in 2026: 6-point shared-focal/one-sided-focal relative-pose solvers (4.2.0) and an AnyCalib single-image calibration backend (Apache-2.0) in COLMAP.

### Cited Findings
- "Without prior knowledge about the focal length, it is recommended to set the focal length to 1.25 * max(width_in_px, height_in_px)" with source GUESS; the calibration source (GUESS/EXIF/USER) tells the reconstruction whether to trust the focal length — [COLMAP tutorial](https://colmap.github.io/tutorial.html)
- Intrinsics should be shared only "if all your images were captured by the same physical camera with identical zoom factor"; COLMAP exits if one shared camera model meets differing image sizes or EXIF focal lengths; partial EXIF is completed from a camera sensor database (updated in 4.1.0) — [COLMAP tutorial](https://colmap.github.io/tutorial.html), [COLMAP releases](https://github.com/colmap/colmap/releases)
- "The global mapper depends on good focal length priors"; if intrinsics are unreliable run `view_graph_calibrator` before `global_mapper` (optional but recommended; modifies the database in place, so work on a copy); known calibration can be passed via `--ImageReader.camera_params` — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Camera model advice: start with SIMPLE_RADIAL; FULL_OPENCV only with many images sharing intrinsics — [COLMAP FAQ](https://colmap.github.io/faq.html)
- 4.2.0: "Added 6-point shared-focal and one-sided-focal relative-pose solvers"; 4.1.0: "Estimate separate fx/fy in the p4pf solver for two-focal camera models"; 4.2.1: UNDEFINED/DEGENERATE pairs no longer reach the mappers — [COLMAP releases](https://github.com/colmap/colmap/releases)
- AnyCalib model v1.0.0 published by COLMAP as static ONNX export "for COLMAP's AnyCalib camera calibration backend", Apache-2.0; upstream AnyCalib repo Apache-2.0 (LICENSE file read 19.11.2026) — [COLMAP releases](https://github.com/colmap/colmap/releases), [javrtg/AnyCalib](https://github.com/javrtg/AnyCalib)
- Incremental mapper is "the most robust and well-tested pipeline"; global mapper "may be less robust to outliers in the matching" — [COLMAP FAQ](https://colmap.github.io/faq.html)

### Inferences
- Video frames: one camera per clip (or per constant-zoom segment), which gives hundreds of observations per intrinsic set; historic scans and internet photos: one camera per image with SIMPLE_RADIAL (few parameters, since each has a single image). This matches the COLMAP sharing rule above.
- Cropped images violate the centred-principal-point assumption; with a single image per camera the principal point cannot be estimated reliably, so the usual choice is to keep it fixed at the centre and accept a biased focal/pose for such images, or to register them last against the finished model (pose-only use) so they cannot damage the structure. No recent official guidance on crops was found; this is reasoning, and such images should be treated as texture/appearance sources rather than geometry sources.
- For the roughly 16 % non-video images, an AnyCalib focal prior is likely better than the 1.25 guess for telephoto postcards and wide-angle phone shots; the one-sided-focal solver (one image calibrated by video intrinsics, the other unknown) fits exactly the "historic photo against calibrated video frame" pair. Both exist in COLMAP 4.2; benefit on this data is untested.
- Given mixed, partly unknown intrinsics and likely doppelganger facades, the documented guidance favours the incremental mapper (or global mapper only after `view_graph_calibrator`) for the mixed set.

### Gaps
- How AnyCalib is invoked inside COLMAP (option names, which release exposes it in the CLI) was not found in the docs pages fetched; only the model release note exists as evidence.
- No published evaluation of AnyCalib or view-graph calibration on scanned historic photographs was found.
- No official COLMAP/GLOMAP guidance on cropped images or off-centre principal points was found.
- Whether `view_graph_calibrator` handles per-image cameras with only a few pairs each (typical for historic photos) is not documented in the pages read.
