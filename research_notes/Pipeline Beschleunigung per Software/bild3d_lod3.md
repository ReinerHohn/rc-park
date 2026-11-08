# Image-to-3D for ornaments and automatic LoD2->LoD3 / inverse procedural building modeling (2024-2026)

Context: H0 (1:87) printed buildings from photos + official LoD2/DOM1. Local GPU RTX 4060 Laptop 8 GB; RTX 4090/5090 rentable. Commercial sale from Germany/EU, so the EU-exclusion and revenue-cap clauses decide what can be used. Checked 2026-11-05. Tags: [verified] = read on the primary page in this session; [snippet] = from search summary/aggregator only; [unverified] = from model knowledge, not checked this session.

## (a) Image-to-3D generative models for small ornamental parts: license, VRAM, speed, quality, metric fidelity

### Takeaway
The models with clean commercial licenses are TRELLIS.2 (MIT, code+weights), TripoSG/PartCrafter (MIT), Direct3D-S2 (MIT), Step1X-3D (Apache-2.0) and TripoSR (MIT). Of these, only TripoSG, PartCrafter and TripoSR fit on 8 GB without compromises; TRELLIS.2 and Step1X-3D need a rented 24-32 GB GPU. Hunyuan3D 2.x is **legally unusable in the EU**: its license territory explicitly excludes the EU. Stability models (SF3D/SPAR3D) are usable only while the seller earns under USD 1 M/year. None of the models gives metric scale, so every output must be rescaled to a measured bounding box, which matches the planned approach.

