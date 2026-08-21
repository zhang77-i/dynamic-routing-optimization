import csv
from dataclasses import asdict
from pathlib import Path


class BenchmarkResultWriter:
    """Persist optimization benchmark results."""

    def __init__(self, output_path="results.csv"):
        self.output_path = Path(output_path)

    def write(self, records):
        if not records:
            return

        with self.output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(asdict(records[0]).keys())
            )
            writer.writeheader()

            for record in records:
                writer.writerow(asdict(record))
