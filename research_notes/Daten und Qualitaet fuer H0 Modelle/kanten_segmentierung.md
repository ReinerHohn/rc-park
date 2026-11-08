# Learned edge/line detection and semantic masks for a model-vs-photo facade edge metric

Context: rendered model edges (creases, depth discontinuities) are compared with photo edges (currently OpenCV Canny after ~7 cm Gaussian blur) using truncated chamfer distance. Canny also fires on shadows, stains, foliage, texture, signs, people and cars. The goal is photo edges that correspond to geometric structure. All licenses below were checked on 2026-11-05 through the GitHub license API, the raw LICENSE files and HF model-card tags, unless noted otherwise. Licenses for code and for weights are listed separately. Where a source does not say, the entry says "unknown".

## 1. Learned edge detectors (accuracy, speed, license of code and weights)

### Takeaway
DexiNed, TEED, EDTER, DiffusionEdge, DeepLSD, HAWP and SOLD2 have code under permissive licenses (MIT/Apache). PiDiNet ("research purpose only, commercial use contact authors") and RCF (CC BY-NC-SA 4.0) are not permissive. Almost no repo gives a separate license for its weights, and most weights are trained on BSDS500/BIPED, whose own terms were not verified. No generic edge detector separates geometric edges from texture edges. They give cleaner and thinner edges than Canny, but shadow and stain edges remain.

