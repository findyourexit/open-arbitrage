from tabulate import tabulate
import random
from marketplace import *
from player import *

market = [Item('a', 10.00),
          Item('b', 50.00),
          Item('c', 25.00),
          Item('d', 30.00),
          Item('e', 5.00),
          Item('f', 1.00)]

player = Player('Tom')

stash = [['a', 0], ['b', 0], ['c', 0], ['d', 0], ['e', 50], ['f', 0]]
cities = ('Sydney', 'Melbourne', 'Zurich', 'New York', 'Milano', 'Santa Barbara')
cash = 200
loan = 10000
loan_max = 100000
interest_rate = 0.20
current_city = 0


def start_game(name):
    print('|-------------------------------------------------------|')
    print(f'| Welcome, {(name + ".").ljust(30)}               |')
    print('|                                                       |')
    print('| The rules are rather simple. Just follow the prompts  |')
    print('| and use your best judgement to turn a profit by       |')
    print('| making the right calls at the right times. Be warned  |')
    print('| though, you\'ll be going into this thing with an       |')
    print('| outstanding debt that will need to be repaid in a     |')
    print('| timely manner, or you\'ll drown in debt. A bit like a  |')
    print('| student loan run rife, but a little more shit.        |')
    print('|-------------------------------------------------------|')
    play_response = input('\nThink you\'ve got what it takes? (Y/N)\n>> ').lower()
    if play_response == 'y':
        print('\nAlright, let\'s do this!\n')
        player.stash_add(market[4], 50)
        start_turn()
    elif play_response == 'n':
        print('\nScared, huh? Nah, I get it. ')
    else:
        print('\nLet\'s try that again... The question is simple, pal.\n')
        start_game(name)


def start_turn():
    # Maybe include an adverse event here to impact stash, cash, or whatever.
    # Manipulate the market here.
    show_position_summary()
    player_input()


def end_game():
    print('Game over.')


def player_input():
    print(tabulate([['What would you like to do? (0-3)'],
                    ['Sell items(s)'],
                    ['Buy items(s)'],
                    ['Change city'],
                    ['Pay loan']],
                   tablefmt="simple", showindex="always", headers="firstrow"))
    try:
        top_menu_input = int(input(">> "))
        print('\n')
        if top_menu_input == 0:
            sell_items()
        elif top_menu_input == 1:
            buy_items()
        elif top_menu_input == 2:
            change_city()  # End turn equivalent?
        elif top_menu_input == 3:
            pay_loan()
        else:
            print('Invalid input. Please try again...')
            player_input()
    except ValueError:
        print('Invalid input. Please try again...')
        player_input()


def change_city():
    print('Where would you like to go? (0-5)')
    print('+-[ CHANGE CITY ]'.ljust(49, '-') + '+')
    for index, city in enumerate(cities):
        print(('| ' + str(index)).ljust(20) + city.ljust(29) + '|')
    print('+'.ljust(49, '-') + '+')
    print('\n')
    try:
        change_city_input = int(input(">> "))
        print('\n')
        if 0 <= change_city_input <= 5:
            global current_city
            if change_city_input != current_city:
                current_city = change_city_input
                print('You\'re now in ' + cities[current_city][0] + '.')
                reroll_market()
                compound_loan(1)
                if loan >= loan_max:
                    print('You\'re drowning in debt.')
                    end_game()
                else:
                    start_turn()
            else:
                print('You\'re already in ' + cities[current_city][0] + '.')
                player_input()
        else:
            print('Invalid input. Please try again...')
            change_city()
    except ValueError:
        print('Invalid input. Please try again...')
        change_city()


def buy_items():
    show_stash()
    show_cash_available()
    show_market()
    try:
        buy_items_input = int(input("What would you like to buy? (0-5)\n>> "))
        if 0 <= buy_items_input <= 5:
            complete_purchase(buy_items_input)
        else:
            print('Invalid input. Please try again...')
            buy_items()
    except ValueError:
        print('Invalid input. Please try again...')
        buy_items()


def complete_purchase(item):
    global cash
    if market[item].value > cash:
        print('You can\'t afford any ' + market[item].name + '. Choose something in your budget...')
        buy_items()
    else:
        try:
            max_purchasable = int(cash / market[item].value)
            complete_purchase_input = int(input('How many ' + market[item].name + ' do you want to purchase? (max: '
                                                + str(max_purchasable) + ')\n>> '))
            if cash >= (complete_purchase_input * market[item].value):
                cash -= complete_purchase_input * market[item].value
                stash[item][1] += complete_purchase_input
                show_stash()
                player_input()
            else:
                print('You\'ve not enough cash for ' + str(complete_purchase_input) + ' of ' + market[item].name
                      + '.')
                complete_purchase(item)
        except ValueError:
            print('Invalid input. Please try again...')
            complete_purchase(item)


