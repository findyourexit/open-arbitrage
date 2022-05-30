import random

def blackjack_play(dealer_num, player_num):
    
    user_input = input('Enter your decision: ').lower()

    next_num_user = random.randrange(10) + 2   # generate from 2..11 (11 = ace)
    next_num_dealer = random.randrange(10) + 2   # generate from 2..11 (11 = ace)

    if user_input == 'h':
        
        player_num += next_num_user

        # say "Lucky" or "Unlucky" depending on winning move
        print(f'Player chose Hit... a {next_num_user} is placed on their deck. You now have {player_num}')

        if player_num < 21:
            dealer_num += next_num_dealer
            print(f'Dealer reveals their next card to be {next_num_dealer}, bringing their total to {dealer_num}')

            return handle_dealer(dealer_num, player_num)

        elif player_num == 21:
            print('Player wins with 21!')
            return True

        else:
            print('Player busts by going over 21!')
            return False

    elif user_input == 's':

        print(f'Player chose Stand on {player_num}!')

        dealer_num += next_num_dealer
        print(f'Dealer reveals their next card to be {next_num_dealer}, bringing their total to {dealer_num}')

        return handle_dealer(dealer_num, player_num)

    else:
        
        # Just call function again if the user incorrectly inputs
        blackjack_play(dealer_num, player_num)



def handle_dealer(dealer_num, player_num):
    if (dealer_num > 21):
        print('Dealer busts! You win.')
        return True
    elif (dealer_num == 21):
        print('Dealer wins with 21!')
        return False
    else:
        winner = "Player" if (player_num >= dealer_num) else "Dealer"
        print(f'{winner} wins by being closer to 21!')
        return (player_num >= dealer_num)