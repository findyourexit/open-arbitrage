from random import gauss
from math import sqrt, exp
import random
import matplotlib.pyplot as plt


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


def simulate_market(iterations, market):
    iteration_indexes = range(iterations)
    simulated_history = [[], [], [], [], [], []]

    for i in range(iterations):
        fluctuate_market_experimental(market)
        for idx, item in enumerate(market):
            simulated_history[idx].append(item.value)
            print(str(f'${item.value:.2f}').ljust(10), end='')
        print('\n', end='')

    for idx, item in enumerate(simulated_history):
        plt.plot(iteration_indexes, simulated_history[idx], label='Item ' + market[idx].name)

    plt.xlabel('Day')
    plt.ylabel('Value ($)')
    plt.title('Market Simulation (' + str(iterations) + ' iterations)')
    plt.legend()
    plt.show()