### Cited Findings
**TRELLIS.2 (Microsoft, arXiv 2512.14692)**
- Code **and weights** are MIT ("This model and code are released under the MIT License"). Dependencies such as nvdiffrast/nvdiffrec carry their own licenses (nvdiffrast is NVIDIA-licensed and possibly non-commercial [unverified]; check it before selling) — [GitHub microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2) [verified]
- 4B parameters. Officially needs **>=24 GB VRAM** (verified on A100/H100). On an H100 it takes about 3 s at 512³, 17 s at 1024³ and 60 s at 1536³. Output is a GLB with PBR materials. Its O-Voxel representation handles open surfaces, non-manifold geometry and internal enclosed structures. The page does **not** promise watertight output — [GitHub microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2) [verified]
- Low-VRAM community ComfyUI workflows claim 8-10 GB. One Reddit user reported a 3060 run at 1024 taking 13 min. A third-party site claims about 120 s at 1024³ on a 4060 in low-VRAM mode, but its own pages contradict each other. No official GGUF build was found — [trellis2.app low VRAM](https://trellis2.app/blog/trellis-2-low-vram), [Reddit snapshot](https://reddit.sentinel-team.org/posts/1su7mdv/snapshots/2026-04-24T21%3A23%3A19.131371Z) [snippet, low reliability]
- TRELLIS v1 (2024) is also MIT; its small models fit roughly 16 GB [unverified].

**SAM 3D Objects (Meta, Nov 2025)**
- Code and checkpoints are under the "SAM License". The grant is worldwide, non-exclusive and royalty-free, with no explicit ban on commercial use and no EU exclusion — [LICENSE](https://raw.githubusercontent.com/facebookresearch/sam-3d-objects/main/LICENSE) [verified]
- Conditions: Trade Controls; no military/nuclear/espionage/weapons use; no reverse engineering; a copy of the agreement must ship with any redistribution; indemnification of Meta; Meta may modify the agreement; California law governs — [LICENSE](https://raw.githubusercontent.com/facebookresearch/sam-3d-objects/main/LICENSE) [verified]
- Main output is a **Gaussian splat (PLY)**, not a mesh. It recovers shape, texture, layout and pose, and is designed for "real-world scenarios with occlusion and clutter" and small objects. This makes it the only candidate built for objects in scenes, such as statues in niches. The README states neither VRAM, runtime nor metric scale — [GitHub sam-3d-objects](https://github.com/facebookresearch/sam-3d-objects) [verified]

**Hunyuan3D 2.0 / 2.1 / 2mini (Tencent)**
- License territory is "worldwide ... **excluding the territory of the European Union, United Kingdom and South Korea**". The preamble says the agreement "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA". Above 1 M MAU a separate license is required — [HF Hunyuan3D-2.1 LICENSE](https://huggingface.co/tencent/Hunyuan3D-2.1/blob/main/LICENSE) [verified]
- 2mini (0.6B) shape generation takes about 5-6 GB VRAM; shape plus texture about 12 GB. Released 18 Mar 2025 — [GitHub Tencent/Hunyuan3D-2](https://github.com/Tencent/Hunyuan3D-2), [DeepWiki](https://deepwiki.com/Tencent/Hunyuan3D-2/2.1-installation) [snippet]
- For Hunyuan3D 2.5 only the tech report was found (arXiv 2506.16504). Open weights or a license for 2.5/3.0 could not be confirmed — [arXiv 2506.16504](https://web3.arxiv.org/abs/2506.16504) [snippet]

**Stability: Stable Fast 3D (SF3D), SPAR3D**
- Stability AI Community License: free commercial use only up to **USD 1,000,000 annual revenue** (including affiliates). Above that, a license must be requested and is granted at Stability's discretion. No geographic exclusion. The user owns the outputs — [Stability Community License](https://stability.ai/community-license-agreement) [verified]
- SF3D: about 0.5 s per asset on a GPU with 7 GB VRAM. It is built on TripoSR but fully retrained — [Stability news](https://stability.ai/news/introducing-stable-fast-3d) [snippet]
- SPAR3D: about 10.5 GB VRAM by default, about 7 GB in low-VRAM mode (slower); elsewhere the README says about 6 GB for one image (contradictory). Outputs GLB, with optional triangle/quad remesh — [GitHub stable-point-aware-3d](https://github.com/Stability-AI/stable-point-aware-3d) [verified]

**TripoSR, TripoSG, PartCrafter (VAST and partners)**
- TripoSR is MIT and runs in under 1 s. Its VRAM need is listed as 6-8 GB on aggregators. Quality is low (2024 generation) — [analyticsvidhya](https://www.analyticsvidhya.com/blog/2024/03/stability-ais-triposr-from-image-to-3d-model-in-seconds/), [ai-tools-finder](https://ai-tools-finder.pages.dev/tools/triposr) [snippet]
- TripoSG (1.5B rectified flow, SDF): MIT per the HF card. The official requirement is ">=8 GB VRAM". One user reported 1 min 15 s and 7.4 GB on a 3060 Ti 8 GB. Out-of-memory reports concern the texturing step, not the shape model — [HF TripoSG README](https://huggingface.co/gen-lab/TripoSG/blob/main/README.md), [Reddit](https://redlib.cypherpunktools.com/r/StableDiffusion/comments/1jpl4tm/open_sourcing_triposg_highfidelity_3d_generation), [HF Space discussion](https://huggingface.co/spaces/VAST-AI/TripoSG/discussions/6) [snippet]
- PartCrafter: MIT, ">=8 GB VRAM". It fine-tunes TripoSG's DiT and keeps the VAE fixed. The part count is set with `--num_parts` or suggested by a VLM, and it also handles scenes — [GitHub wgsxm/PartCrafter](https://github.com/wgsxm/PartCrafter) [verified]. TripoSG's base weights are MIT, so the chain stays MIT [inference].

**Step1X-3D (StepFun), Direct3D-S2**
- Step1X-3D is **Apache-2.0**; the README does not mention separate weight terms. VRAM is about 27 GB (geometry 1.3B + texture) or about 29 GB (label variant). It takes about 152 s for 50 steps (GPU not named). The geometry stage "produces watertight TSDF representations" — [GitHub stepfun-ai/Step1X-3D](https://github.com/stepfun-ai/Step1X-3D) [verified]
- Direct3D-S2 is MIT. It needs >=10 GB VRAM at 512³ and about 24 GB at 1024³ — [search summary of the repo / ar5iv 2505.17412](https://ar5iv.labs.arxiv.org/html/2505.17412) [snippet]

**InstantMesh (TencentARC)**
- My recollection is Apache-2.0 code; best quality is said to need 24 GB+ and about 1 min. **Neither was verified** — [pixazo comparison](https://www.pixazo.ai/blog/?p=2770888) [snippet/unverified]. It depends on Zero123++ multiview, whose weights license should be checked separately [unverified].

### Inferences
- **EU-compatible shortlist for selling:** TRELLIS.2 (MIT; check nvdiffrast), TripoSG/PartCrafter (MIT), Direct3D-S2 (MIT), Step1X-3D (Apache), TripoSR (MIT). SAM 3D Objects is probably usable commercially, but the license is custom, revocable/modifiable and carries indemnity, so it belongs in the "examine before sale" class (`modelle/LIZENZ_WERKZEUGE.md`). **Exclude Hunyuan3D 2.x entirely** in the EU, even for testing if the results enter the product. SF3D/SPAR3D only while revenue stays under USD 1 M.
- **Hardware split:** the local 4060 (8 GB) can run TripoSG/PartCrafter (shape only) and TripoSR/SF3D. TRELLIS.2 at 1024³, Step1X-3D and Direct3D-S2 at 1024 belong on a rented 4090 (24 GB) or 5090 (32 GB). Batch all ornament crops per city in one rented session.
- **Scale at H0:** a 2 m statue prints at about 23 mm, not 2.3 mm (2000/87 = 23 mm; the brief's "2.3 mm" looks like a slip unless 1:870 was meant). At 23 mm and an FDM/resin resolution of about 0.1-0.4 mm, a 512³ voxel grid already resolves more than any printer can. High-resolution TRELLIS.2 runs are therefore unnecessary for ornaments; small, fast models suffice. Coats of arms 0.5-1 m wide (6-12 mm printed) are nearly pure relief, so a depth-map or relief extrusion is probably sufficient and more faithful than generative 3D.
- **Relief/attached objects:** all these generators assume a complete, free-standing object and hallucinate the hidden back side. For wall-attached parts, the safe procedure would be: segment the crop (SAM 2/3), generate, cut the mesh at the wall plane known from LoD2/facade geometry, then scale it to the box measured with `foto_mass.py`. SAM 3D Objects is the only model claimed to handle occlusion in context, but it outputs splats, so a meshing step (for example Poisson or TSDF) is needed.
- **Watertightness:** SDF/TSDF-based models (TripoSG, Step1X-3D, Direct3D-S2) should give closed surfaces by construction. TRELLIS.2 explicitly allows open and non-manifold surfaces, so repair is needed before the manifold3d boolean (manifold3d already rejects non-manifold input).
- **Metric fidelity:** single-image generators have no metric scale and unreliable proportions in depth. Under the project rules (Register CB, Quellen-Blindheit) such output can only be a form proposal ("Formvorschlag") with `ANNAHME:` labels and must be checked against `foto_diff.py`. It can never serve as a measurement source.

### Gaps
- No independent benchmark of these models on relief or wall-attached architectural ornaments was found. Quality has to be tested on our own crops (Martinstor coats of arms and statues).
- VRAM and runtime of SAM 3D Objects were not stated in the README.
- InstantMesh license/VRAM and the nvdiffrast license were not verified in this session.
- Hunyuan3D 2.5/3.0 weight availability is unknown; the EU exclusion probably continues.
- No official 8 GB build of TRELLIS.2 exists; community claims are inconsistent.

## (b) Automatic LoD2->LoD3, inverse procedural modeling and commercial tools: what could replace hand modeling of oriels with helm roofs, stepped gables and arcades?

### Takeaway
No published method or tool, academic or commercial, produces a watertight, detailed LoD3 from photos + LoD2 that covers oriels, helm roofs, stepped gables or arcades. The state of the art (Scan2LoD3, Texture2LoD3, the 2026 ISPRS spherical-panorama pipeline) does **2.5D facade work**: it detects and cuts windows and doors into LoD1/LoD2 planes and sometimes adds shallow depth. Inverse procedural methods (FaçAID, Pro-DG, the 2025 point-cloud-to-program transformer) recover 2D facade split grammars or coarse building programs. LLM-to-code reconstruction (CAD-Recode, MeshCoder, 3D-CoS) is the most promising route to "parametric part from evidence", but none of it is building-specific. The project's approach (parametric generator plus measurement table) is therefore not obsolete. These methods can automate sub-steps: opening detection and facade rectification, and possibly fitting parameters of a component library.

### Cited Findings
**LoD3 from images / point clouds**
- **Scan2LoD3** (Wysocki et al., TUM, CVPRW 2023): proposes openings from ray-casting conflicts between MLS rays and the LoD2 model, fuses them with point clouds and images (Mask R-CNN) in a Bayesian network, cuts the openings into the LoD2 prior, and fits objects from a facade-object library. The code combines C++ ray casting, Python, R and **FME** (commercial) for CityGML output. It needs MLS laser data — [GitHub OloOcki/scan2lod3](https://github.com/OloOcki/scan2lod3), [CVPRW paper](https://openaccess.thecvf.com/content/CVPR2023W/PCV/papers/Wysocki_Scan2LoD3_Reconstructing_Semantic_3D_Building_Models_at_LoD3_Using_Ray_CVPRW_2023_paper.pdf) [snippet]
- **MLS2LoD3** (Feb 2024) refines low-LoD models with mobile laser scanning — [arXiv 2402.06288](https://www.arxiv.org/abs/2402.06288) [snippet]
- **Texture2LoD3** (CVPRW 2025): LoD3 from **panoramic street images**, using low-LoD models as planar targets for ortho-texturing. Releases the ReLoD3 dataset; reports +11 % facade segmentation accuracy — [arXiv 2504.05249](https://arxiv.org/html/2504.05249v1) [snippet]
- **"Spherical Vision meets 3D Semantics" (Saadatseresht, Arefi, Askari; Univ. Tehran + i3mainz Mainz; ISPRS Congress 2026)**: LoD1 (OSM) to LoD3 facades from **Mapillary panoramas** plus a weak point-cloud prior. Each facade is processed separately: rectification into fronto-parallel images, visibility-driven view selection, multi-view fusion, a 2.5D depth field (ray consistency + appearance + point support + regularization), planar segmentation and polygonization, and opening detection under architectural constraints. The output is a **2.5D facade** relief per wall plane, not free 3D (no oriels or helms). CC BY 4.0 — [ISPRS Archives XLIX-B2-2026-539](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/539/2026/isprs-archives-XLIX-B2-2026-539-2026.pdf) [verified, pp. 1-2 read]
- **SI3FP** (Aug 2025): image-to-3D facade parser for thermal LoD3 (window-to-wall ratio) — [arXiv 2508.04406](https://arxiv.org/abs/2508.04406v1) [snippet]
- Kim et al. (ISPRS 2025): automated LoD3 from **oblique UAV images** with deep-learning window detection. They note that LiDAR usually stays at LoD2 because facade point density is too sparse — [ISPRS XLVIII-G-2025-797](https://isprs-archives.copernicus.org/articles/XLVIII-G-2025/797/2025/isprs-archives-XLVIII-G-2025-797-2025.pdf) [snippet]
- Roof superstructures: Xu et al. 2024 reconstruct LoD2.2 with dormers from DSM+RGB. Roof-vertex mAP is 64.3 % on their own dataset but roof-plane mAP only 12.4 % on Roof3D — [JAG 2024 / DOAJ](https://doaj.org/article/1bdcfde074f242c1adb99cb5c8ad7af4) [snippet]. Li et al. 2026 reach 3D roof-plane recall of 0.43 — [ISPRS XLIX-B2-2026-459](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/459/2026/) [snippet]
- Pantoja-Rosero et al. (2022, EPFL) produce LoD3 from SfM + opening segmentation — cited via [ISPRS XLVIII-G-2025-797](https://isprs-archives.copernicus.org/articles/XLVIII-G-2025/797/2025/isprs-archives-XLVIII-G-2025-797-2025.pdf) [snippet]

**Inverse procedural / neural-symbolic**
- Wu et al. 2013/14, "Inverse Procedural Modeling of Facade Layouts": derives a split grammar from a segmented facade (MDL cost, approximate DP) — [arXiv 1308.0419](https://arxiv.org/pdf/1308.0419) [snippet]
- **FaçAID** (2024): a transformer converts segmented facades into procedural split-grammar definitions; includes a dataset — [arXiv 2406.01829](https://arxiv.org/pdf/2406.01829) [snippet]
- **Pro-DG** (Apr 2025): reconstructs a facade grammar from one image, edits it, then renders with diffusion. 2D only — [arXiv 2504.01571](https://arxiv.deeppaper.ai/papers/2504.01571v1?locale=en) [snippet]
- **"Synthesizing 3D Abstractions by Inverting Procedural Buildings with Transformers"** (Jan 2025): point cloud to a programmatic building description, trained on synthetic procedural buildings. The output is coarse abstractions — [arXiv 2501.17044](https://arxiv.org/html/2501.17044v1) [snippet]
- LLM/code reconstruction, general purpose:
  - **CAD-Recode** (ICCV 2025) maps point clouds to CadQuery Python, trained on about 1 M procedural sketch-extrude sequences — [arXiv 2412.14042](https://arxiv.org/abs/2412.14042v2)
  - **MeshCoder** (2025) maps point clouds to part-based Blender Python (41 categories) — [arXiv 2508.14879](https://arxiv.org/html/2508.14879v1)
  - **3D-CoS** (2026) maps a single image to Blender Python via a VLM agent that repairs its own code — [arXiv 2606.10478](https://arxiv.org/pdf/2606.10478)
  - **StepCAD** (NeurIPS 2026) does mesh-to-CAD with IoU-guided tree search — [NeurIPS](https://neurips.cc/virtual/2026/poster/149665)
  - **Zero-to-CAD** (2026) does agentic CAD synthesis at million scale — [arXiv 2604.24479](https://arxiv.org/pdf/2604.24479)
  - All [snippet]; none is building-specific.

**Geometric reconstruction tools (point cloud to watertight polyhedra)**
- PolyFit (Nan & Wonka, ICCV 2017) is **GPL-3.0**; it has been in CGAL since 2019 — [ecosyste.ms PolyFit](https://awesome.ecosyste.ms/projects/github.com%2FLiangliangNan%2FPolyFit) [snippet]
- CGAL **Kinetic Surface Reconstruction** (CGAL 6.0+) is **GPL** (CGAL is also sold under a commercial license [unverified]). Pipeline: shape detection, regularization, kinetic partition, graph-cut. A `ksr_building.cpp` example exists — [CGAL KSR doc](https://doc.cgal.org/latest/Kinetic_surface_reconstruction/Kinetic_surface_reconstruction_2ksr_parameters_8cpp-example.html) [snippet]
- City3D (Huang, Nan et al. 2022, aerial LiDAR to LoD2) depends on these components; its own license was **not verified**.

**Commercial**
- **RealityScan 2.x (formerly RealityCapture, Epic)**: free under USD 1 M annual gross revenue, otherwise USD 1,250 per seat per year. Version 2.0 (June 2025) needs a new EULA and the Epic Launcher — [realityscan.com download](https://www.realityscan.com/en-US/download), [RealityScan 2.0 news](https://www.realityscan.com/news/realityscan-20-new-release-brings-powerful-new-features-to-a-rebranded-realitycapture), [CG Channel Nov 2025](https://www.cgchannel.com/?p=172238) [snippet]. It is photogrammetry (mesh), not LoD3 semantics.
- Esri CityEngine (CGA rule-based procedural modeling) and Agisoft Metashape: no current license or price check was done this session [unverified]. CityEngine generates from hand-written rules; it does not infer rules from photos.

### Inferences
- **Stepped gables, arcades, window rows:** these are the parts where inverse-procedural ideas fit best. They are repetitive and fit a split grammar (FaçAID/Wu style). A practical route is to rectify the facade from LoD2 planes plus calibrated photos (as in the ISPRS 2026 pipeline, which uses the same Mapillary source as this project), count with `foto_zaehlung.py`, and fill grammar parameters (step count, rise, arch spacing) into existing generator components. This stays data-driven and testable; no off-the-shelf model does it end to end.
- **Oriels with helm roofs and towers:** no LoD3 method handles free-standing 3D superstructures. Options:
  - (1) Fit a parametric component (prism + helm, with `bauteile.py`) to the photo silhouette by optimization, roughly as already done.
  - (2) Try LLM/VLM-to-code (3D-CoS/MeshCoder-style) as a proposal generator for component parameters. This is research grade, but it fits the "everything automatic" rule.
  - (3) Use an image-to-3D mesh (TRELLIS.2/TripoSG) only as a form prior, cut and scaled by the LoD2/DOM1 box. Risk: hallucinated symmetry or proportions.
- **Licensing:** GPL tools (PolyFit, CGAL KSR) can be used internally to make models. Selling the printed model or STL output is not affected by the GPL; distributing the software itself would be [inference, not legal advice]. Scan2LoD3 depends on FME (commercial).
- **Quality gap:** the reported metrics (roof-plane mAP 12.4 %, 3D roof recall 0.43) show that automatic roof-detail recovery is still weak. Results should go through the measurement table and test bench (Masstabelle/Pruefstand) rather than be trusted directly.

### Gaps
- No 2024-2026 paper was found that reconstructs **oriels, helm roofs or stepped gables** as 3D objects automatically, nor any method that uses an LLM to infer building grammars from images.
- Code availability and licenses for Texture2LoD3, the ISPRS 2026 spherical pipeline, FaçAID, Pro-DG and arXiv 2501.17044 were not checked.
- City3D and 3DBAG (NL) licensing and methods were not researched in detail this session. 3DBAG is LoD2.2 only [unverified].
- No current CityEngine or Metashape pricing or license terms were retrieved.
