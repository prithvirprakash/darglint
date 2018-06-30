"""A parser for Sphinx-style docstrings.

The EBNF for the parser is as follows:

  docstring = short-description, [long-description];
            | short-description
                , [long-description]
                , item
                , {[newline], item}
                , newline;

  short-description = unline
                    | line, newline;
  long-description = line, {line}, newline;

  item = indent, item-name, item-definition;
  section-name = colon, keyword, [word], colon;
  item-definition = line, {line};
  line = unline, newline
  unline = { word
           , hash
           , colon
           , indent
           , keyword
           , lparen
           , rparen
           }, [noqa];

  noqa = noqa-head, [colon, list]
  noqa-head = hash, noqa-keyword
  list = word {"," word}

  keyword = "arg"
          | "argument"
          | "param"
          | "parameter"
          | "key"
          | "keyword"
          | "raises"
          | "raise"
          | "except"
          | "exception"
          | "var"
          | "ivar"
          | "cvar"
          | "returns"
          | "return"
          | "yield"
          | "yields"
          | "type"
          | "vartype"
          | "rtype"
          | "ytype";

  indent  = " " * 4;
  word    = ? r/[^\ \n\:\"\t]+/ ?;
  noqa-keyword = "noqa"
  hash = "#"
  lparen = "("
  rparen = ")"
  colon   = ":";
  newline = "\n";

"""

from collections import deque
from itertools import chain
from typing import (  # noqa
    Dict,
    List,
)

from ..node import (
    Node,
    NodeType,
)
from ..peaker import Peaker  # noqa
from ..token import (  # noqa
    Token,
    TokenType,
)
from .common import (
    Assert,
    AssertNotEmpty,
    ParserException,
    parse_colon,
    parse_hash,
    parse_indent,
    parse_keyword,
    parse_lparen,
    parse_noqa,
    parse_rparen,
    parse_word,
)

KEYWORDS = {
    'arg': NodeType.ARGUMENTS,
    'argument': NodeType.ARGUMENTS,
    'param': NodeType.ARGUMENTS,
    'parameter': NodeType.ARGUMENTS,
    'key': NodeType.ARGUMENTS,
    'keyword': NodeType.ARGUMENTS,
    'type': NodeType.TYPE,
    'raises': NodeType.RAISES,
    'raise': NodeType.RAISES,
    'except': NodeType.RAISES,
    'exception': NodeType.RAISES,
    'var': NodeType.VARIABLES,
    'ivar': NodeType.VARIABLES,
    'cvar': NodeType.VARIABLES,
    'vartype': NodeType.TYPE,
    'returns': NodeType.RETURNS,
    'return': NodeType.RETURNS,
    'rtype': NodeType.TYPE,
    'yield': NodeType.YIELDS,
    'yields': NodeType.YIELDS,
    'ytype': NodeType.TYPE,
}

_KEYWORD_TO_SECTION = {
    NodeType.ARGUMENTS: NodeType.ARGS_SECTION,
    NodeType.RAISES: NodeType.RAISES_SECTION,
    NodeType.VARIABLES: NodeType.VARIABLES_SECTION,
    NodeType.RETURNS: NodeType.RETURNS_SECTION,
    NodeType.YIELDS: NodeType.YIELDS_SECTION,
}


def _in_keywords(peaker, offset=1):
    # type: (Peaker[Token], int) -> bool
    token = peaker.peak(offset)
    if token is None:
        return False
    return token.value in KEYWORDS


def _is(expected_type, peaker, offset=1):
    # type: (TokenType, Peaker[Token], int) -> bool
    """Check if the peaker's next value is the given type.

    Args:
        expected_type: The type we're checking.
        peaker: The peaker.
        offset: The lookahead to use.  (Most of the time, this
            will be 1 -- the current token.)

    Returns:
        True if the next token is the given type, false
        otherwise. (Including if there are no more tokens.)

    """
    token = peaker.peak(offset)
    if token is not None:
        return token.token_type == expected_type
    return False


def parse_line(peaker):
    # type: (Peaker[Token]) -> Node
    AssertNotEmpty(peaker, 'Parsing line.')
    children = []  # type: List[Node]

    while peaker.has_next() and not _is(TokenType.NEWLINE, peaker):
        if _is(TokenType.WORD, peaker) and _in_keywords(peaker):
            children.append(parse_keyword(peaker, KEYWORDS))
        elif _is(TokenType.WORD, peaker):
            children.append(parse_word(peaker))
        elif _is(TokenType.COLON, peaker):
            children.append(parse_colon(peaker))
        elif _is(TokenType.INDENT, peaker):
            children.append(parse_indent(peaker))
        elif _is(TokenType.LPAREN, peaker):
            children.append(parse_lparen(peaker))
        elif _is(TokenType.RPAREN, peaker):
            children.append(parse_rparen(peaker))
        elif _is(TokenType.HASH, peaker):
            token = peaker.peak(lookahead=2)
            if token is not None and token.value == 'noqa':
                children.append(parse_noqa(peaker))
            else:
                children.append(parse_hash(peaker))
        else:
            token = peaker.peak()
            assert token is not None
            raise ParserException('Unexpected type {} in line.'.format(
                token.token_type
            ))

    # It is possible that there are no children at this point, in
    # which case there is likely just the newline.  In this case,
    # we try to set the token so that the line can have a line
    # number.
    token = None
    if peaker.has_next():
        if not children:
            token = peaker.next()
        else:
            peaker.next()  # Throw away newline.
    return Node(
        NodeType.LINE,
        children=children,
        token=token,
    )


