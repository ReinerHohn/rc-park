# SfM disambiguation for symmetric buildings (doppelgangers) and merging of separately reconstructed sub-models (state Nov 2026)

Research date 2026-11-19. Licenses marked "GitHub API" were read from api.github.com/repos/<repo> on that date (spdx_id field); "None" there means no LICENSE file was detected (legally: all rights reserved, ask the authors before commercial use). "NOASSERTION" means a license file exists but is not a standard SPDX text; in those cases the file/README was read separately where noted.

## 1. Learned pair classifiers (Doppelgangers, Doppelgangers++, newer)

### Takeaway
The only two published learned doppelganger classifiers with code are Doppelgangers (MIT code, LoFTR Apache-2.0: commercially usable) and Doppelgangers++ (CC BY-NC-SA 4.0 code on top of CC BY-NC-SA MASt3R: NOT usable for sold results). Doppelgangers++ is clearly better and needs no per-scene threshold (0.8 everywhere), the original needed thresholds between 0.6 and 0.97 depending on the scene.

### Cited Findings
- Doppelgangers (Cai et al., ICCV 2023 oral) frames disambiguation as binary classification of image pairs; the network input is the spatial distribution of local keypoints and matches. — [arXiv 2309.02420](https://arxiv.org/abs/2309.02420)
- Doppelgangers code license: MIT (GitHub API, last push 2024-03-01, 205 stars). — [RuojinCai/doppelgangers](https://github.com/RuojinCai/doppelgangers)
- Its matcher LoFTR is Apache-2.0 (GitHub API). — [zju3dv/LoFTR](https://github.com/zju3dv/LoFTR)
- Integration: runs COLMAP feature extraction + matching, classifies each matched pair using LoFTR matches, deletes pairs below the threshold from the COLMAP database, then runs the mapper on the pruned database; requires COLMAP 3.8 or later; flags `--skip_feature_matching` (reuse existing database) and `--skip_reconstruction`. Environment pinned to Python 3.8 / PyTorch 1.12 / CUDA 10.2. — [RuojinCai/doppelgangers README](https://github.com/RuojinCai/doppelgangers)
- Recommended threshold: default 0.8. README rule: if the reconstruction splits into several components, lower it; if it is not fully disambiguated, raise it. — [RuojinCai/doppelgangers README](https://github.com/RuojinCai/doppelgangers)
- Demonstrated: vanilla COLMAP produced double towers on Alexander Nevsky Cathedral and missing sides on Big Ben; the classifier-pruned run recovered correct models. The authors note that for some landmarks the correct result splits into two components "due to a lack of camera views from sufficient viewpoints". — [Doppelgangers ICCV 2023 supplemental](https://openaccess.thecvf.com/content/ICCV2023/supplemental/Cai_Doppelgangers_Learning_to_ICCV_2023_supplemental.pdf)
- Known weaknesses of the original, as stated by the follow-up paper (same group): (a) a few surviving bad edges are enough to give a wrong model; (b) reconstruction is sensitive to the threshold - scene-specific values were needed, e.g. 0.97 for Church on Spilled Blood, 0.6 for Ponte di Rialto and Palacio de Comunicaciones; (c) trained only on landmark photos, generalises poorly to everyday scenes (streets, office buildings); (d) depends on COLMAP features + LoFTR match masks, which adds overhead and makes scaling harder. — [Doppelgangers++ arXiv 2412.05826v2](https://arxiv.org/html/2412.05826v2)
- Doppelgangers++ (Xiangli, Cai, Chen, Byrne, Snavely; CVPR 2025): feeds the image pair through a frozen pre-trained MASt3R, takes the decoder's intermediate features and trains a classification head on them. Trained on the Doppelgangers set (73K pairs) plus VisymScenes (47K training pairs mined from 26 sites using GPS/IMU metadata). — [Doppelgangers++ arXiv 2412.05826v2](https://arxiv.org/html/2412.05826v2)
- Doppelgangers++ results: one threshold 0.8 for all 21 benchmark scenes; registers more images than the original in 19 of 21 scenes and has an equal or higher geotag inlier ratio in all 21; Belvedere Vienna: original fails (inlier ratio 0.451), ++ reaches 0.874. Pairwise AP / ROC-AUC on out-of-domain test sets improve by 25-65 % with the same training data. — [Doppelgangers++ arXiv 2412.05826v2](https://arxiv.org/html/2412.05826v2)
- Doppelgangers++ validation method (useful independently of the classifier): geo-tagged images are registered to the model, RANSAC estimates a similarity transform between camera centres and their ECEF geotag positions; the inlier ratio is the correctness score (weighted average over components). Geotags are used only for evaluation, not for reconstruction. — [Doppelgangers++ arXiv 2412.05826v2](https://arxiv.org/html/2412.05826v2)
- Doppelgangers++ code license: the LICENSE file is "Creative Commons Attribution-NonCommercial-ShareAlike 4.0". — [doppelgangers-plusplus LICENSE](https://raw.githubusercontent.com/doppelgangers25/doppelgangers-plusplus/main/LICENSE)
- Doppelgangers++ usage: `colmap_usage.py --colmap_exe_command colmap --input_image_path ... --output_path ... --threshold 0.8 --pretrained checkpoints/checkpoint-dg+visym.pth`; authors used COLMAP 3.10; checkpoints on Hugging Face `doppelgangers25/doppelgangers_plusplus`; includes a dust3r submodule; repo also carries NOTICE and CHECKPOINTS_NOTICE files. — [doppelgangers25/doppelgangers-plusplus](https://github.com/doppelgangers25/doppelgangers-plusplus)
- MASt3R code is CC BY-NC-SA 4.0; its checkpoints carry a separate notice because training datasets have their own terms (Map-free described as very restrictive). — [naver/mast3r](https://github.com/naver/mast3r); [MASt3R checkpoint notice copy](https://huggingface.co/spaces/zino36/Demo/blob/main/CHECKPOINTS_NOTICE)
- GLUEMAP (2026, colmap organisation, co-author J. Schoenberger): global SfM combined with feed-forward backbones, outputs COLMAP sparse models. Uses Doppelgangers++ as an optional two-view stage to filter non-covisible retrieval pairs; option `skip_doppelgangers` (default false; README suggests skipping when the scene has no repetitive structure). GLUEMAP itself is "new BSD", but the README warns that building with the third-party dependencies "may affect the resulting GLUEMAP license"; vendored submodules: Doppelgangers++ (MASt3R/DUSt3R/CroCo), SALAD, VGGSfM, LightGlue, Pi3, VGGT, MapAnything. — [colmap/gluemap](https://github.com/colmap/gluemap); [GLUEMAP paper arXiv 2605.26103](https://arxiv.org/html/2605.26103v1)
- The GLUEMAP paper states that feed-forward methods can collapse distinct parts of a symmetric scene into one reconstruction. — [arXiv 2605.26103](https://arxiv.org/html/2605.26103v1)
- "Semantic Validation in Structure from Motion" (arXiv 2304.02420) appeared in searches as a related approach; not read. — [arXiv 2304.02420](https://arxiv.org/pdf/2304.02420)

### Inferences
- For sold results the commercially clean learned option is the original Doppelgangers (MIT + Apache-2.0 LoFTR). Doppelgangers++ and GLUEMAP-with-Doppelgangers++ are non-commercial because of the CC BY-NC-SA chain (++ code, MASt3R code, MASt3R weights). They can still be used as an internal diagnostic only if the NC license is read as permitting that - this is a legal question, not answered by any source found; flag it.
- 8 GB feasibility: original Doppelgangers = LoFTR (outdoor_ds) + small classifier on downsized pairs, plausible on 8 GB (not stated in the README). Doppelgangers++ = MASt3R ViT-Large at 512 px inference per pair; MASt3R pair inference is commonly run on 8 GB-class cards but no source read here states the memory need.
- Runtime scales with the number of matched PAIRS (not images). For ~700 images with exhaustive/retrieval matching that is tens of thousands of pairs; classify only pairs that survive geometric verification. No per-pair timing was found in the sources.
- The threshold rule of the original (0.6 to 0.97 per scene) means it must be swept and judged by an independent test (e.g. the geotag inlier ratio, or the project's own LoD2/GPS gates) - a single run at 0.8 proves nothing.
- Effort: original = 0.5-1 day (old PyTorch pin; may need a separate environment; database from COLMAP 4.x may need schema checks because the script was written for 3.8). ++ = 0.5 day, COLMAP 3.10-era script.

### Gaps
- Exact number of benchmark scenes solved by the original Doppelgangers vs. Heinly/Wilson/Cui/Yan baselines: the full paper table was not retrieved (abstract page only).
- No runtime or VRAM numbers for either classifier in the sources read.
- No third learned doppelganger classifier with public code (2024-2026) was found beyond these two; the search was not exhaustive.
- Whether the Doppelgangers++ CHECKPOINTS_NOTICE adds restrictions beyond CC BY-NC-SA was not read.
- Whether either script works unmodified with a COLMAP 4.x database (rigs/frames schema, pose-graph tables) is untested.

## 2. Classical geometric / graph methods and their public implementations

### Takeaway
The one maintained, COLMAP-database-native implementation is cvg/sfm-disambiguation-colmap (Yan 2017 and Cui 2015, plus results for Kataria 2020), but it has NO license file, needs per-scene tuning, and its own authors state no method works across datasets with one parameter set. Heinly 2014 and Wilson 2013 have old code (2015/2017) that is not COLMAP-native.

### Cited Findings
- cvg/sfm-disambiguation-colmap implements Yan et al. 2017 (geodesic consistency / path network; parameters `coverage_thres`, `score_thres`, `track_degree`, `alpha`, `minimal_views`) and Cui & Tan 2015 (missing correspondences; `score_version` 1-3, `min_num_valid_depths`, `max_num_neighbors`, `square_radius`), and reports results with Kataria et al. 2020 (reliable resectioning; modified COLMAP sources in `reliable_resectioning/src`). Zach, Jiang, Heinly, Shen, Wang, Wilson, Roberts, Cohen, Ceylan are only covered in its literature review, not implemented. — [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap)
- Workflow: features from COLMAP SIFT or hloc (SuperPoint, D2-Net, R2D2, DISK), exhaustive matching, import via `colmap matches_importer`; the method scores image pairs and writes filtered databases `db_yan_*.db` / `db_cui_*.db`, on which the normal mapper runs. Python 3.7 recommended, notebooks. — [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap)
- Parameter guidance (Yan): coverage 0.7-0.9 for small indoor scenes, about 0.6 for large unstructured sets; score threshold about 0.3 small scenes, 0.04-0.1 large outdoor scenes; Alexander Nevsky Cathedral used coverage 0.6, score 0.1. No recommended values for Cui. — [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap)
- Stated limitations: "No method consistently works well over all datasets with a single set of hyperparameters"; Kataria's method still fails on several datasets even with tuning; the Yan implementation deviates from the paper (non-iconic images in the path network, unique-track percentage in filtering, alpha = 0); Cui's bounding-box score is unstable with outliers (uniform/Gaussian mask variants added, Gaussian lightly tested). Results shown are qualitative (Alexander Nevsky teaser), no quantitative table. — [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap)
- Runtime: Yan's method on berliner_dom (1618 images) took more than 8 hours with the default data structure; `smallarray` or a keypoint limit is recommended for large sets. — [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap)
- License: GitHub API reports no license for cvg/sfm-disambiguation-colmap (last push 2024-06-03, 318 stars). — [GitHub API](https://api.github.com/repos/cvg/sfm-disambiguation-colmap)
- Heinly et al. ECCV 2014 "Correcting for Duplicate Scene Structure in Sparse 3D Reconstruction" is a POST-processing step: it analyses a finished reconstruction, detects errors from duplicate structure (conflicting observations) and splits/re-merges. Code at jheinly/sfm_duplicate_structure_correction; GitHub API: no license, last push 2015. — [Heinly project page](https://www.cs.unc.edu/~jheinly/duplicate_structure.html); [GitHub API](https://api.github.com/repos/jheinly/sfm_duplicate_structure_correction)
- A COLMAP user reported (2018) that Heinly's code needs inlier matches and camera/point data in VisualSfM format. — [COLMAP Google group](https://groups.google.com/g/colmap/c/4afHlSOTUfo)
- Wilson & Snavely ICCV 2013 "Network Principles for SfM" (track-graph local clustering coefficient / bad-track removal): code wilsonkl/sfm-disambig, BSD-2-Clause, last push 2017 (cited as the Wilson baseline by the Doppelgangers paper; repository contents not inspected). — [GitHub API](https://api.github.com/repos/wilsonkl/sfm-disambig); [Doppelgangers paper](https://arxiv.org/pdf/2309.02420)
- The Doppelgangers authors' assessment of the classical family: hand-designed heuristics that are brittle, can require manual parameter tuning for each reconstruction, and can over-segment correct models. — [Doppelgangers paper](https://arxiv.org/pdf/2309.02420)
- TC-SfM (2022, track-community based: groups tracks into communities and removes ambiguous ones). — [arXiv 2206.05866](https://arxiv.org/pdf/2206.05866)
- HiSfM (3dv-casia, 2025; "Orientation of ambiguous image sequences with similar and repeated structures") has a repository github.com/3dv-casia/HiSfM. — [ResearchGate listing](https://www.researchgate.net/publication/392733695_Orientation_of_ambiguous_image_sequences_with_similar_and_repeated_structures)
- "Robust Global Structure-from-Motion via View Graph Pruning" (Xu et al., arXiv 2608.22054, 22 Aug 2026): partition view graph into locally consistent subgraphs, run global SfM per subgraph, RANSAC-prune inconsistent edges ACROSS subgraphs, run global SfM again; tested on ambiguous, sequential and unordered sets; abstract gives no numbers and no code link. — [arXiv 2608.22054](https://arxiv.org/abs/2608.22054)
- VidMap (cvg, ECCV 2026; code Apache-2.0 per GitHub API, last push 2026-11-17): video SfM built on the GLOMAP pipeline. Tracks are built only from sequential matches; loop-closure matches are attached as separate observations instead of being merged transitively, so one wrong closure cannot fuse two chains; sequential edges get Huber loss, loop-closure edges Cauchy loss in rotation averaging and global positioning. LaMAR full-sequence AUC 88.5 vs 62.3 for GLOMAP+LightGlue; without provenance-aware losses 79.9. Stated limit: many mutually consistent false closures can still bias the solution. Depends on RoMa v2, MegaLoc, Depth Anything 3, GeoCalib (licenses of these not checked). — [VidMap arXiv 2607.27194](https://arxiv.org/html/2607.27194); [GitHub API](https://api.github.com/repos/cvg/vidmap)

### Inferences
- Demonstrated vs. plausible: Yan/Cui/Heinly/Wilson are demonstrated on the Heinly-2014 / Yan-2017 / Roberts / Jiang benchmark scenes (mostly symmetric landmarks and small indoor repeats); nothing found demonstrates them on a narrow gate tower with two near-identical faces and almost no corner views. That case is the hardest one for missing-correspondence cues because the "unique" context (neighbouring houses) is different on both sides - which is exactly the cue Cui/Zach/Heinly exploit, so it is plausibly favourable, but unproven.
- Yan 2017 needs "iconic" images and long paths through unambiguous tracks; with a tower whose two sides are linked only by wrong matches, the path network should separate them - plausible, matches its Alexander Nevsky use.
- The missing-correspondence idea (Zach 2008, Cui 2015) is directly implementable with pycolmap on an existing model: for a pair (A,B), project A's triangulated points that B's pose should see; if large image regions with valid depth have no matches while a compact region matches, the pair is a doppelganger. Same for Heinly's conflicting-observation test as a post-check on a merged model. Effort: 1-2 days for a pycolmap script; no license problem because it is a reimplementation of a published idea.
- VidMap's provenance principle (trust sequential/video edges, down-weight cross-sequence edges) is implementable without VidMap: build tracks only within video sequences, treat cross-sequence matches as candidates to verify. Relevant because part of the data is video frames.
- License status "None" for cvg/sfm-disambiguation-colmap and Heinly's code means they can be used to study/try but should not be shipped or relied on commercially without written permission; ideas can be reimplemented.
- 8 GB: all classical methods are CPU/RAM bound; GPU irrelevant. Yan on ~700 images should be far below the 8 h reported for 1618 images (cost grows faster than linearly) - estimate, not measured.

### Gaps
- Zach et al. 2008/2010, Roberts 2011, Jiang 2012, Wang 2018 (BMVC), Kataria 2020: no standalone maintained public implementation was found in this session; Kataria's is only available as modified COLMAP sources inside the cvg repo. Not exhaustively searched.
- Quantitative success rates per method per benchmark scene were not retrieved.
- HiSfM and TC-SfM licenses and COLMAP compatibility not verified (GitHub API rate limit hit).
- Code for arXiv 2608.22054 (view graph pruning): none found.

## 3. What COLMAP 4.x / GLOMAP offer themselves

### Takeaway
Neither COLMAP nor the integrated global mapper contains a doppelganger-specific filter; what exists is generic (relative-pose filtering, inlier thresholds, robust rotation averaging, track limits) plus, since 4.2.0, multi-component output of the global mapper. Position priors (pose_prior_mapper, global mapper prior std options) are the only built-in mechanism that can actually contradict a wrong side assignment.

### Cited Findings
- GLOMAP was integrated into COLMAP 4.0.0 (14 Mar 2026) as the global mapper; the stand-alone glomap repo is archived. — [COLMAP changelog](https://colmap.github.io/changelog.html); [colmap GitHub org](https://github.com/colmap)
- 4.0.0: view graph calibration module; relative pose filtering moved into the view graph (later renamed PoseGraph); track filtering in the global pipeline; optional position prior in absolute pose refinement; gravity added to pose priors; fixed 180-degree flipped solutions in gravity-aligned rotation averaging; fixed sign of GPS longitude from EXIF; guided geometric verification with a known reconstruction. — [COLMAP changelog](https://colmap.github.io/changelog.html)
- 4.1.0 (26 Jun 2026): gravity pose priors from EXIF orientation tags; `GlobalMapper.keep_max_num_tracks`; rotation averaging options exposed in GlobalMapper; gravity-aligned averaging made robust against 180-degree flips. — [COLMAP changelog](https://colmap.github.io/changelog.html)
- 4.2.0 (31 Aug 2026): global mapper reconstructs disconnected view-graph components as separate models (`GlobalMapper.multiple_models`, `GlobalMapper.min_model_size`; breaking default change); optional match-count weighting for rotation averaging; `SequentialMatching.loop_detection_min_index_distance`; fix for merging reconstructions with inconsistent image ID/name mappings. — [COLMAP changelog](https://colmap.github.io/changelog.html)
- 4.2.1 (29 Sep 2026): rejected (DEGENERATE) pairs have payloads cleared and are skipped when loading the database cache; minimum inlier ratio honoured consistently across two-view estimation paths. — [COLMAP changelog](https://colmap.github.io/changelog.html)
- 3.13.0 (7 Nov 2025): pose prior mapper more robust against outlier priors; option to filter stationary points in two-view geometry; option to clean two-view geometries in database_cleaner. — [COLMAP changelog](https://colmap.github.io/changelog.html)
- 3.11 introduced the pose-prior based mapper and the `pose_priors` database table (absolute priors, e.g. GPS). — [COLMAP changelog](https://colmap.github.io/changelog.html)
- CLI: `rotation_averager` runs stand-alone rotation averaging on the view graph; `view_graph_calibrator` modifies intrinsics and two-view geometries in the database in place (run on a copy); the global mapper "depends on reasonably good focal length priors". — [COLMAP CLI docs](https://colmap.github.io/cli.html)
- Third-party statement that GLOMAP is relatively sensitive to matching errors from visual ambiguity (as summarised by search from the view-graph pruning paper; the abstract itself only says global SfM is sensitive to erroneous edges). — [arXiv 2608.22054](https://arxiv.org/pdf/2608.22054)
- The COLMAP FAQ contains no guidance on repetitive/symmetric scenes. — [COLMAP FAQ](https://colmap.github.io/faq.html)

### Inferences
- A consistent doppelganger edge set (many pairs all implying "north face = south face") is geometrically self-consistent, so RANSAC inlier thresholds, relative-pose filtering and robust rotation averaging cannot reject it; raising `min_num_inliers` only helps when the false pairs are weaker than the true ones. This is the reason dedicated methods exist (supported by the Doppelgangers motivation and by VidMap's stated limit on mutually consistent false closures).
- The stand-alone `rotation_averager` gives a cheap diagnostic: for a symmetric tower, false edges imply a relative rotation near 0 degrees for cameras that truly differ by about 180 degrees; comparing each edge's relative rotation against compass/gravity priors or against the per-side averaged rotations flags them. Plausible, not found demonstrated.
- Since 4.2.0 the global mapper returns separate components if the view graph is split beforehand (by classifier or clustering) - this fits a "split into sides first, merge later by external geometry" workflow.
- The project's mapper is a self-built 4.3.dev and the rest pycolmap 4.2.1 (project memory), so all options above should be present; verify names with `colmap global_mapper -h`.

### Gaps
- No COLMAP/GLOMAP GitHub issue specifically about symmetric towers/opposite facades was retrieved (search engines did not surface issue threads; GitHub issue search was not queried directly).
- Exact option names of relative-pose filtering thresholds in 4.2 (max rotation/positional error, min inlier ratio) not read from the source.
- The 3.11/3.12 changelog text was only read via search summary.

## 4. Community detection / view-graph clustering to split into sides before mapping

### Takeaway
Graph partitioning is standard in SfM for scalability (COLMAP hierarchical mapper, DAGSfM, the 2026 view-graph-pruning paper) and track-community methods exist for disambiguation, but no source found shows plain community detection reliably separating two doppelganger sides; the published evidence is for "cluster, reconstruct locally, then test cross-cluster edges geometrically".

### Cited Findings
- COLMAP `hierarchical_mapper` partitions the scene into overlapping sub-models, reconstructs them in parallel and merges them; it recommends extra triangulation and bundle adjustment afterwards. — [COLMAP CLI docs](https://colmap.github.io/cli.html)
- DAGSfM (Pattern Recognition 2020, "Graph-Based Parallel Large Scale SfM"): view-graph clustering and distributed reconstruction with public code. — [AIBluefisher/DAGSfM](https://github.com/AIBluefisher/DAGSfM)
- Xu et al. 2026: locally consistent subgraphs, per-subgraph global SfM, RANSAC pruning of inconsistent inter-subgraph edges, second global run. — [arXiv 2608.22054](https://arxiv.org/abs/2608.22054)
- TC-SfM: community detection on the TRACK graph rather than the image graph to isolate ambiguous tracks. — [arXiv 2206.05866](https://arxiv.org/pdf/2206.05866)
- Wilson & Snavely 2013 operate on the bipartite visibility/track graph with local network measures (code BSD-2-Clause). — [wilsonkl/sfm-disambig](https://github.com/wilsonkl/sfm-disambig)
- Doppelgangers reports that correct disambiguation may legitimately leave two components when views around the corner are missing. — [Doppelgangers supplemental](https://openaccess.thecvf.com/content/ICCV2023/supplemental/Cai_Doppelgangers_Learning_to_ICCV_2023_supplemental.pdf)

### Inferences
- The project's own result (Martinstor split into North 555 / South 122 images by keeping only confirmed connections, commit 46b7be5c) is the same pattern: strict edge set -> components -> per-component models. The literature supports this as the correct end state when no true corner links exist.
- Plain modularity clustering (Louvain/Leiden via networkx/igraph, BSD/GPL - check igraph's GPL) on a match-count-weighted graph is cheap to try (hours), but doppelganger edges are often as strong as true edges, so clusters must be validated by missing-correspondence or prior tests. Not demonstrated in a publication as a stand-alone solution.
- The Xu 2026 recipe is implementable with COLMAP 4.2: cluster, `global_mapper` per cluster, then for each cross-cluster edge compare its relative pose with the pose predicted by the best similarity alignment between the two cluster models (RANSAC); prune disagreeing edges. Effort 2-3 days.

### Gaps
- No practitioner report (forum, issue) of community detection being used routinely against doppelgangers was found.
- No code for Xu 2026.

## 5. Merging disconnected sub-models that share no true common points

### Takeaway
COLMAP `model_merger` cannot do this (it needs common registered images). Published routes are: symmetry + semantic cues (Cohen et al. ICCV 2015, outputs several plausible candidates, no code found), external georeferenced anchors (GPS similarity alignment per sub-model, footprints/GIS with ICP, satellite/ground localisation), or structural matching (windows, 3D lines). Learned low-overlap point-cloud registration (Predator, GeoTransformer; both MIT) still needs real overlap and does not apply to two opposite faces.

### Cited Findings
- `model_merger`: "Attempt to merge two disconnected reconstructions, if they have common registered images"; FAQ recommends a global bundle adjustment after merging. — [COLMAP CLI docs](https://colmap.github.io/cli.html); [COLMAP FAQ](https://colmap.github.io/faq.html)
- `model_aligner`: geo-registers a model to given camera centres (from database priors or a text file, GPS or Cartesian); at least 3 images needed for the similarity transform; options `--ref_images_path` / `--database_path`, `--ref_is_gps`, `--alignment_type ecef|enu`, `--alignment_max_error` (RANSAC threshold). — [COLMAP FAQ](https://colmap.github.io/faq.html)
- `image_registrator` registers additional database images into an existing model without bundle adjustment or triangulation. — [COLMAP CLI docs](https://colmap.github.io/cli.html)
- Cohen, Sattler, Pollefeys, "Merging the Unmatchable: Stitching Visually Disconnected SfM Models" (ICCV 2015): targets exactly building sides that reconstruct separately without visual overlap; uses symmetries and semantic cues to infer the relative placement; states the general problem is unsolvable and therefore outputs a SET of plausible merged models; checks against aerial views. — [Cohen et al. ICCV 2015](https://www.cv-foundation.org/openaccess/content_iccv_2015/papers/Cohen_Merging_the_Unmatchable_ICCV_2015_paper.pdf)
- Cohen et al. ECCV 2016 "Indoor-Outdoor 3D Reconstruction Alignment": aligns disconnected models by detecting windows in 3D via semantic labels and maximising matched windows without model intersection; Koch et al. CVPR-W 2016 do the same with 3D line segments. — [Springer](https://link.springer.com/chapter/10.1007/978-3-319-46487-9_18); [Koch et al.](https://openaccess.thecvf.com/content_cvpr_2016_workshops/w19/papers/Koch_Automatic_Alignment_of_CVPR_2016_paper.pdf)
- GIS-footprint registration: SfM cloud aligned to 2D building footprints from three or more user-picked correspondences (corners), refined by ICP. — [arXiv 1507.03698](https://arxiv.org/pdf/1507.03698)
- "Ground-to-Satellite Localization in Unconstrained Image Collections for 3D Scene Reconstruction" (arXiv 2608.29211, 2026): per search summary, includes a case where ground cameras form two groups without any visual overlap and the two SfM models are joined only via satellite/ground alignment. Not read in full. — [arXiv 2608.29211](https://arxiv.org/pdf/2608.29211)
- PREDATOR (Huang et al., CVPR 2021, "Registration of 3D Point Clouds with Low Overlap"): attention on the overlap region; code MIT (GitHub API, prs-eth/OverlapPredator). — [Predator project page](https://overlappredator.github.io); [GitHub API](https://api.github.com/repos/prs-eth/OverlapPredator)
- GeoTransformer (Qin et al., CVPR 2022 / TPAMI): code MIT (GitHub API, qinzheng93/GeoTransformer, last push 2023-11). — [arXiv 2308.03768](https://arxiv.org/pdf/2308.03768); [GitHub API](https://api.github.com/repos/qinzheng93/GeoTransformer)
- Metashape practitioner note (unofficial community manual, self-described as an untested hypothesis): point-based chunk alignment cannot break geometric symmetry - matches land on the mirrored copy and the two sides overlap; changing keypoint limits/preselection changes match counts but not the wrong share. Recommended recovery there is marker-based: markers with coordinates placed in both chunks. — [Metashape expert manual, alignChunks symmetry](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/alignment/alignchunks-symmetric-scene-failure/); [same, helping alignment](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/alignment/helping-alignment/)

### Inferences
- "Low overlap" in Predator/GeoTransformer means roughly 10-30 % shared surface (3DLoMatch-type benchmarks); North and South face of a tower share zero surface except possibly thin flank/roof strips. They would match the two look-alike faces onto each other - reproducing the doppelganger error in 3D. Not recommended for face-to-face merging; only useful for registering each side to an external full-coverage cloud (LoD2 mesh sampled, DSM, laser) where true overlap exists. 8 GB is sufficient for both at their usual voxel sizes (plausible, both were trained on 11-24 GB cards; not verified).
- The 180-degree rotation about the building axis (what the project did for Martinstor) is a special case of Cohen 2015's symmetry hypothesis. Cohen's own conclusion applies: symmetry gives a candidate set, not a unique answer. For a two-fold symmetric tower the residual freedoms are: exact axis position (2 DOF in plan), wall thickness/depth offset along the passage axis, height offset, relative scale. These need independent evidence: flank/side walls seen from both sides, roof ridge/eaves, LoD2 footprint width, DSM height, geotags.
- Most robust commercial-safe route with existing tools: align EACH sub-model separately to the same external frame - (a) `model_aligner` with geotagged camera centres (>=3, RANSAC) for coarse placement, (b) refine against LoD2/footprint walls by plane/ICP fit restricted to the facade the sub-model actually sees, (c) fix scale per sub-model from a measured building dimension. Then the two models are merged by construction, and symmetry serves only as a cross-check. All steps are pycolmap/Open3D (MIT) work; effort 1-2 days; the project already has the gates (lage_gps_pruefen, wolke_grundriss_pruefen).
- After placing both sides in one frame, shared tie points can be created artificially: sparse user constraints (3-4 points per side picked on corners visible from both, e.g. roof corners, flank edges) used as control points in a final bundle adjustment with fixed/soft positions. COLMAP has no marker GUI; implement via pycolmap bundle adjustment with position priors or fixed 3D points (plausible, standard practice in Metashape via markers).
- Bridging images are the only way to get true common points: `image_registrator` (or the mapper) can add corner/oblique/aerial photos that see both a face and a flank; with a registered bridge in both models `model_merger` works.

### Gaps
- No public code for Cohen et al. 2015/2016 was found.
- No publication found that evaluates the accuracy of a symmetry-based 180-degree placement against ground truth for towers.
- arXiv 2608.29211 code/license not checked.
- TEASER++ and other robust registration licenses could not be checked (API rate limit); TEASER++ is commonly cited as MIT - unverified here.

## 6. Capture-side and data-side remedies (practitioners; priors in COLMAP)

### Takeaway
Practitioner guidance found is thin and partly unofficial: the consistent recommendations are bridging views around corners, markers/control points with coordinates, and position priors. COLMAP supports GPS priors natively since 3.11 (pose_prior_mapper; global mapper prior std options; gravity priors since 4.0/4.1), which is the directly usable data-side remedy.

### Cited Findings
- COLMAP extracts EXIF GPS automatically into the pose_priors table at feature extraction; `pose_prior_mapper` is the incremental mapper with position-prior constraints; `--overwrite_priors_covariance` with `--prior_position_std_x/y/z` (default 1.0 m each). — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Global mapper accepts the same prior position std options. — [COLMAP changelog/search summary](https://colmap.github.io/changelog.html)
- 3.13.0 improved pose-prior-mapper robustness to outlier priors; 4.0.0 fixed the sign of EXIF GPS longitude and added gravity priors; 4.1.0 extracts gravity from EXIF orientation tags; 4.2.0 fixed spatial matching with missing pose priors. — [COLMAP changelog](https://colmap.github.io/changelog.html)
- A 2026 preprint notes that the pose-prior mapper consumes position priors only and re-runs full incremental SfM (cannot warm-start from good existing poses). Single third-party source. — [arXiv 2608.21008](https://arxiv.org/pdf/2608.21008)
- Doppelgangers++ shows that noisy geotags (Mapillary) are good enough to decide whether a model is correctly disambiguated via a RANSAC similarity inlier ratio. — [arXiv 2412.05826v2](https://arxiv.org/html/2412.05826v2)
- Doppelgangers: correct reconstructions split into two components where "camera views from sufficient viewpoints" are lacking - i.e. the cure is images that connect the sides. — [Doppelgangers supplemental](https://openaccess.thecvf.com/content/ICCV2023/supplemental/Cai_Doppelgangers_Learning_to_ICCV_2023_supplemental.pdf)
- Metashape community manual: for cameras/chunks that will not align, place markers visible in at least two correctly aligned photos; markers need coordinates to act in Optimize Cameras; tuning keypoint limits does not fix symmetric mismatches. Unofficial source, says no Agisoft thread documents the symmetric case separately. — [Metashape expert manual](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/alignment/helping-alignment/)
- A University of Trieste Metashape guide lists repeated building morphology as a cause of wrong alignments (per search summary). — [RRMD Guida Metashape](https://moodle2.units.it/pluginfile.php/814171/mod_resource/content/1/RRMD_GuidaMetashape_eng_light.pdf)
- VidMap evidence that temporal order is a strong disambiguator: treating sequential and loop-closure edges equally is "catastrophic" on LaMAR. — [VidMap arXiv 2607.27194](https://arxiv.org/html/2607.27194)

### Inferences
- A smartphone geotag error of 5-10 m is larger than a gate tower's depth (walls at about +-4 m in the project), so position priors alone cannot say on which SIDE of the wall plane a camera stands with certainty for a single image; but they do so statistically over many images, and the viewing direction (compass heading / the fact that a camera looking at the north face stands north of the tower) flips by 180 degrees between sides. Position prior + estimated rotation therefore gives a strong test: for each registered camera check that the tower lies in front of the camera given its GPS position. This is implementable in pycolmap in a few hours and license-free. Demonstrated only indirectly (Doppelgangers++ geotag validation).
- COLMAP has gravity priors but no heading (compass) prior in the sources read; heading must be used as an external check, not as a mapper constraint.
- Images that truly connect opposite faces: (1) walk-around sequences with small angular steps past the corners (flank visible together with a face), (2) oblique or aerial/drone/high-vantage views showing roof plus two faces, (3) views through the gate passage showing the inner vault and the far street, (4) distant views where asymmetric surroundings (neighbouring houses, street furniture) share the frame with the tower. For gate towers in a row of houses, (1) is often physically impossible because flanks are built in - then only roof-level/aerial views and passage views bridge. This is reasoning from the cited component-split observations; no practitioner source enumerating these for towers was found.
- Video frames: use sequential matching with loop detection restricted (`loop_detection_min_index_distance`) and treat cross-video matches as suspect, following VidMap's principle.
- Geotag-less internet photos can be given coarse priors by hand (north side / south side label = position prior some metres in front of the respective face with a few metres std); with pose_prior_mapper or global-mapper priors this turns a side label into a constraint. Plausible; std must be loose enough not to distort geometry. Effort: 0.5 day.

### Gaps
- No official Agisoft or RealityCapture/RealityScan documentation passage dealing specifically with symmetric towers was retrieved; the only specific page is an unofficial community manual that calls its own claim an untested hypothesis.
- No source quantifies how many bridging images are needed.
- No test found of pose_prior_mapper specifically as a doppelganger remedy.

## 7. Summary per candidate (license / 8 GB / benefit / effort)

### Takeaway
Commercially clean and worth trying first: geotag/side-label priors and prior-based checks (COLMAP BSD), strict-edge splitting plus per-side alignment to external geometry, own pycolmap reimplementation of missing-correspondence tests, original Doppelgangers (MIT). Non-commercial or unlicensed: Doppelgangers++, MASt3R, GLUEMAP with its default dependencies, cvg/sfm-disambiguation-colmap (no license), Heinly code (no license).

### Cited Findings
- Doppelgangers: MIT; LoFTR Apache-2.0; default threshold 0.8, needs per-scene tuning 0.6-0.97. — [RuojinCai/doppelgangers](https://github.com/RuojinCai/doppelgangers); [arXiv 2412.05826v2](https://arxiv.org/html/2412.05826v2)
- Doppelgangers++: CC BY-NC-SA 4.0, on MASt3R CC BY-NC-SA 4.0; threshold 0.8 for all scenes. — [LICENSE](https://raw.githubusercontent.com/doppelgangers25/doppelgangers-plusplus/main/LICENSE); [naver/mast3r](https://github.com/naver/mast3r)
- GLUEMAP: BSD core, license affected by vendored dependencies incl. Doppelgangers++. — [colmap/gluemap](https://github.com/colmap/gluemap)
- cvg/sfm-disambiguation-colmap: no license; Yan >8 h on 1618 images; per-scene tuning. — [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap)
- wilsonkl/sfm-disambig: BSD-2-Clause (2017). — [GitHub API](https://api.github.com/repos/wilsonkl/sfm-disambig)
- VidMap: Apache-2.0 code, video input, built on GLOMAP. — [GitHub API](https://api.github.com/repos/cvg/vidmap)
- Predator, GeoTransformer: MIT. — [GitHub API Predator](https://api.github.com/repos/prs-eth/OverlapPredator); [GitHub API GeoTransformer](https://api.github.com/repos/qinzheng93/GeoTransformer)
- COLMAP built-ins: pose_prior_mapper, global mapper multi-component (4.2.0), rotation_averager, model_aligner, model_merger (needs common images). — [COLMAP changelog](https://colmap.github.io/changelog.html); [COLMAP CLI](https://colmap.github.io/cli.html)

### Inferences
- Ranking by expected benefit per effort for a single gate tower (judgement, not a benchmark): (1) position/side priors + geotag-consistency test, hours, CPU only; (2) keep strict split into sides and align each side separately to LoD2/GPS, then cross-check with the 180-degree symmetry, 1-2 days; (3) pycolmap missing-correspondence/conflicting-observation test to prune pairs or verify a merged model, 1-2 days; (4) original Doppelgangers with threshold sweep judged by test (1), 0.5-1 day, GPU 8 GB plausible; (5) VidMap for the video portions, effort unknown, its dependencies' licenses unchecked; (6) Doppelgangers++ only as a non-commercial diagnostic, never in the sold chain without legal clearance; (7) low-overlap point-cloud registration: not suited for face-to-face.
- COLMAP itself is BSD (repository license file; GitHub API reports NOASSERTION because the text is non-standard) - confirm in the repo before stating it in a customer-facing document.

### Gaps
- None of the candidates has a published result on narrow two-faced gate towers; every benefit estimate above is extrapolated from landmark benchmarks.
- Licenses of weights/dependencies for VidMap (RoMa v2, MegaLoc, Depth Anything 3, GeoCalib) and for the LoFTR outdoor checkpoint's training data (MegaDepth) were not checked.
