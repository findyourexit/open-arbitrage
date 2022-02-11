from tabulate import tabulate
import random

market = [['a', 10.00, 5.00, 15.00],
          ['b', 50.00, 25.00, 75.00],
          ['c', 25.00, 12.50, 37.50],
          ['d', 30.00, 15.00, 45.00],
          ['e', 5.00, 2.50, 7.50],
          ['f', 1.00, 0.50, 1.50]]
stash = [['a', 0], ['b', 0], ['c', 0], ['d', 0], ['e', 50], ['f', 0]]
cities = (['Sydney'], ['Melbourne'], ['Zurich'], ['New York'], ['Milano'], ['Santa Barbara'])
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
        start_turn()
    elif play_response == 'n':
        print('\nScared, huh? Nah, I get it. ')
    else:
        print('\nLet\'s try that again... The question is simple, pal.\n')
        start_game(name)


def start_turn():
    # Maybe include an adverse event here to impact stash, cash, or whatever.
    # Manipulate the market here.
    position_summary()
    player_input()


def end_game():
    print('Game over.')


def position_summary():  # This needs to be formatted such that it can appear in an easily digested table.
    show_current_city()
    show_market()
    show_stash()
    show_loan_outstanding()
    show_cash_available()


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
    print(tabulate(cities, headers=['Where would you like to go? (0-5)'], tablefmt="simple", showindex="always"))
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
    if market[item][1] > cash:
        print('You can\'t afford any ' + market[item][0] + '. Choose something in your budget...')
        buy_items()
    else:
        try:
            complete_purchase_input = int(input('How many ' + market[item][0] + ' do you want to purchase?\n>> '))
            if cash > (complete_purchase_input * market[item][1]):
                cash -= complete_purchase_input * market[item][1]
                stash[item][1] += complete_purchase_input
                show_stash()
                player_input()
            else:
                print('You\'ve not enough cash for ' + str(complete_purchase_input) + ' of ' + market[item][0] + '.')
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
        print('You\'ve got no ' + market[item][0] + ' to sell...')
        sell_items()
    else:
        try:
            complete_sale_input = int(input('How many ' + market[item][0] + ' do you want to sell?\n>> '))
            if stash[item][1] >= complete_sale_input:
                stash[item][1] -= complete_sale_input
                cash += complete_sale_input * market[item][1]
                show_stash()
                player_input()
            else:
                print('You\'ve not enough ' + market[item][0] + ' to sell.')
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
        reroll = item[1] * random.uniform(0.5, 1.5)
        if reroll < item[2]:
            item[1] = item[2]
        elif reroll > item[3]:
            item[1] = item[3]
        else:
            item[1] = reroll


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
    print(tabulate(market, headers=["Item", "Price ($)", "Min ($)", "Max ($)"], tablefmt="simple", floatfmt=".2f")
          + '\n')


def show_current_city():
    print('Your current city is ' + cities[current_city][0] + '.\n')


def show_loan_outstanding():
    print('Loan amount (total outstanding): $' + str(loan) + '.\n')


def show_cash_available():
    print('Available cash (liquidity): $' + str(cash) + '.\n')


if __name__ == '__main__':
    intro()
    start_game(input('\nBefore we being, what should I call you?\n>> '))
