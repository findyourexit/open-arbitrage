class Item:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.min_value = int(value * 0.5)
        self.max_value = int(value * 1.5)
        self.last_value = self.value
