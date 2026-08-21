import random


class AdaptiveOperatorSelector:
    """Roulette-wheel operator selection for ALNS.

    Operators with better historical performance receive higher probability.
    """

    def __init__(self, operators, reaction_factor=0.2):
        self.operators = operators
        self.reaction_factor = reaction_factor
        self.weights = {op.__name__: 1.0 for op in operators}
        self.scores = {op.__name__: 0.0 for op in operators}

    def select(self):
        names = list(self.weights.keys())
        values = list(self.weights.values())
        return random.choices(names, weights=values, k=1)[0]

    def update(self, operator_name, reward):
        old = self.weights[operator_name]
        self.weights[operator_name] = (
            (1 - self.reaction_factor) * old
            + self.reaction_factor * reward
        )
