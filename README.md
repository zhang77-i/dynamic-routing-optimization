# Learning-Augmented Dynamic Routing Optimization

A dynamic vehicle routing optimization framework combining graph representation, operations research, and heuristic search for intelligent logistics decision making.

## Architecture

```
Dynamic Orders
      |
      v
Graph Representation
      |
      v
VRP Modeling
      |
      +----------------+
      |                |
      v                v
 CP-SAT Solver       ALNS
      |                |
      +----------------+
              |
              v
 Rolling Horizon Re-optimization
```

## Key Features

- Dynamic Vehicle Routing Problem modeling
- Dynamic order insertion
- Constraint-aware route optimization
- Adaptive Large Neighborhood Search
- Rolling horizon replanning

## Engineering Goal

Build practical routing decision systems where learning methods enhance state representation and optimization methods guarantee feasible solutions.

## Project Structure

```
src/
├── graph/
├── routing/
├── heuristic/
├── dynamic/
└── evaluation/
```

## Core Algorithms

### VRP Modeling

Decision variable:

$$x_{ijk}=1$$

indicates vehicle $k$ travels from node $i$ to node $j$.

### ALNS

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

The system periodically updates routing decisions when new requests arrive.

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
