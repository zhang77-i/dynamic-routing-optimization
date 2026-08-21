# Dynamic Routing Optimization

An intelligent routing framework combining Operations Research and AI methods for dynamic logistics decision making.

## Overview

This project focuses on dynamic vehicle routing problems where customer requests arrive continuously and routing decisions need periodic updates.

Pipeline:

```
Dynamic Orders
      |
      v
Initial Solution
      |
      v
ALNS Optimization
      |
      v
Rolling Horizon Re-planning
      |
      v
Routing Decision
```

## Features

- Vehicle Routing Problem (VRP) modeling
- Dynamic order insertion
- Adaptive Large Neighborhood Search (ALNS)
- Destroy and repair operators
- Rolling Horizon optimization

## Structure

```
dynamic-routing-optimization
|
├── vrp
│   ├── model.py
│   └── constraints.py
|
├── heuristic
│   ├── alns.py
│   ├── destroy.py
│   └── repair.py
|
├── dynamic
│   └── rolling_horizon.py
|
├── benchmark
|
└── demo
```

## Core Algorithms

### VRP

Decision variable:

$$x_{ijk}=1$$

vehicle $k$ travels from node $i$ to node $j$.

### ALNS

Optimization process:

```
Initial Solution
       |
Destroy Operator
       |
Repair Operator
       |
Acceptance Criterion
```

### Rolling Horizon

The system periodically updates routing decisions according to newly released orders.

## Applications

- Instant delivery
- Last-mile logistics
- Fleet dispatching
- Dynamic transportation optimization

## Tech Stack

- Python
- OR-Tools
- NumPy
- Operations Research
- Metaheuristics
