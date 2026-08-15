def is_palindrome(string: str) -> bool:
    """ Test if given string is a palindrome """
    return string == string[::-1]


def make_palindrome(string: str) -> str:
    """ Find the shortest palindrome that begins with a supplied string. """
    for i in range(len(string)):
        # Check suffixes from longest to shortest
        if is_palindrome(string[i:]):
            return string + string[:i][::-1]
    return string
