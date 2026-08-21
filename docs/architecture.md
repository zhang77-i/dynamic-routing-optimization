# System Architecture

## Overview

Dynamic Routing Optimization is designed as a modular optimization framework for vehicle routing problems with dynamic order arrivals.

## Architecture

```
Data Sources
    |
    v
Data Processing
    |
    v
Routing Model
    |
    +----------------+
    |                |
    v                v
ALNS Solver     OR-Tools Solver
    |                |
    +----------------+
             |
             v
Routing Solution
             |
             v
Evaluation + Visualization
```

## Modules

### Data Layer

Handles benchmark instances and online order streams.

### Model Layer

Defines routing entities and constraints.

### Solver Layer

Provides interchangeable optimization strategies.

### Dynamic Layer

Implements rolling horizon dispatching.

### Evaluation Layer

Measures distance, runtime, vehicle usage and service quality.
