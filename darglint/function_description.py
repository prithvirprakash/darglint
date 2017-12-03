"""A linter for docstrings following the google docstring format."""
import ast
from typing import (
    List,
    Iterator,
    Set,
    Tuple,
)

from .config import get_logger


logger = get_logger()


def read_program(filename: str) -> str:
    """Read a program from a file.

    Args:
        filename: The name of the file to read.

    Returns:
        The program as a single string.

    """
    program = None  # type: str
    with open(filename, 'r') as fin:
        program = fin.read()
    return program


def _get_arguments(fn: ast.FunctionDef) -> Tuple[List[str], List[str]]:
    arguments = list()  # type: List[str]
    types = list()  # type: List[str]

    def add_arg_by_name(name, arg):
        arguments.append(name)
        if arg.annotation is not None and hasattr(arg.annotation, 'id'):
            types.append(arg.annotation.id)
        else:
            types.append(None)

    for arg in fn.args.args:
        add_arg_by_name(arg.arg, arg)

    # Handle single-star arguments.
    if fn.args.vararg is not None:
        name = '*' + fn.args.vararg.arg
        add_arg_by_name(name, fn.args.vararg)

    if fn.args.kwarg is not None:
        name = '**' + fn.args.kwarg.arg
        add_arg_by_name(name, fn.args.kwarg)

    return arguments, types


def _has_return(fun: ast.FunctionDef) -> bool:
    """Return true if the function has a fruitful return.

    Args:
        fun: A function node to check.

    Returns:
        True if there is a fruitful return, otherwise False.

    """
    for node in ast.walk(fun):
        if isinstance(node, ast.Return) and node.value is not None:
            return True
    return False


def _has_yield(fun: ast.FunctionDef) -> bool:
    for node in ast.walk(fun):
        if isinstance(node, ast.Yield) or isinstance(node, ast.YieldFrom):
            return True
    return False


def _get_docstring(fun: ast.AST) -> str:
    return ast.get_docstring(fun)


def _get_all_functions(tree: ast.AST) -> Iterator[ast.FunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            yield node


def _get_all_classes(tree: ast.AST) -> Iterator[ast.ClassDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


def _get_all_methods(tree: ast.AST) -> Iterator[ast.FunctionDef]:
    for klass in _get_all_classes(tree):
        for fun in _get_all_functions(klass):
            yield fun


def _get_decorator_names(fun: ast.FunctionDef) -> List[str]:
    """Get decorator names from the function.

    Args:
        fun: The function whose decorators we are getting.

    Returns:
        The names of the decorators. Does not include setters and
        getters.

    """
    ret = list()
    for decorator in fun.decorator_list:
        # Attributes (setters and getters) won't have an id.
        if hasattr(decorator, 'id'):
            ret.append(decorator.id)
    return ret


def _is_classmethod(fun: ast.FunctionDef) -> bool:
    return 'classmethod' in _get_decorator_names(fun)


def _is_staticmethod(fun: ast.FunctionDef) -> bool:
    return 'staticmethod' in _get_decorator_names(fun)


def _get_stripped_method_args(
        method: ast.FunctionDef) -> Tuple[List[str], List[str]]:
    args, types = _get_arguments(method)
    if 'cls' in args and _is_classmethod(method):
        args.remove('cls')
        types.pop(0)
    elif 'self' in args and not _is_staticmethod(method):
        args.remove('self')
        types.pop(0)
    return args, types


def _get_all_raises(fn: ast.FunctionDef) -> Iterator[ast.Raise]:
    for node in ast.walk(fn):
        if isinstance(node, ast.Raise):
            yield node


def _get_exception_name(raises: ast.Raise) -> str:
    if isinstance(raises.exc, ast.Name):
        return raises.exc.id
    elif isinstance(raises.exc, ast.Call):
        if hasattr(raises.exc.func, 'id'):
            return raises.exc.func.id
        elif hasattr(raises.exc.func, 'attr'):
            return raises.exc.func.attr
        else:
            logger.error(
                'Raises function call has neither id nor attr.'
                'has only: %s' % str(dir(raises.ecx.func))
            )
    else:
        raise Exception('Unexpected type in raises expression: {}'.format(
            type(raises.exc)
        ))
    return ''


def _get_exceptions_raised(fn: ast.FunctionDef) -> Set[str]:
    ret = set()  # type: Set[str]
    for raises in _get_all_raises(fn):
        # TODO: Handle this?
        # There is a bare raise in the function, no type given.
        if raises.exc is None:
            continue
        ret.add(_get_exception_name(raises))
    return ret


def _get_return_type(fn: ast.FunctionDef) -> str:
    if fn.returns is not None and hasattr(fn.returns, 'id'):
        return fn.returns.id
    return None


class FunctionDescription(object):
    """Describes a function or method.

    Whereas a `Docstring` object describes a function's docstring,
    a `FunctionDescription` describes the function itself.  (What,
    ideally, the docstring should describe.)

    """

    def __init__(self, is_method: bool, function: ast.FunctionDef) -> None:
        """Create a new FunctionDescription.

        Args:
            is_method: True if this is a method. Will attempt to remove
                self or cls if appropriate.
            function: The base node of the function.

        """
        self.is_method = is_method
        self.function = function
        self.line_number = function.lineno
        self.name = function.name
        if is_method:
            self.argument_names, self.argument_types = (
                _get_stripped_method_args(function)
            )
        else:
            self.argument_names, self.argument_types = _get_arguments(function)
        self.has_return = _has_return(function)
        self.return_type = _get_return_type(function)
        self.has_yield = _has_yield(function)
        self.docstring = _get_docstring(function)
        try:
            self.raises = _get_exceptions_raised(function)
        except Exception as ex:
            msg = '{}: {}'.format(self.name, ex)
            logger.error(msg)
            raise


def get_function_descriptions(
        program: ast.AST) -> List[FunctionDescription]:
    """Get function name, args, return presence and docstrings.

    This function should be called on the top level of the
    document (for functions), and on classes (for methods.)

    Args:
        program: The tree representing the entire program.
            This should be the direct result of

    Returns:
        A list of function descriptions pulled from the ast.

    """
    ret = list()  # type: List[FunctionDescription]

    methods = set(_get_all_methods(program))
    for method in methods:
        ret.append(FunctionDescription(is_method=True, function=method))

    functions = set(_get_all_functions(program)) - methods
    for function in functions:
        ret.append(FunctionDescription(is_method=False, function=function))

    return ret