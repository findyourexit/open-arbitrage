def blackjack_play(dealer_num, player_num):
    
    user_input = input('Enter your decision: ').lower()

    if user_input == 'h':

        print('Player chose Hit!')

        return 100

    elif user_input == 's':

        print('Player chose Stand!')

        return -200

    else:
        
        # Just call function again if the user incorrectly inputs
        blackjack_play(dealer_num, player_num)