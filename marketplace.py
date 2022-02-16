import random


class Item:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.min_value = int(value * 0.5)
        self.max_value = int(value * 1.5)
        self.last_value = self.value


def fluctuate_market(market):
    for item in market:
        item.last_value = item.value
        # reroll = item.value * random.uniform(0.5, 1.5)
        reroll = item.value * random.gauss(0.95, 0.95/2)
        if reroll < item.min_value:
            item.value = item.min_value
        elif reroll > item.max_value:
            item.value = item.max_value
        else:
            item.value = reroll
