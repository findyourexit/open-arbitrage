from random import gauss
from math import sqrt, exp
import random


class Item:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.base_value = value
        self.min_value = float(self.base_value * 0.1)
        self.max_value = float(self.base_value * 4.0)
        self.last_value = self.value


def fluctuate_market(market):
    mu = 0.5
    sigma = mu / 2

    for item in market:
        item.last_value = item.value

        step = random.gauss(mu, sigma)

        new_value = item.value

        if step <= 0.5:
            new_value += item.base_value * step

        if step > 0.5:
            new_value += item.base_value * -step

        new_value = (new_value + item.base_value) / 2

        if new_value < item.min_value:
            item.value = item.min_value
        elif new_value > item.max_value:
            item.value = item.max_value
        else:
            item.value = new_value


def fluctuate_market_experimental(market):
    mu = 0.5
    sigma = mu / 2

    for item in market:
        item.value *= exp((mu - 0.5 * sigma ** 2) * (1. / 365.) + sigma * sqrt(1. / 365.) * gauss(mu=0, sigma=1))
