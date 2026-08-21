# Benchmark Protocol

## Dataset

The project uses standard Vehicle Routing Problem benchmarks.

Primary dataset:

- Solomon VRPTW instances
- C101
- R101
- RC101

## Compared Methods

The benchmark framework supports multiple solvers:

- ALNS
- OR-Tools based routing solver
- Baseline heuristics

## Metrics

Evaluation metrics include:

| Metric | Description |
|---|---|
| Total Distance | Total route length |
| Runtime | Optimization time |
| Vehicle Count | Number of vehicles used |
| Service Rate | Percentage of served orders |

## Experiment Pipeline

```
Dataset
  |
Loader
  |
Solver
  |
Evaluation
  |
Result Writer
  |
CSV Report
```

## Future Extensions

Possible extensions include:

- Larger VRPTW benchmarks
- Real road network experiments
- Dynamic order simulation
- Hybrid optimization methods
