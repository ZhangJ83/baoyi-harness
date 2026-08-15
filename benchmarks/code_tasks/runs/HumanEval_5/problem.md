# HumanEval/5

from typing import List


def intersperse(numbers: List[int], delimeter: int) -> List[int]:
    """ Insert a number 'delimeter' between every two consecutive elements of input list `numbers'
    >>> intersperse([], 4)
    []
    >>> intersperse([1, 2, 3], 4)
    [1, 4, 2, 4, 3]
    """


请在 HumanEval_5 目录中实现函数 `intersperse`，保存为 solution.py，只输出代码，不要写测试文件。