from typing import List


def separate_paren_groups(paren_string: str) -> List[str]:
    """ Input to this function is a string containing multiple groups of nested parentheses. Your goal is to
    separate those group into separate strings and return the list of those.
    Separate groups are balanced (each open brace is properly closed) and not nested within each other
    Ignore any spaces in the input string.
    >>> separate_paren_groups('( ) (( )) (( )( ))')
    ['()', '(())', '(()())']
    """
    # Remove spaces
    paren_string = paren_string.replace(" ", "")

    result = []
    balance = 0
    current = []

    for ch in paren_string:
        current.append(ch)
        if ch == '(':
            balance += 1
        elif ch == ')':
            balance -= 1
            if balance == 0:
                result.append(''.join(current))
                current = []

    return result
