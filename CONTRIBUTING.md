# Contributing Guide

Thank you for contributing to Dynamic Routing Optimization.

## Development Setup

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
pytest
```

## Project Architecture

- `src/data`: benchmark and dynamic order data processing
- `src/routing`: routing model definitions
- `src/heuristic`: ALNS operators and search strategies
- `src/solver`: solver abstraction and implementations
- `src/dynamic`: online dispatch and rolling horizon optimization
- `benchmark`: experiment scripts

## Adding New Solvers

Implement the `BaseRoutingSolver` interface:

```python
solve(instance)
```

and return a `RoutingSolution` object.

## Pull Requests

Please include:

- problem description
- algorithm change
- test coverage
- benchmark comparison when applicable
