from dataclasses import dataclass
from pathlib import Path


@dataclass
class SolomonCustomer:
    customer_id: int
    x: float
    y: float
    demand: float
    ready_time: float
    due_time: float
    service_time: float


def load_solomon_instance(file_path):
    """Load Solomon VRPTW benchmark instance.

    The parser converts benchmark text files into structured customer objects
    for routing experiments.
    """
    customers = []

    lines = Path(file_path).read_text().splitlines()

    data_start = False
    for line in lines:
        parts = line.split()

        if len(parts) == 0:
            continue

        if parts[0].isdigit() and len(parts) >= 7:
            data_start = True

        if data_start:
            customers.append(
                SolomonCustomer(
                    customer_id=int(parts[0]),
                    x=float(parts[1]),
                    y=float(parts[2]),
                    demand=float(parts[3]),
                    ready_time=float(parts[4]),
                    due_time=float(parts[5]),
                    service_time=float(parts[6]),
                )
            )

    return customers
