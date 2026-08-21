# VRP Model

## Problem Definition

Dynamic vehicle routing problem with multiple vehicles and customer requests.

## Model

Decision variable:

$$x_{ijk}=1$$

indicates vehicle $k$ travels from node $i$ to node $j$.

Constraints:

- Each customer served once
- Vehicle capacity constraint
- Flow conservation
- Route continuity

Objective:

Minimize total travel cost and improve service quality.
