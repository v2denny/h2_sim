import random


class Variable:
    def __init__(self, config):
        self.config = config
        self.value = 0.0
        self.last_update = -1

    def update(self, t):
        if isinstance(self.config, (int, float)):
            self.value = float(self.config)
            return self.value

        if isinstance(self.config, dict):
            interval = self.config.get("update_interval", 1)

            if t - self.last_update >= interval:
                self.value = random.uniform(
                    self.config.get("min", 0),
                    self.config.get("max", 1)
                )
                self.last_update = t

        return self.value

    def set_manual(self, value):
        self.value = float(value)