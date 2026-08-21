# Optimization Algorithms

## ALNS Framework

Adaptive Large Neighborhood Search is used for large-scale routing optimization.

The framework contains four components:

1. Initial solution generation
2. Destroy operators
3. Repair operators
4. Acceptance strategy

## Destroy Operators

Destroy operators partially remove customers from the current solution.

Implemented strategies:

- Random removal
- Worst removal

The purpose is to explore new solution neighborhoods.

## Repair Operators

Repair operators reconstruct feasible routes.

Typical strategies:

- Greedy insertion
- Regret insertion

## Adaptive Operator Selection

Operator weights are updated according to historical performance.

Operators producing better solutions receive higher selection probability.

## Simulated Annealing Acceptance

A controlled probability of accepting worse solutions helps escape local optima.

The acceptance probability follows:

```
P = exp(-delta / T)
```

where T is the current temperature.

## Dynamic Optimization

Rolling horizon optimization handles continuous order arrivals:

```
New Orders
    |
Update State
    |
Re-optimize Remaining Tasks
    |
Dispatch
```
