import random
from quotes_list import POWERFUL_QUOTES as quotes

def get_random_quote():
    return random.choice(quotes)
