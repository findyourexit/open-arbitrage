import marketplace
from marketplace import *
from player import *


market = [Item('a', 10.00),
          Item('b', 50.00),
          Item('c', 25.00),
          Item('d', 30.00),
          Item('e', 5.00),
          Item('f', 1.00)]
cities = ('Sydney', 'Melbourne', 'Zurich', 'New York', 'Milano', 'Santa Barbara')
player = Player()


def start_game(name):
    player.name = name
    print('|-------------------------------------------------------|')
    print(f'| Welcome, {(player.name + ".").ljust(30)}               |')
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
    show_player_input_menu()
    try:
        top_menu_input = int(input(">> "))
        print('\n')
        if top_menu_input == 0:
            show_position_summary()
            player_input()
        elif top_menu_input == 1:
            sell_items()
        elif top_menu_input == 2:
            buy_items()
        elif top_menu_input == 3:
            change_city()  # End turn equivalent?
        elif top_menu_input == 4:
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
            if change_city_input != player.current_city:
                player.current_city = change_city_input
                print('You\'re now in ' + cities[player.current_city] + '.')
                marketplace.fluctuate_market(market)
                compound_loan(1)
                if player.loan >= player.loan_max:
                    print('You\'re drowning in debt.')
                    end_game()
                else:
                    start_turn()
            else:
                print('You\'re already in ' + cities[player.current_city] + '.')
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
    if market[item].value > player.cash:
        print('You can\'t afford any ' + market[item].name + '. Choose something in your budget...')
        buy_items()
    else:
        try:
            max_purchasable = int(player.cash / market[item].value)
            complete_purchase_input = int(input('How many ' + market[item].name + ' do you want to purchase? (max: '
                                                + str(max_purchasable) + ')\n>> '))
            if player.cash >= (complete_purchase_input * market[item].value):
                player.cash -= complete_purchase_input * market[item].value
                player.stash_add(market[item], complete_purchase_input)
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
    stash_item = player.stash_get(market[item])
    if stash_item is not None:
        max_sellable = stash_item[1]
        try:
            complete_sale_input = int(input('How many ' + market[item].name + ' do you want to sell? (max: '
                                            + str(max_sellable) + ')\n>> '))
            if stash_item[1] >= complete_sale_input:
                stash_item[1] -= complete_sale_input
                player.cash += complete_sale_input * market[item].value
                show_stash()
                player_input()
            else:
                print('You\'ve not enough ' + market[item].name + ' to sell.')
                complete_sale(item)
        except ValueError:
            print('Invalid input. Please try again...')
            complete_sale(item)
    else:
        print('You\'ve got no ' + market[item].name + ' to sell...')
        sell_items()


def pay_loan():
    show_loan_outstanding()
    show_cash_available()

    if player.cash <= 0:
        print('You\'ve got no cash to use to repay your loan.')
        player_input()
    try:
        pay_loan_input = int(input('How much of your loan would you like to repay? (1-' + str(player.cash) + ')\n>> '))
        if pay_loan_input > player.cash:
            print('You don\'t have $' + str(pay_loan_input) + ' to use to pay off your loan.')
            pay_loan()
        elif pay_loan_input <= 0:
            print('Please enter an amount that\'s greater than zero.')
            pay_loan()
        else:
            if pay_loan_input > player.loan:
                print('Paying back more than you owe? Show off. Nicely done though!')
                end_game()
            elif pay_loan_input == player.loan:
                print('Paying out your loan? Nice one!')
                end_game()
            else:
                print('Paid $' + str(pay_loan_input) + ' back into loan. $' + str(player.loan - pay_loan_input)
                      + ' outstanding.')
                player.loan -= pay_loan_input
                player.cash -= pay_loan_input
                player_input()
    except ValueError:
        print('Invalid input. Please try again...')
        pay_loan()


def compound_loan(days):
    for j in range(days):
        player.loan += player.loan * player.interest_rate


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
    print('Item'.ljust(10) + '| Quantity'.ljust(15))
    print(''.ljust(10, '-') + '+'.ljust(15, '-'))
    for stash_item in player.stash:
        print(str(stash_item[0].name).ljust(10) + ('| ' + str(stash_item[1])).ljust(15))
    print('\n')


def show_player_input_menu():
    print('What would you like to do? (0-3)')
    print('+'.ljust(10, '-') + '+'.ljust(19, '-') + '+')
    print('| 0'.ljust(10) + '| Show overview'.ljust(19) + '|')
    print('| 1'.ljust(10) + '| Sell items(s)'.ljust(19) + '|')
    print('| 2'.ljust(10) + '| Buy items(s)'.ljust(19) + '|')
    print('| 3'.ljust(10) + '| Change city'.ljust(19) + '|')
    print('| 4'.ljust(10) + '| Pay loan'.ljust(19) + '|')
    print('+'.ljust(10, '-') + '+'.ljust(19, '-') + '+')


def show_market():
    print('Local market values in ' + cities[player.current_city] + ' are:')
    print('Item'.ljust(10) + '| Price ($)'.ljust(15))
    print(''.ljust(10, '-') + '+'.ljust(15, '-'))
    for item in market:
        print(str(item.name).ljust(10) + f'| ${item.value:.2f}'.ljust(15))
    print('\n')


def show_current_city():
    print('Your current city is ' + cities[player.current_city] + '.\n')


def show_loan_outstanding():
    print('Loan amount (total outstanding): $' + str(player.loan) + '.\n')


def show_cash_available():
    print('Available cash (liquidity): $' + str(player.cash) + '.\n')


def show_position_summary():
    print('+-[ POSITION SUMMARY ]'.ljust(69, '-') + '+')
    print('| Available cash (liquidity): '.ljust(40) + str(f'${player.cash:.2f}').ljust(29) + '|')
    print('| Loan amount (total outstanding): '.ljust(40) + str(f'${player.loan:.2f}').ljust(29) + '|')
    print('| Current city: '.ljust(40) + cities[player.current_city].ljust(29) + '|')
    print('+-[ MARKET SUMMARY ]'.ljust(69, '-') + '+')
    for item in market:
        print(('| ' + item.name).ljust(40) + str(f'${item.value:.2f}').ljust(29) + '|')
    print('+-[ STASH SUMMARY ]'.ljust(69, '-') + '+')
    for stash_item in player.stash:
        print(('| ' + stash_item[0].name).ljust(40) + str(stash_item[1]).ljust(29) + '|')
    print('+'.ljust(69, '-') + '+')
    print('\n')


if __name__ == '__main__':
    # simulate_market(500, market)
    intro()
    start_game(input('\nBefore we being, what should I call you?\n>> '))