def sell_items():
    show_stash()
    show_market()
    try:
        sell_items_input = int(input('What would you like to sell? (0-5)\n>> '))
        if 0 <= sell_items_input <= 5:
            complete_sale(sell_items_input)
        else:
            print('Invalid input. Please try again...')
            sell_items()
    except ValueError:
        print('Invalid input. Please try again...')
        sell_items()


def complete_sale(item):
    global cash
    if stash[item][1] == 0:
        print('You\'ve got no ' + market[item].name + ' to sell...')
        sell_items()
    else:
        try:
            max_sellable = stash[item][1]
            complete_sale_input = int(input('How many ' + market[item].name + ' do you want to sell? (max: '
                                            + str(max_sellable) + ')\n>> '))
            if stash[item][1] >= complete_sale_input:
                stash[item][1] -= complete_sale_input
                cash += complete_sale_input * market[item].value
                show_stash()
                player_input()
            else:
                print('You\'ve not enough ' + market[item].name + ' to sell.')
                complete_sale(item)
        except ValueError:
            print('Invalid input. Please try again...')
            complete_sale(item)


def pay_loan():
    show_loan_outstanding()
    show_cash_available()

    global cash, loan
    if cash <= 0:
        print('You\'ve got no cash to use to repay your loan.')
        player_input()
    try:
        pay_loan_input = int(input('How much of your loan would you like to repay? (1-' + str(cash) + ')\n>> '))
        if pay_loan_input > cash:
            print('You don\'t have $' + str(pay_loan_input) + ' to use to pay off your loan.')
            pay_loan()
        elif pay_loan_input <= 0:
            print('Please enter an amount that\'s greater than zero.')
            pay_loan()
        else:
            if pay_loan_input > loan:
                print('Paying back more than you owe? Show off. Nicely done though!')
                end_game()
            elif pay_loan_input == loan:
                print('Paying out your loan? Nice one!')
                end_game()
            else:
                print('Paid $' + str(pay_loan_input) + ' back into loan. $' + str(loan - pay_loan_input)
                      + ' outstanding.')
                loan -= pay_loan_input
                cash -= pay_loan_input
    except ValueError:
        print('Invalid input. Please try again...')
        pay_loan()


def reroll_market():
    for item in market:
        item.last_value = item.value
        reroll = item.value * random.uniform(0.5, 1.5)
        if reroll < item.min_value:
            item.value = item.min_value
        elif reroll > item.max_value:
            item.value = item.max_value
        else:
            item.value = reroll


def compound_loan(days):
    global loan
    for i in range(days):
        loan += loan * interest_rate


def intro():
    print('|-------------------------------------------------------|')
    print('|                  Welcome to OpenARB                   |')
    print('|-------------------------------------------------------|')
    print('| OpenARB is an open source program aiming to emulate a |')
    print('| free market while encouraging players to participate  |')
    print('| in arbitrage in order to increase working capital.    |')
    print('|-------------------------------------------------------|')


def show_stash():
    print('Your stash:')
    print(tabulate(stash, headers=["Item", "Quantity"], tablefmt="simple", floatfmt=".2f") + '\n')


def show_market():
    print('Local market values in ' + cities[current_city][0] + ' are:')
    print('Item'.ljust(10) + '| Price ($)'.ljust(15))
    print(''.ljust(10, '-') + '+'.ljust(15, '-'))
    for item in market:
        print(str(item.name).ljust(10) + f'| ${item.value:.2f}'.ljust(15))


def show_current_city():
    print('Your current city is ' + cities[current_city][0] + '.\n')


def show_loan_outstanding():
    print('Loan amount (total outstanding): $' + str(loan) + '.\n')


def show_cash_available():
    print('Available cash (liquidity): $' + str(cash) + '.\n')


def show_position_summary():
    print('+-[ POSITION SUMMARY ]'.ljust(69, '-') + '+')
    print('| Available cash (liquidity): '.ljust(40) + str(f'${cash:.2f}').ljust(29) + '|')
    print('| Loan amount (total outstanding): '.ljust(40) + str(f'${loan:.2f}').ljust(29) + '|')
    print('| Current city: '.ljust(40) + cities[current_city].ljust(29) + '|')
    print('+-[ MARKET SUMMARY ]'.ljust(69, '-') + '+')
    for item in market:
        print(('| ' + item.name).ljust(40) + str(f'${item.value:.2f}').ljust(29) + '|')
    print('+-[ STASH SUMMARY ]'.ljust(69, '-') + '+')
    for item in stash:
        print(('| ' + item[0]).ljust(40) + str(f'{item[1]}').ljust(29) + '|')
    print('+'.ljust(69, '-') + '+')
    print('\n')


if __name__ == '__main__':
    intro()
    start_game(input('\nBefore we being, what should I call you?\n>> '))
