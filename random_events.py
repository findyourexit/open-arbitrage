from marketplace import *
from player import *
import random
from random_games import blackjack_play

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
    'Blackjack' : 
                { 
                    'intro_text' : 'In a drunken daze you regain consciousness whilst at the Blackjack table. The dealer shows a X[?] and you show a Y[?]. You have $Z at stake.',
                    'call_to_action' : 'Do you Hit or Stand? (H/S)',
                    'func_calc' : blackjack_play 
                }
}

def get_random_event(player):

    event_name = random.choice(list(random_events))

    intro_text = random_events[event_name]['intro_text']
    call_to_action = random_events[event_name]['call_to_action']
    game_fn = random_events[event_name]['func_calc']

    populateScreenWithEvent(intro_text, call_to_action)

    net_gain = game_fn(23, 45)

    print (f'User gained ${net_gain}')
    


def populateScreenWithEvent(intro_text, call_to_action):

    print('|-------------------------------------------------------|')
    print(get_multiline(intro_text))
    print('|                                                       |')
    print('|                                                       |')
    print(get_multiline(call_to_action))
    print('|-------------------------------------------------------|')

# Converts a single-lined string into a displayable and tablised multiline string
def get_multiline(text):

    multi_string = "| "

    max_chars_per_line = 53
    curr_chars = 0

    for char in text:

        if (curr_chars != max_chars_per_line):

            curr_chars += 1
            multi_string += char

        else:
            
            multi_string += f' |\n| '
            curr_chars = 0

            if char != ' ':
                multi_string += char
                curr_chars += 1

            

    chars_left = max_chars_per_line - curr_chars

    if (chars_left > 0):
        multi_string += " " * chars_left
        multi_string += " |"


    return multi_string





