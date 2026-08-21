import math


class SimulatedAnnealingAcceptance:
    """Simulated annealing acceptance criterion for ALNS.

    Allows controlled acceptance of worse solutions to escape local optima.
    """

    def __init__(self, temperature=100.0, cooling_rate=0.995):
        self.temperature = temperature
        self.cooling_rate = cooling_rate

    def accept(self, current_cost, candidate_cost):
        if candidate_cost < current_cost:
            return True

        delta = candidate_cost - current_cost
        probability = math.exp(-delta / max(self.temperature, 1e-9))
        return probability > 0.5

    def cool_down(self):
        self.temperature *= self.cooling_rate
