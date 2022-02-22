from marketplace import *
from player import *
import random

# self.name = 'Unknown'
# self.cash = 200
# self.loan = 10000
# self.loan_max = 200000
# self.interest_rate = 0.15
# self.current_city = 0
# self.stash = []

''' 
    Two options for random events. Either they are themed to the current city or players 
    outstanding debt, or completely random.
    
    For extensibility, replayability and times sake, it will follow the latter option for now.
'''

# Random events are a KV pair with the following { event_name : { intro_text, call_to_action, function_to_calc_outcome } }
random_events = {
    'Blackjack' : { 'intro_text' : 'In a drunken daze you regain consciousness whilst at the Blackjack table. The dealer shows a 17[?] and you show a 13[?].',
                    'call_to_action' : 'Do you Hit or Stay? (H/S)',
                    'func_calc' : False }
}

def get_random_event(player):

    event_name = random.choice(list(random_events))

    intro_text = random_events[event_name]['intro_text']
    call_to_action = random_events[event_name]['call_to_action']

    populateScreenWithEvent(intro_text, call_to_action)


def populateScreenWithEvent(intro_text, call_to_action):

    intro_multiline = get_multiline(intro_text)

    print('|-------------------------------------------------------|')
    print(intro_multiline)
    print('\n\n')
    print(call_to_action)
    print('|-------------------------------------------------------|')

def get_multiline(text):

    multi_string = "|"

    max_chars_per_line = 52
    curr_chars = 0

    for char in text:

        if (curr_chars != max_chars_per_line):

            curr_chars += 1
            multi_string += char

        else:
            
            multi_string += f'|\n|{char}'
            curr_chars = 0


    return multi_string


def blackjack_play(dealer_num, player_num):
    
    input = input('\nThink you\'ve got what it takes? (Y/N)\n>> ').lower()

    if input.lower() == 'h':

        print('Player chose Hit!')

    elif input.lower() == 's':

        print('Player chose Stay!')

    else:
        
        # Just call function again if the user incorrectly inputs
        blackjack_play(dealer_num, player_num)


