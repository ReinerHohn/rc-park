# Faster analysis-by-synthesis fitting: a procedural CSG building model against calibrated photos

Context assumed throughout: manifold3d CSG on the CPU, 1-3 s per build; 10-30 continuous parameters plus discrete elements; an exact GPU edge rasterizer over 12-20 photos; truncated symmetric chamfer distance computed from distance transforms; CMA-ES (pycma) at about 4.5 min per generation; RTX 4060 Laptop with 8 GB; commercial sale planned.
Research date: 2026-11-05. About 15 tool calls, so many points are marked as unverified.

## 1. Differentiable rasterizers: licenses, and whether gradients can flow through edge/silhouette chamfer losses

### Takeaway
nvdiffrast is still under the NVIDIA Source Code License, non-commercial only. It is fine for testing, but it cannot go into a product. Mitsuba 3 / Dr.Jit (BSD-3), PyTorch3D (BSD), Kaolin (Apache-2.0) and gsplat (Apache-2.0) can all be used commercially. Silhouette and edge gradients need special handling at visibility discontinuities. The options are antialiasing (nvdiffrast, DiffCSG), soft rasterization (PyTorch3D SoftRas), projective edge sampling (Mitsuba 3) and "micro-edges" (Pidhorskyi et al. 2024).

### Cited Findings
- **nvdiffrast LICENSE.txt** is the "NVIDIA Source Code License (1-Way Commercial)". §3.3 says: "The Work and any derivative works thereof only may be used or intended for use non-commercially". Non-commercially means "for research or evaluation purposes only". The file says nothing about Apache relicensing. — [nvdiffrast LICENSE](https://github.com/NVlabs/nvdiffrast/blob/main/LICENSE.txt)
- A search for an Apache relicensing of nvdiffrast found no evidence. — [search, no hit](https://github.com/NVlabs/nvdiffrast)
- **Kaolin** (NVIDIA) LICENSE is Apache 2.0 with no non-commercial restriction. Whether optional kaolin code paths call nvdiffrast was not checked. — [Kaolin LICENSE](https://github.com/NVIDIAGameWorks/kaolin/blob/master/LICENSE)
- **PyTorch3D** is "released under the BSD License". The latest release named in the README is v0.7.5 (31 Oct 2023), so releases are slow, and the README warns "Anything can be broken at any time". — [PyTorch3D GitHub](https://github.com/facebookresearch/pytorch3d)
- **Dr.Jit** (Mitsuba 3 backend) is BSD-3-Clause. It JIT-compiles to CUDA or LLVM and has forward- and reverse-mode AD. — [Dr.Jit GitHub](https://github.com/mitsuba-renderer/drjit)
- **Mitsuba 3 projective sampling** (Zhang, Roussel, Jakob, TOG Dec 2023) handles visibility discontinuities. It collects paths near a boundary during the forward pass and projects them onto the silhouette. Each shape type needs its own projection operator. The integrators are `direct_projective` (direct light only) and `prb_projective`. — [Mitsuba docs](https://mitsuba.readthedocs.io/en/latest/src/inverse_rendering/projective_sampling_integrators.html); [paper](https://ziyi-zhang.github.io/papers/html/projective-sampling/index.html)
- **Rasterized Edge Gradients** (Pidhorskyi et al., Meta, arXiv 2405.02508, v4 July 2024) uses "micro-edges" for gradients at visibility discontinuities. It leaves the forward rasterization unchanged, with no blur or filtering, and works for masks, depth and normals, including geometry intersections. The paper calls silhouette edge sampling (as in Mitsuba-type methods) "a significant bottleneck". No code release was found. — [arXiv 2405.02508](https://arxiv.org/abs/2405.02508)
- **gsplat** is Apache-2.0 (Nerfstudio). It is a Gaussian splatting rasterizer, not a mesh rasterizer. — [gsplat topic](https://www.emergentmind.com/topics/gsplat-apache-2-0) (secondary source; check the LICENSE in the repo)

### Inferences
- Chamfer from a distance transform is differentiable on the model side: dC/dx = gradient of DT_photo at the rendered edge pixel times d(pixel)/d(parameter). The photo DT is a fixed image, so only the positions of the model edges need gradients. That makes it simpler than a full image-space visibility gradient: project crease and silhouette edges analytically as 3D line segments, sample points on them, look up `grid_sample(DT_photo)`, and the gradient comes out exactly. Visibility (occlusion) only acts as a per-sample mask treated as constant, which is a standard approximation. This "edge-sampling chamfer" needs no differentiable rasterizer and therefore carries no license problem. Plain PyTorch (BSD) is enough.
- The reverse term, photo edge to model DT, does need a DT of the rendered image. A DT is not differentiable in its input mask. Either keep it frozen per iteration (alternating, ICP style) or use soft rasterization.
- nvdiffrast is fine as a test oracle in a research branch (per LIZENZ_WERKZEUGE.md), but not as a product dependency.

### Gaps
- Kaolin's own rasterizer (DIB-R) and its edge-gradient quality were not checked; nor whether kaolin pulls in nvdiffrast internally.
- No numbers found for VRAM at 86 MP with PyTorch3D or Mitsuba. Inference: PyTorch3D's per-pixel K-face buffers (`faces_per_pixel`) at 86 MP would very likely blow 8 GB, so tiling or a lower resolution would be needed.
- No code repo found for micro-edges.

## 2. Differentiable CSG / procedural modeling

### Takeaway
DiffCSG (SIGGRAPH Asia 2024) is the closest match. It is a differentiable CSG rasterizer (Goldfeather, no mesh boolean) on top of nvdiffrast that fits 3-22 continuous parameters with Adam, and 62 % of its shapes finish in under 10 s. It inherits nvdiffrast's NC license and cannot change discrete structure. A commercial route would be to reimplement the idea in Dr.Jit/PyTorch, or to use an SDF-CSG generator with edge sampling.

### Cited Findings
- **DiffCSG** (Yuan, Bousseau, Pan, Zhang, Mitra, Li; SIGGRAPH Asia 2024, arXiv 2409.01421) renders CSG through Goldfeather rasterization using depth and parity tests, with no explicit boolean mesh. It is built on nvdiffrast and adds antialiasing along primitive intersections so that gradients exist there. — [arXiv html](https://arxiv.org/html/2409.01421v2)
  - Time per iteration: Bike 0.345 s (2,980 triangles, 17 parameters), RaceCar 0.557 s (4,336 triangles, 22 parameters), Moon/Nut about 0.06 s.
  - Adam, lr 1e-3, up to 5,000 steps, stopping early when loss < 5e-4. Loss is L1/L2 on normal or colour images at 512×512, averaged over several views.
  - 62 % of shapes finish in under 10 s and 29 % in under 100 s; the bike can take up to 1,000 s (Fig. 7).
  - Limitations: no change of structure (primitive types or boolean operations), local minima depending on initialisation, primitives that shrink to zero lose their gradient for good, failure when the target is far away, and the authors call the Goldfeather/edge code unoptimised.
  - Code and data: [project page](https://yyyyyhc.github.io/DiffCSG) (license not checked).
- **Automatic Differentiable Procedural Modeling** (Gaillard et al., CGF 2022) is a node-based engine that builds a differentiable graph for 3D geometry and comes with its own optimiser for inverse procedural modeling. — [PDF](https://www.cs.purdue.edu/homes/bbenes/papers/Gaillard22CGF.pdf)
- **Node Graph Optimization Using Differentiable Proxies** (Hu et al., SIGGRAPH 2022) replaces non-differentiable nodes with neural proxies, then switches back to the original nodes after optimisation. It targets material graphs. Code: github.com/yiwei-hu/DiffProxy. — [arXiv 2207.07684](https://arxiv.org/pdf/2207.07684)
- **Fuzzy boolean** (Toronto DGP) is one differentiable boolean operator that is also differentiable with respect to the boolean type. Venue and year were not confirmed. — [PDF](https://www.dgp.toronto.edu/~hsuehtil/pdf/fuzzyBoolean.pdf)

### Inferences
- manifold3d itself is not differentiable. For continuous parameters that only move vertices (wall offset, niche depth, roof offset), the topology stays the same over small steps. In that case dVertex/dParameter can be computed cheaply by finite differences on the vertex positions, with the same mesh topology and no rendering. Combined with the analytic edge-sampling chamfer from section 1, this gives a gradient for N parameters from N extra builds instead of N extra full renders and measurements. Builds can run in parallel on the CPU; the GPU cost of each step drops to a single measurement. Whether the topology really stays stable has to be checked per parameter (vertex count and face order must not change). This is unverified.
- An SDF-CSG generator (PyTorch/Warp/JAX) plus marching cubes would be differentiable, but it gives up exact sharp edges. For a building model judged by edges, that is probably a step backwards.
- Discrete elements stay with CMA-ES or a discrete search. A gradient method only makes sense as an inner loop for the continuous parameters (hybrid).

### Gaps
- "ShapeAssembly" and "Infinigen inverse" were not researched (budget).
- 2025 papers on differentiable mesh booleans: none found in one search.

## 3. Black-box speedups (evosax, surrogates/BO, multi-fidelity, caching, separability)

### Takeaway
At 4.5 min per generation the wall time is dominated by evaluation, not optimiser overhead. A GPU CMA-ES (evosax) therefore brings almost nothing. What saves time is fewer or cheaper evaluations: surrogate-assisted CMA-ES (lq-CMA-ES, built into pycma), a coarse-to-fine image pyramid, and partial caching.

### Cited Findings
- **evosax** (JAX) license: the GitHub sidebar says **Apache-2.0**, while a third-party page says MIT. GitHub is the primary source. It includes CMA-ES, Sep-CMA-ES, LM-MA-ES, MA-ES, CR-FM-NES and SV-CMA-ES; current version is v0.3.2. The repo shows no benchmark against pycma. — [evosax GitHub](https://github.com/RobertTLange/evosax); contradicted on the license by [SourcePulse](https://www.sourcepulse.org/projects/2182768)
- The only "5-10× faster than pycma" figure found is from a project planning document, not a measurement. — [jax_mppi plan](https://riccardo-enr.github.io/jax_mppi/plan/completed/evosax_integration.html) (unverified)
- **lq-CMA-ES** (Hansen, GECCO 2019) fits a global linear or quadratic surrogate (pseudoinverse) that grows from linear to diagonal to full quadratic as data allows, and saves true evaluations. It is built into pycma as `cma.fmin_lq_surr2` with `maxfevals`. Caveat: in the legacy API, `es.best` can be the best surrogate value rather than a true one. — [lq-cma](https://cma-es.github.io/lq-cma); [GitHub](https://github.com/CMA-ES/lq-cma); [pycma docs](https://tessl.io/registry/tessl/pypi-cma/4.3.0/files/docs/advanced-optimization.md); [DOI](https://dx.doi.org/10.1145/3321707.3321842)
- An example run: lq-CMA-ES on 10-D Rosenbrock reached ftarget 1e-11 after 1,177 evaluations. No baseline is shown. — [lq-cma](https://cma-es.github.io/lq-cma)
- A 2025 rank-based variant "falls short to entirely meet the lq-CMA-ES performance levels". — [IP Paris](https://researchportal.ip-paris.fr/en/publications/rank-based-linear-quadratic-surrogate-assisted-cma-es/)

### Inferences
- With n=10-30, a full quadratic surrogate needs (n+1)(n+2)/2 points: 66 for n=10 and 496 for n=30. For 30 parameters only the linear/diagonal model kicks in early. A truncated chamfer is not quadratic far from the optimum, so the gain is largest near the end. This is unverified for our cost function; a test on the existing versuche.jsonl logs is the next step.
- **BoTorch** (MIT, not re-checked in this session) or a GP-BO pays off for evaluations of minutes and up to about 20 dimensions. At 30 dimensions plus discrete parameters, standard GP-BO gets weak. Possible options are TuRBO or SAASBO (both in BoTorch); no numbers checked.
- **Multi-fidelity / pyramid:** chamfer on a downscaled image is not lossless. (a) Edge positions get quantised to the coarser pixel, so the cost surface is flat below about 1 px of the coarse level. (b) Close parallel edges (window frames, niche jambs) merge or disappear in edge detection, so fine parameters lose their signal. (c) The truncation radius has to scale too. Sensible order: coarse level (about 1/4 linear, about 5 MP) for global parameters (wall and roof offsets), full resolution only in the last generations, or only in ROI crops around fine elements (windows, niches). Crops instead of full frames also solve the 7 GB VRAM peak at 86 MP.
- **Caching:** the photo-side DTs and edge maps are independent of the parameters and only need computing once per photo; whether that already happens should be checked in the code. Per-element caching of the CSG (unchanged sub-solids) only pays off if the generator is built as a tree of reusable `Manifold` objects.
- **Separability:** coordinate-wise search (1-D line search per parameter) suits locally separable parameters (window scale vs roof offset, different faces). Correlated parameters (wall offset and niche depth on the same face) should be grouped. A practical scheme is block-coordinate: CMA-ES per group of 3-6 parameters, with fewer photos per group (only the photos that see that face). This is an inference, no literature number.

### Gaps
- No independent evosax-vs-pycma benchmark.
- No concrete speedup factors for lq-CMA-ES from the GECCO paper were retrieved (only the COCO data archive is linked). Do not quote figures from memory.

## 4. GPU distance transform / chamfer

### Takeaway
Kornia is Apache-2.0 (0.9.0rc1, July 2026) and has `kornia.contrib.distance_transform`, but whether it is exact or fast enough at 86 MP was not verified. For truncated chamfer, an exact Euclidean DT is not needed beyond the truncation radius τ, so an iterative or banded DT, or tiling with a τ-wide halo, is enough.

### Cited Findings
- Kornia is Apache 2.0; latest PyPI release 0.9.0rc1 of 19 July 2026. — [kornia GitHub](https://github.com/arraiyopensource/kornia); [PyPI stats](https://pepy.tech/project/kornia)
- `distance_transforms` (Molloi Lab) is a separate GPU DT package for Python and Julia (CUDA, ROCm, Metal, oneAPI); license not confirmed. — [DistanceTransforms.jl](https://molloilab.github.io/DistanceTransforms.jl)

### Inferences
- Tiling: a truncated DT with radius τ only needs a halo of τ pixels per tile, so tiles of e.g. 4096² with τ=32 halo give the same result as the whole image and cap VRAM, losslessly.
- fp16 for DT values: with τ ≤ 64 px, fp16 (exact for integers up to 2048, 10-bit mantissa) is enough for chamfer sums per pixel; accumulate the sums in fp32. Edge masks as uint8 or bool cut memory by 4× compared with float32.
- Photo DTs are constant, so compute them once, store as uint8 (clipped to τ), and the per-candidate GPU work drops to rendering the model plus gathering. Only the reverse term (photo to model) needs a DT of each render; it could be replaced by sampling photo edge points and looking them up in the model DT, done at coarse resolution.
- cupy / `cupyx.scipy.ndimage.distance_transform_edt` exists (MIT; not re-checked in this session).

### Gaps
- No measured runtimes or VRAM figures for kornia DT at 86 MP.

## 5. Expected speedups: gradient methods vs CMA-ES at 10-30 parameters

### Takeaway
No direct literature comparison of gradient vs CMA-ES for 10-30-dimensional render fitting was found. The one concrete figure is from DiffCSG: about 0.06-0.56 s per Adam step and usually under 10-100 s total for 3-22 parameters at 512² and a few views. Against the current 4.5 min per generation, that points to one to two orders of magnitude, but only near a good initialisation and only for continuous parameters.

### Cited Findings
- DiffCSG: 3-22 parameters, 62 % under 10 s, 29 % under 100 s, up to 1,000 s for a complex bike; it can get stuck in local minima and fails when the target is far away. — [arXiv html](https://arxiv.org/html/2409.01421v2)

### Inferences
- Plausible hybrid: CMA-ES (possibly lq-surrogate) at a coarse pyramid level for global search and discrete elements, then gradient refinement (finite-difference vertex Jacobian plus analytic edge-sampling chamfer, sections 1/2) at full resolution in ROIs. Per gradient step: N parallel CPU builds (vertices only, no render) plus one GPU measurement, instead of λ (typically 4+3 ln n ≈ 14-15 for n=20) full renders × 12-20 photos.
- Truncated chamfer has zero gradient outside τ. Use a large τ for the gradient phase or the coarse phase and shrink τ as the fit converges.

### Gaps
- No benchmark comparing CMA-ES vs Adam in evaluations-to-target for silhouette or edge fits of similar dimension was found; it would have to be measured on our own versuche.jsonl.
