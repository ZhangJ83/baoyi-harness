# HumanEval/7

from typing import List


def filter_by_substring(strings: List[str], substring: str) -> List[str]:
    """ Filter an input list of strings only for ones that contain given substring
    >>> filter_by_substring([], 'a')
    []
    >>> filter_by_substring(['abc', 'bacd', 'cde', 'array'], 'a')
    ['abc', 'bacd', 'array']
    """


请在 HumanEval_7 目录中实现函数 `filter_by_substring`，保存为 solution.py，只输出代码，不要写测试文件。