def parse_short_description(peaker):
    # type: (Peaker[Token]) -> Node
    AssertNotEmpty(peaker, 'parse short description')
    Assert(
        not _is(TokenType.NEWLINE, peaker),
        'Must have short description in docstring.'
    )
    return Node(
        NodeType.SHORT_DESCRIPTION,
        children=[parse_line(peaker)],
    )


def _at_item(peaker):
    # type: (Peaker[Token]) -> bool
    token = peaker.peak(lookahead=2)
    if token is None:
        return False
    return (_is(TokenType.COLON, peaker)
            and token.value in KEYWORDS)


def parse_long_description(peaker):
    # type: (Peaker[Token]) -> Node
    AssertNotEmpty(peaker, 'parse long description')
    children = list()  # type: List[Node]
    while peaker.has_next() and not _at_item(peaker):
        children.append(parse_line(peaker))

    return Node(
        node_type=NodeType.LONG_DESCRIPTION,
        children=children,
    )


def parse_item_definition(peaker):
    # type: (Peaker[Token]) -> Node
    children = [parse_line(peaker)]
    while _is(TokenType.INDENT, peaker, 2):
        children.append(parse_line(peaker))
    return Node(
        node_type=NodeType.ITEM_DEFINITION,
        children=children,
    )


def parse_item_head(peaker):
    # type: (Peaker[Token]) -> Node
    AssertNotEmpty(peaker, 'parse item')
    children = list()  # type: List[Node]

    token = peaker.peak()
    assert token is not None
    Assert(
        _is(TokenType.COLON, peaker),
        'Expected item to start with {} but was {}'.format(
            TokenType.COLON, token.token_type
        ),
    )
    children.append(parse_colon(peaker))

    AssertNotEmpty(peaker, 'parse item')
    token = peaker.peak()
    assert token is not None
    Assert(
        _in_keywords(peaker),
        'Expected a keyword (e.g. "arg", "returns", etc.) but was {}'.format(
            token.value
        )
    )
    keyword = parse_keyword(peaker, KEYWORDS)
    children.append(keyword)

    if not _is(TokenType.COLON, peaker):
        children.append(parse_word(peaker))

    AssertNotEmpty(peaker, 'parse item head end')
    token = peaker.peak()
    assert token is not None
    Assert(
        _is(TokenType.COLON, peaker),
        'Expected item head to end with {} but was {} {}'.format(
            TokenType.COLON,
            token.token_type,
            repr(token.value),
        ),
    )
    children.append(parse_colon(peaker))
    return Node(
        node_type=NodeType.ITEM_NAME,
        children=children,
    )


def parse_item(peaker):
    # type: (Peaker[Token]) -> Node
    head = parse_item_head(peaker)

    keyword = head.children[1]

    if keyword.node_type == NodeType.TYPE:
        allowable_types = ['type', 'rtype', 'vartype', 'ytype']
        Assert(
            keyword.value in allowable_types,
            'Unable to determine section type from keyword {}: '
            'expected one of {}'.format(
                keyword.value,
                str(allowable_types),
            )
        )
        if keyword.value == 'rtype':
            section_type = NodeType.RETURNS_SECTION
        elif keyword.value == 'vartype':
            section_type = NodeType.VARIABLES_SECTION
        elif keyword.value == 'type':
            section_type = NodeType.ARGS_SECTION
        elif keyword.value == 'ytype':
            section_type = NodeType.YIELDS_SECTION
    else:
        section_type = _KEYWORD_TO_SECTION[keyword.node_type]

    children = [
        head,
        parse_item_definition(peaker),
    ]

    return Node(
        node_type=section_type,
        children=children,
    )


def parse(peaker):
    # type: (Peaker[Token]) -> Node
    AssertNotEmpty(peaker, 'parse docstring')
    children = [
        parse_short_description(peaker),
    ]

    long_descriptions = list()  # type: List[Node]
    while peaker.has_next() and not _at_item(peaker):
        long_descriptions.append(
            parse_long_description(peaker)
        )
    if long_descriptions:
        desc = [x.children for x in long_descriptions]
        children.append(
            Node(
                node_type=NodeType.LONG_DESCRIPTION,
                children=list(chain(*desc))
            )
        )

    while peaker.has_next():
        children.append(parse_item(peaker))

    return Node(
        node_type=NodeType.DOCSTRING,
        children=children,
    )

    # TODO: In the parse function, parse everything,
    # then run over it and conglomerate the sections.
    # that will allow us to treat the tree the same as we
    # treat the Google tree.


def consolidate_ast(node):
    # type: (Node) -> Node
    """Consolidate sections of AST from Sphinx to match Google-Style.

    Args:
        node: The docstring to consolidate.

    Returns:
        The consolidated docstring.

    """
    Assert(
        node.node_type == NodeType.DOCSTRING,
        'We can only consolidate docstrings.'
    )
    storage_node_types = {
        NodeType.ARGS_SECTION,
        NodeType.VARIABLES_SECTION,
        NodeType.RAISES_SECTION,
    }
    # The first occurence of the given storage node types.
    storage = dict()  # type: Dict
    queue = deque()  # type: deque
    queue.appendleft(node)
    while queue:
        parent = queue.pop()
        remove_from_parent = deque()  # type: deque
        for i in range(len(parent.children)):
            child = parent.children[i]
            if child.node_type not in storage_node_types:
                continue
            if child.node_type in storage:
                remove_from_parent.appendleft(i)
                storage[child.node_type].children.extend(
                    child.children
                )
                child.children = list()
            else:
                storage[child.node_type] = child
        for i in remove_from_parent:
            parent.children.pop(i)
    return node
