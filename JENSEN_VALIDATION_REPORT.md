# Jensen / Mosetti / Grady validation mode

## Scope

WFLOP now uses the Jensen top-hat wake and the dimensionless paper cost model in the optimizer and simulator path. This is a validation mode, not a claim that the models are suitable replacements for the existing offshore design model.

Sources read:

- Jensen, *A note on wind generator interaction* (Risø-M-2411, 1983), especially wake model, multiple wakes, and entrainment constant (`document-jensen/jensen.md`, pp. 5–14).
- Mosetti, Poloni & Diviacco, *Optimization of wind turbine positioning in large windfarms by means of a genetic algorithm* (1994), §§2 and 4 (`document-jensen/mosetti.md`, lines 58–116 and 197–216).
- Grady, Hussaini & Abdullah, *Placement of wind turbines using genetic algorithms* (2005), §2 and §4 (`document-jensen/grady.md`, lines 64–151 and 203–232).

## Implemented model

### Wake

For an upstream turbine and a downstream candidate:

```text
R_wake(x) = D/2 + alpha*x
alpha     = 0.5 / ln(H/z0)
Ct        = 4*a*(1-a)
a         = (1 - sqrt(1-Ct))/2
DeltaU/U  = 2*a / (1 + 2*alpha*x/D)^2
```

The deficit is applied only when the downstream rotor centre lies inside the circular top-hat wake and `x > 0`. Multiple wakes use the Mosetti/Grady kinetic-energy rule:

```text
U_j/U_inf = sqrt(max(0, 1 - sum_i (DeltaU_i/U_inf)^2))
```

This replaces the Gaussian Bastankhah shape, Niayifar dynamic `k*`, wake-added TI, linear deficit superposition, and TI iteration for the active sparse solver. The existing fatigue calculation remains present, but fatigue is not part of either paper's validation objective.

### Cost

`evaluate_financial_cost` now returns the paper's dimensionless annual cost:

```text
C(N) = N * (2/3 + 1/3 * exp(-0.00174*N^2))
```

This is the equation printed by Grady et al. (Eq. 6) and the intended Mosetti model (Eq. 5; the extracted PDF text has a superscript/OCR ambiguity). It deliberately replaces the Kikuchi offshore CAPEX calculation on this path.

### Data-flow

```mermaid
flowchart TD
    A[Wind state and layout] --> B[Transform turbine pairs into flow frame]
    B --> C{Downstream and inside top-hat wake?}
    C -->|No| D[Zero single deficit]
    C -->|Yes| E[Jensen deficit]
    D --> F[Sum squared normalized deficits]
    E --> F
    F --> G[Grady/Mosetti kinetic-energy superposition]
    G --> H[Power curve and annual energy]
    A --> I[Count installed turbines]
    I --> J[Paper cost C(N)]
    H --> K[Optimizer objective]
    J --> K
```

## Conflicts that affect reproduction

### 1. Cost objective differs by implementation

Mosetti describes a weighted objective combining inverse annual production and cost; Grady explicitly minimizes `cost / P_tot`. WFLOP's SOGA/MOGA framework exposes separate objectives such as CAPEX, AEP, LCOE, and fatigue. Reproducing paper layouts requires selecting `cost / annual energy` as one scalar objective, not treating paper cost as ordinary GBP CAPEX.

### 2. Unit mismatch

Paper cost is dimensionless and normalized to one turbine. WFLOP output labels and visualizer assume GBP/£ and the README describes Kikuchi CAPEX. Numerical cost values must not be interpreted as pounds until a separate scaling is supplied.

### 3. Turbine and power curve mismatch

Both validation studies use one turbine type, hub height 60 m, `Ct=0.88`, `z0=0.3 m`, and a 40 m rotor-radius statement in Grady's table/text (Mosetti says 40 m diameter in its extracted text, while the 5D cell/domain arithmetic implies a 40 m diameter). Grady uses `P=0.3*u^3`; WFLOP uses loaded Cp curves, rated power, cut-in/cut-off, density, and SI conversion. Exact paper numbers cannot be expected without a paper-compatible turbine input.

### 4. Grid and spacing mismatch

Mosetti and Grady use a 10x10 grid with 5D cells, 50D x 50D domain. WFLOP accepts an arbitrary mesh and heterogeneous turbine types. Different node coordinates or boundary masks change wake overlap and the optimum even if the equations match.

### 5. Wake overlap and multiple-wake interpretation

Jensen's original report derives a sequential aligned-wake treatment. Mosetti/Grady use the simplified kinetic-energy sum for mixed wakes. This implementation follows the latter because those are the layout-validation papers. It is not a full momentum-conserving sequential wake-merging solver.

### 6. Wind-direction convention

The code rotates coordinates using its existing radians/towards-flow convention. Paper cases use direction sectors in degrees, including 36 equally likely directions in Grady/Mosetti. A 90-degree or sign convention error can produce plausible but wrong layouts. Validate one pair with a hand-calculated downstream/upstream check before comparing optimizations.

### 7. Turbulence, fatigue, and offshore effects are out of scope in the papers

Niayifar TI growth, Yang fatigue, bathymetry, cable topology, installation logistics, workability, and offshore substation costs are not part of Mosetti/Grady's benchmark. They should be disabled or excluded from reported comparisons. The sparse solver no longer uses TI to change wake growth, but fatigue remains calculated for existing output compatibility.

### 8. Optimization convergence is not comparable automatically

Mosetti reports roughly 200 individuals and 350–400 generations. Grady reports 600 individuals, 20 subpopulations, and up to 3000 generations. WFLOP's operators, elitism, mutation, constraints, and stopping rules differ. Grady explicitly attributes disagreement partly to insufficient Mosetti convergence; matching a result requires matching GA settings and random-seed protocol, not only physics.

### 9. Reported metrics conflict

Mosetti emphasizes farm efficiency and cost per energy. Grady accepts lower efficiency when total energy and cost/energy improve. WFLOP's Pareto front may therefore return layouts that look worse under efficiency but are correct under `C/P`. Always report turbine count, total annual energy, efficiency relative to isolated turbines, cost, and cost/energy together.

### 10. Dense visualization path

The active sparse optimizer/simulator wake path is Jensen-style. The separate dense 3-D visualization routine still contains Niayifar/Bastankhah logic. Animation fields are therefore not guaranteed to match validation wake calculations and must not be used as validation evidence without a second conversion.

## Validation protocol

1. Build with `make simulator`.
2. Create a 10x10, 5D grid and one turbine type with paper parameters.
3. Run one turbine, two turbines aligned downwind, and two turbines crosswind. Check the hand equations above.
4. Use uniform 12 m/s wind first; then reproduce 36 directions; then reproduce the 8/12/17 m/s wind rose.
5. Compare `P_tot`, efficiency, turbine count, `C(N)`, and `C/P_tot`, not only optimizer fitness.
6. Run multiple seeds and record best-so-far, because paper GA convergence is stochastic.

## Code locations

- `source/wflop_core.f90:689`: paper cost formula.
- `source/wflop_core.f90:1173`: kinetic-energy wake aggregation.
- `source/wflop_core.f90:1331`: Jensen top-hat sparse wake calculation.
- `document-jensen/*.md`: source papers.

The compiler check passed with `make simulator` after the change.