### Cited Findings
**DexiNed** (Soria et al.)
- Code is MIT. The README gives no weights license; the PyTorch checkpoint is on Google Drive. — [GitHub xavysp/DexiNed](https://github.com/xavysp/DexiNed)
- BIPEDv2 results from the README table: DexiNed-f ODS .895 / (probably OIS) .900 / AP .927; DexiNed-a .893/.897/.940. For comparison: RCF .849/.861, BDCN .890/.899, CATS .887/.892. The second column is labelled "ODS" twice in the README; OIS is my inference. — [GitHub xavysp/DexiNed](https://github.com/xavysp/DexiNed)
- DexiNed was trained on BIPED, a dataset of outdoor street and building images (from memory, not re-verified). This would make it the domain closest to facades. Treat as an inference.

**TEED** (Tiny and Efficient Edge Detector, ICCV 2023 Workshop)
- Code is MIT. About 58K parameters ("less than 0.2% of the state-of-the-art models"). Training on BIPED takes less than 30 minutes. The README gives no weights license and no inference FPS. — [GitHub xavysp/TEED](https://github.com/xavysp/TEED), [CVF Open Access](https://openaccess.thecvf.com/content/ICCV2023W/RCV/html/Soria_Tiny_and_Efficient_Model_for_the_Edge_Detection_Generalization_ICCVW_2023_paper.html)
- The ODS 0.828 often quoted for TEED is on UDED, not BIPED. SOTAVerified marks it as unverified. — [paperswithcode](https://www.paperswithcode.com/paper/tiny-and-efficient-model-for-the-edge), [SOTAVerified](https://sotaverified.org/papers/tiny-and-efficient-model-for-the-edge)

**PiDiNet** (Pixel Difference Networks, ICCV 2021)
- LICENSE begins: "It is just for research purpose, and commercial use should be contacted with authors first." An MIT text follows, but the preamble limits use. Treat as NC for sale. — [LICENSE hellozhuo/pidinet](https://raw.githubusercontent.com/hellozhuo/pidinet/master/LICENSE)
- BSDS (README, RTX 2080 Ti): PiDiNet ODS .807 / OIS .823 / 96 FPS; PiDiNet-small .798/.814/161 FPS; PiDiNet-tiny-L .787/.804/253 FPS; table7 variant (with extra data, presumably VOC) .818/.824/17 FPS. Weights are in the repo under `trained_models`. — [GitHub hellozhuo/pidinet](https://github.com/hellozhuo/pidinet)

**HED** (Xie & Tu 2015)
- The original repo is a Caffe fork under a BSD-style Caffe license (redistribution with copyright notice). No separate weights license. — [LICENSE s9xie/hed](https://raw.githubusercontent.com/s9xie/hed/master/LICENSE)
- `controlnet_aux` (Apache-2.0) bundles PyTorch ports of HED, PiDiNet, MLSD, LineArt and others. The HF repo it loads weights from (`lllyasviel/Annotators`) is tagged "license:other". — [GitHub API huggingface/controlnet_aux](https://github.com/huggingface/controlnet_aux), [HF lllyasviel/Annotators](https://huggingface.co/lllyasviel/Annotators)

**RCF** (Richer Convolutional Features)
- Code is CC BY-NC-SA 4.0, "for NonCommercial use only. Any commercial use should get formal permission first". — [LICENSE yun-liu/RCF](https://raw.githubusercontent.com/yun-liu/RCF/master/LICENSE)

**EDTER** (Edge Detection with Transformer, CVPR 2022)
- Code is MIT. — [GitHub mengyangpu/EDTER](https://github.com/mengyangpu/EDTER)
- BSDS: 0.824 ODS / 0.841 OIS single-scale (BSDS-only training) in the DiffusionEdge table. EDTER's own paper reports 0.840 ODS multi-scale and higher with extra data. — [arXiv 2401.02032](https://arxiv.org/pdf/2401.02032), [arXiv 2203.08566](https://arxiv.org/pdf/2203.08566)
- It is a ViT-based two-stage model, heavier than the CNN detectors. No VRAM figure found.

**DiffusionEdge** (AAAI 2024)
- Code is Apache-2.0. — [GitHub GuHuangAI/DiffusionEdge](https://github.com/GuHuangAI/DiffusionEdge)
- BSDS single-scale: 0.834 ODS / 0.848 OIS (vs UAED 0.829/0.847, EDTER 0.824/0.841). Its main selling point is crisp, thin edges without NMS. — [arXiv 2401.02032](https://arxiv.org/pdf/2401.02032)
- EDMB reports DiffusionEdge's model is about 3x larger than EDMB's. Sampling is iterative and slow. — [arXiv 2501.04846](https://arxiv.org/pdf/2501.04846)

**UAED / MuGE** (Zhou et al., CVPR 2023 / CVPR 2024)
- Code is at github.com/ZhouCX117/UAED (README also covers MuGE). Weights are on Google Drive / Quark. The GitHub API returned no license for the repos tried, so the license is unknown. — [arXiv 2303.11828](https://arxiv.org/pdf/2303.11828), [relatedrepos UAED_MuGE](https://relatedrepos.com/gh/ZhouCX117/UAED_MuGE)
- MuGE on BSDS: 0.831 ODS / 0.847 OIS / 0.886 AP (third-party table snippet). MuGE has a granularity control input, which could suppress fine texture edges by asking for coarse granularity. — [sotaverified MuGE](https://sotaverified.org/papers/muge-multiple-granularity-edge-detection), [MuGE PDF](https://www3.cs.stonybrook.edu/~hling/publication/MuGE.pdf)
- A Stable-Diffusion-based detector (GED, arXiv 2410.03080) claims ODS 0.886, "+3.6% over MuGE" (setting not checked). It needs an SD backbone, so it is heavy. — [arXiv 2410.03080](https://arxiv.org/pdf/2410.03080)

**SAM-based edges**
- SAM, zero-shot on BSDS500 (16x16 point grid, 768 masks, Sobel on mask probabilities, edge NMS): ODS 0.768. The paper notes SAM "often outputs more edges than are present in the ground truth" because it is not trained to BSDS bias. — [arXiv 2304.02643](https://arxiv.org/pdf/2304.02643)
- SAM v1 code and weights are Apache-2.0; SAM 2.1 HF weights are tagged apache-2.0. — [GitHub facebookresearch/segment-anything](https://github.com/facebookresearch/segment-anything), [HF facebook/sam2.1-hiera-large](https://huggingface.co/facebook/sam2.1-hiera-large)
- SCESAME (spectral-clustering ensemble of SAM masks, Apache-2.0) reduces over-detection; the authors report BSDS performance close to "CNN-based methods from seven years ago". — [arXiv 2308.13779](https://arxiv.org/pdf/2308.13779), [GitHub ymgw55/SCESAME](https://www.github.com/ymgw55/SCESAME)
- FastSAM reports zero-shot BSDS edges similar to SAM. — [arXiv 2306.12156](https://arxiv.org/pdf/2306.12156)

### Inferences
- On BSDS, the learned detectors all sit between 0.79 and 0.84 ODS single-scale. The differences are small next to the domain gap (BSDS holds natural images). DexiNed/TEED trained on BIPED, which is closer to urban scenes, is the cheapest commercially clean test (MIT code). The weights license still needs to be confirmed with the author.
- The BSDS ground truth was drawn by humans, who mark object and region boundaries. This partly suppresses fine texture, but humans also trace strong shadows and signs. A BSDS-trained detector therefore removes foliage clutter and wall texture better than Canny does, but not shadows.
- SAM mask boundaries are a natural fit for "region" edges such as wall vs sky, roof vs wall and window panes. But SAM also segments posters and shadows as regions. Combine it with a semantic mask (section 3) and a normal/depth check (section 4).

### Gaps
- No weights license is published for DexiNed, TEED, EDTER, DiffusionEdge, HED, UAED or MuGE. Their training data (BSDS500, BIPED, NYUD, Multicue, PASCAL VOC) carries its own terms, which I did not verify here.
- No reliable VRAM numbers on 8 GB GPUs were found for any detector. From architecture size (inference, unverified): TEED, PiDiNet and DexiNed (~35M params) fit easily at 1-2 MP. EDTER and DiffusionEdge likely need tiling at full photo resolution.
- I found no TEED BIPED ODS/OIS figure in the sources checked.
- paperswithcode is no longer maintained, so no consolidated leaderboard was available.

## 2. Line segment detectors for facades

### Takeaway
Facades are dominated by straight lines, so a line detector is a strong filter against foliage and blob-like stains. DeepLSD (MIT code and MIT weights, MegaDepth-trained outdoor model), HAWP v3 (MIT), ScaleLSD (MIT, CVPR 2025), SOLD2 (MIT code), M-LSD (Apache-2.0) and LETR (Apache-2.0) are all permissive at the code level. DeepLSD is the only one whose weights license is stated explicitly.

### Cited Findings
- **LSD in OpenCV**: removed in OpenCV 3.4.6-3.4.15 and 4.1.0-4.5.3 "due original code license conflict". Restored after the "Computation of a NFA" code was published under MIT. Current 4.x/5.0 docs list `cv::LineSegmentDetector` again. The version range comes from a third-party binding's docs (docs.rs); I did not confirm it in the OpenCV changelog. — [docs.rs opencv LineSegmentDetector](https://docs.rs/crate/opencv/latest/target-redirect/x86_64-unknown-linux-gnu/opencv/imgproc/struct.LineSegmentDetector.html), [OpenCV 5.0 docs](https://docs.opencv.org/5.0/main_modules/classcv_1_1LineSegmentDetector.html)
- **DeepLSD** (CVG ETH): code MIT. "Both models are released under an MIT license, similarly as for the rest of this repo." `deeplsd_wireframe` was trained on Wireframe (indoor, "easy"). `deeplsd_md` was trained on MegaDepth ("more generic, outdoors, harder scenes"). DeepLSD refines line segments using a learned line attraction field. — [GitHub cvg/DeepLSD](https://github.com/cvg/DeepLSD)
- **SOLD2**: code MIT. Weights `sold2_synthetic` and `sold2_wireframe` have no separate license; the Wireframe dataset terms are not stated. — [GitHub cvg/SOLD2](https://github.com/cvg/SOLD2)
- **HAWP v2/v3**: code MIT. HAWPv3 is "a state-of-the-art self-supervised wireframe parser", described as good on out-of-distribution images. Checkpoints come via `downloads.sh` (e.g. `hawpv3-imagenet-03a84.pth`, trained on ImageNet images). No separate weights license. — [GitHub cherubicXN/hawp](https://github.com/cherubicXN/hawp)
- **ScaleLSD** (CVPR 2025, Wuhan Univ./Ant Group/NCSU): self-supervised, trained on more than 10M unlabeled real images. The authors report it beats classical LSD and does well zero-shot on 3D geometry and line matching. Repo `ant-research/scalelsd` is MIT according to the GitHub API. — [arXiv 2506.09369](https://arxiv.org/html/2506.09369v1), [project page](https://ant-research.github.io/scalelsd), GitHub API license check
- **M-LSD** (NAVER, mobile real-time): Apache-2.0. — [GitHub navervision/mlsd](https://github.com/navervision/mlsd)
- **LETR** (line transformer, UCSD): Apache-2.0. — [GitHub mlpc-ucsd/LETR](https://github.com/mlpc-ucsd/LETR)

### Inferences
- For facades, line segments directly suppress foliage (no long straight segments) and many stains. They do not suppress straight shadow edges cast by cornices and eaves, sign borders or window-frame albedo edges. Note that cornice shadows are often parallel to real geometric edges and only a few cm away, so after the 7 cm blur they are roughly aligned anyway.
- Suggested metric variant: rasterize only the detected segments (DeepLSD-md or ScaleLSD) as the photo edge map. Optionally weight by segment length (e.g. > 20 px) and by alignment with vanishing directions. Use these instead of, or intersected with, Canny.
- DeepLSD-md has the clearest commercial status: MIT code and weights. Training data is MegaDepth, which is built from Flickr photos; I did not verify its terms.

### Gaps
- No speed or VRAM figures were collected for DeepLSD, ScaleLSD or HAWPv3 on an 8 GB GPU. All are moderate-size CNNs and likely fit (inference, unverified).
- No facade-specific benchmark was found that compares these line detectors.

## 3. Semantic masks to exclude vegetation, cars, people and sky

### Takeaway
At the code level, Mask2Former and OneFormer are MIT, SAM 2/2.1 is Apache-2.0, and Grounded-SAM-2 is Apache-2.0. SegFormer is NVIDIA research/evaluation-only (NC). DINOv3 and SAM 3 are under Meta's custom licenses, which grant commercial use with restrictions. The bigger problem is the training datasets. Cityscapes and ADE20K are explicitly non-commercial, and the Mapillary Vistas research edition is reportedly NC (unverified). So "MIT" checkpoints trained on them are in a legal grey zone for a product. Text-prompted open-vocabulary pipelines (Grounding DINO + SAM 2) avoid these closed-set datasets.

### Cited Findings
- **SegFormer** (NVlabs): "NVIDIA Source Code License for SegFormer"; the Work may be used "non-commercially ... for research or evaluation purposes only". HF checkpoints (e.g. `nvidia/segformer-b5-finetuned-cityscapes-1024-1024`, `segformer-b0-finetuned-ade-512-512`) are tagged "license:other". — [LICENSE NVlabs/SegFormer](https://raw.githubusercontent.com/NVlabs/SegFormer/master/LICENSE), [HF nvidia/segformer-b5-cityscapes](https://huggingface.co/nvidia/segformer-b5-finetuned-cityscapes-1024-1024)
- **Mask2Former**: repo MIT (GitHub API). HF checkpoints `facebook/mask2former-swin-large-cityscapes-semantic` and `...-mapillary-vistas-semantic` are tagged "license:other". — [GitHub facebookresearch/Mask2Former](https://github.com/facebookresearch/Mask2Former), [HF mask2former vistas](https://huggingface.co/facebook/mask2former-swin-large-mapillary-vistas-semantic)
- **OneFormer**: repo MIT. HF checkpoints `shi-labs/oneformer_cityscapes_swin_large` and `oneformer_ade20k_swin_large` are tagged "license:mit". — [GitHub SHI-Labs/OneFormer](https://github.com/SHI-Labs/OneFormer), [HF shi-labs/oneformer_ade20k_swin_large](https://huggingface.co/shi-labs/oneformer_ade20k_swin_large)
- **UperNet-ConvNeXt** (openmmlab, ADE20K) HF tag: MIT. — [HF openmmlab/upernet-convnext-small](https://huggingface.co/openmmlab/upernet-convnext-small)
- **Cityscapes license**: "may not use the dataset or any derivative work for commercial purposes" (item 4). Distributing models trained on it is allowed as "abstract representations" (item 3). These two clauses are in tension; I read using a Cityscapes-trained model inside a product as risky. — [Cityscapes license](https://www.cityscapes-dataset.com/license/)
- **ADE20K terms**: "Researcher shall use the Database only for non-commercial research and educational purposes"; the researcher's employer is also bound. — [ADE20K Terms](https://ade20k.csail.mit.edu/terms)
- **Mapillary Vistas** sources conflict. Dataset Ninja lists CC BY-NC-SA 4.0 ([Dataset Ninja](https://datasetninja.com/mapillary-vistas-dataset)). The ICCV 2017 paper says a separate "commercial edition" exists with 100 classes ([ICCV paper](https://openaccess.thecvf.com/content_ICCV_2017/papers/Neuhold_The_Mapillary_Vistas_ICCV_2017_paper.pdf)). TechCrunch (2017) says commercial products need a paid license ([TechCrunch](https://techcrunch.com/2017/05/03/mapillary-open-sources-25k-street-level-images-to-train-automotive-ai-systems)). Mapillary's own SeamSeg Vistas model files are CC BY-NC-SA 4.0 ([ecosyste.ms seamseg](https://awesome.ecosyste.ms/projects/github.com%2Fmapillary%2Fseamseg)). I did not find the official license page.
- **SAM 2 / 2.1**: repo Apache-2.0; HF weights tagged apache-2.0. — [GitHub facebookresearch/sam2](https://github.com/facebookresearch/sam2), [HF facebook/sam2.1-hiera-large](https://huggingface.co/facebook/sam2.1-hiera-large)
- **SAM 3** ("SAM License", updated 19 Nov 2025): covers code AND trained weights. It grants a "non-exclusive, worldwide, non-transferable and royalty-free limited license ... to use, reproduce, distribute, copy, create derivative works". It has no NC clause, but includes trade-control and military/weapons end-use bans, a patent-litigation termination clause and an acknowledgment requirement in publications. HF weights are gated (manual approval). SAM 3 supports text-concept prompts, from memory: "promptable concept segmentation". — [LICENSE facebookresearch/sam3](https://raw.githubusercontent.com/facebookresearch/sam3/main/LICENSE), [HF facebook/sam3](https://huggingface.co/facebook/sam3)
- **Grounded-SAM-2** (IDEA-Research): Apache-2.0 (code). Grounding DINO weights and licenses not checked separately. — [GitHub IDEA-Research/Grounded-SAM-2](https://github.com/IDEA-Research/Grounded-SAM-2)
- **DINOv2**: Apache-2.0. **DINOv3**: "DINOv3 License" (19 Aug 2025), the same structure as the SAM License (royalty-free grant including derivatives, trade-control/military restrictions, no explicit NC). HF weights gated. — [GitHub dinov2](https://github.com/facebookresearch/dinov2), [LICENSE dinov3](https://raw.githubusercontent.com/facebookresearch/dinov3/main/LICENSE.md), [HF dinov3-vitl16](https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m)
- **cityscapesScripts** (evaluation tools) is MIT. This does not change the dataset terms. — [GitHub mcordts/cityscapesScripts](https://github.com/mcordts/cityscapesScripts)

### Inferences
- Commercially cleanest option: Grounding DINO (license to confirm) or SAM 3 text prompts ("tree", "car", "person", "sky", "sign", "awning") to get masks, refined by SAM 2.1 (Apache). Then mask out photo edges inside or at these regions, but only through the occluder interior: the wall/sky boundary is itself a wanted roof-line edge. So exclude edges where *both* sides are non-building, or dilate only vegetation/vehicle/person masks.
- DINOv2 (Apache) linear heads exist for ADE20K. The head weights inherit ADE20K NC concerns. Training an own linear head on DINOv2 features from self-labelled facade photos would be clean.
- Mask2Former/OneFormer Cityscapes/Vistas models are probably the most accurate for street scenes (urban classes, "vegetation", "car", "person", "sky"). Treat them as test-only ("NC-Werkzeuge nur zum Testen", per `modelle/LIZENZ_WERKZEUGE.md`) unless the dataset terms are cleared.

### Gaps
- Licenses of the Grounding DINO weights and the commercial status of the Vistas research edition were not verified from primary sources.
- No VRAM figures were collected. Mask2Former Swin-L at Cityscapes resolution and SAM 3 on an 8 GB GPU are unverified. SAM 2.1-hiera-large is commonly run on consumer GPUs (unverified).

## 4. Classifying edges as geometric vs texture (normals, depth, RIND)

### Takeaway
The most directly relevant idea is to compute photo "geometric edges" from predicted surface normals and depth, not from intensity. Normal discontinuities give creases (wall corners, window reveals, cornices), and depth discontinuities give occlusion boundaries (roof line against sky, protrusions). Shadows and stains barely change the predicted normals. Permissive options exist: StableNormal (Apache-2.0), Marigold (code Apache-2.0, normals weights OpenRAIL++), Metric3D v2 (BSD-2 code), Lotus (Apache-2.0), Depth-Anything-V2-Small (Apache). DSINE is explicitly non-commercial. A supervised four-class edge typer (RINDNet) and benchmark (BSDS-RIND) exist for reflectance/illumination/normal/depth edges.

### Cited Findings
- **RINDNet / BSDS-RIND** (ICCV 2021): detects and labels four edge types: reflectance (material and texture), illumination (shadows, highlights), normal (surface-orientation discontinuity) and depth. BSDS-RIND has 500 annotated BSDS images (300 train / 200 test). This taxonomy maps exactly to the wanted split: keep normal+depth, drop reflectance+illumination. — [arXiv 2108.00616](https://arxiv.org/pdf/2108.00616), [GitHub MengyangPu/RINDNet](https://www.github.com/MengyangPu/RINDNet)
- RINDNet repo license: the GitHub API returned "Not Found" (likely a case-sensitive repo name), so the license is unknown. Same author as EDTER (MIT); not verified. A follow-up, RINDNet++, also exists (same search).
- **DSINE** normals (Imperial College): custom licence, "solely for non-commercial, internal or academic research purposes", which explicitly forbids integration into products for sale and research to develop products for sale. — [LICENSE baegwangbin/DSINE](https://raw.githubusercontent.com/baegwangbin/DSINE/main/LICENSE)
- **Marigold**: code Apache-2.0. HF `prs-eth/marigold-normals-v1-1` is tagged openrail++, an RAIL license with use restrictions, generally allowing commercial use. — [GitHub prs-eth/Marigold](https://github.com/prs-eth/Marigold), [HF marigold-normals-v1-1](https://huggingface.co/prs-eth/marigold-normals-v1-1)
- **StableNormal**: code Apache-2.0; HF `Stable-X/stable-normal-v0-1` is tagged apache-2.0. It is a fine-tune of Stable Diffusion, so the base-model OpenRAIL terms may also apply (inference). — [GitHub Stable-X/StableNormal](https://github.com/Stable-X/StableNormal), [HF Stable-X/stable-normal-v0-1](https://huggingface.co/Stable-X/stable-normal-v0-1)
- **Metric3D v2** (depth + normals): "code is under a 2-clause BSD License. For further commercial inquiries, please contact..." No weights license is stated, and the HF repo `JUGGHM/Metric3D` has no license tag. Weights status is unclear. — [README YvanYin/Metric3D](https://github.com/YvanYin/Metric3D), [HF JUGGHM/Metric3D](https://huggingface.co/JUGGHM/Metric3D)
- **Lotus** (diffusion-based depth/normals): Apache-2.0 (code; weights not checked). — [GitHub EnVision-Research/Lotus](https://github.com/EnVision-Research/Lotus)
- **Depth Anything V2**: "Depth-Anything-V2-Small model is under the Apache-2.0 license. Depth-Anything-V2-Base/Large/Giant models are under the CC-BY-NC-4.0 license." — [README Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2), [HF Depth-Anything-V2-Large](https://huggingface.co/depth-anything/Depth-Anything-V2-Large)
- **Apple Depth Pro**: HF tag "apple-amlr" (Apple ML Research license). I did not read the text; it is likely research-only. — [HF apple/DepthPro](https://huggingface.co/apple/DepthPro)
- **Microsoft MoGe**: the GitHub API gave "NOASSERTION" (custom/mixed). Not checked further.

### Inferences
- Proposed geometric photo-edge pipeline:
  1. Predict normals N (StableNormal / Marigold-normals / Metric3D) and relative depth D (Depth-Anything-V2-Small, Apache).
  2. Edge strength = angle between neighbouring normals (e.g. > 20-30 degrees) plus relative depth jumps |dD|/D.
  3. Thin it with NMS and run the existing truncated chamfer distance against the rendered crease/depth edges. These are the *same physical edge classes* the model renders, so the comparison would be like-for-like.
- Alternatively, gate the existing Canny edges: keep a Canny pixel only if a normal or depth discontinuity lies within r pixels (r tied to the 7 cm scale). That keeps Canny's localization accuracy and drops shadow and stain edges.
- Expected weak spots: monocular normals smooth over shallow reliefs (window reveals of a few cm, flat pilasters), so small creases may be lost. Diffusion-based normal estimators hallucinate detail on texture; check this on the calibrated photos with the overlay view (project rule "Foto-Overlay zuerst"). Shadows of deep cornices can produce false normal edges in some models.
- RINDNet would be the direct "edge typer". It is trained on BSDS natural images only (500 images), so generalization to facades is doubtful and its license is unknown. Use it as a test tool at best.

### Gaps
- No quantitative study was found that measures how well monocular normal discontinuities recover architectural creases.
- VRAM and speed of StableNormal, Marigold and Metric3D v2 at 2-4 MP on 8 GB were not checked. The diffusion-based ones are likely slow (several seconds per image) but feasible with fp16 and tiling (inference).
- I did not look at other "structure vs texture edge" papers beyond RINDNet (e.g. occlusion-boundary nets such as DOC/DOOBNet, or the follow-up RINDNet++). Their licenses were not checked.
