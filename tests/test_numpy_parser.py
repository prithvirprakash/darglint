import random
import string
from unittest import (
    TestCase,
    skip,
)
from darglint.docstring.base import (
    DocstringStyle,
)
from darglint.config import (
    Configuration,
    Strictness,
)
from darglint.lex import (
    condense,
    lex,
)
from darglint.parse.numpy import (
    parse,
)
from darglint.parse.identifiers import (
    ArgumentIdentifier,
    ArgumentTypeIdentifier,
)
from darglint.utils import (
    CykNodeUtils,
)


class NumpydocTests(TestCase):

    def setUp(self):
        self.config = Configuration(
            ignore=[],
            message_template=None,
            style=DocstringStyle.NUMPY,
            strictness=Strictness.FULL_DESCRIPTION,
        )

    def assertContains(self, docstring, node_name):
        self.assertTrue(CykNodeUtils.contains(docstring, node_name))

    def assertIdentified(self, docstring, identifier, expected):
        self.assertEqual(expected, {
            identifier.extract(x)
            for x in CykNodeUtils.get_annotated(
                docstring,
                identifier,
            )
        })

    def assertHasIdentifier(self, docstring, identifier):
        self.assertTrue(len(
            CykNodeUtils.get_annotated(docstring, identifier)
        ) > 0)

    def test_can_parse_short_description(self):
        program = '\n'.join([
            'def add(a, b):',
            '    """The sum of two numbers.',
            '',
            '    """',
            '    return a + b'
        ])
        tokens = condense(lex(program, self.config))
        docstring = parse(tokens)
        self.assertContains(
            docstring,
            'short-description',
        )

    def test_can_parse_deprecation_warning(self):
        program = '\n'.join([
            'def mult(a, b):',
            '    """Multiply two numbers.',
            '',
            '    .. deprecated:: 1.6.0',
            '        Nobody does this anymore!',
            '        This will be removed in NumPy 2.0.0',
            '',
            '    """',
            '    return a * b',
        ])
        tokens = condense(lex(program, self.config))
        docstring = parse(tokens)
        for node_name in [
            'deprecation-warning',
            'deprecation-version',
            'deprecation-description'
        ]:
            self.assertContains(
                docstring,
                node_name,
            )

    def test_can_parse_long_description(self):
        program = '\n'.join([
            'def monkey_up():',
            '    """Monkey things up.',
            '',
            '    Not to be confused with sabotage.',
            '',
            '    """',
            '    return {}[()]',
        ])
        tokens = condense(lex(program, self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'long-description')

    def test_can_parse_empty_parameters_section(self):
        """Make sure we can parse an empty parameter section.

        The numpy format allows for unambiguous section headings,
        without necessarily having any content below them.
        We'll probably want to raise an error for an empty
        parameters section.

        """
        program = '\n'.join([
            'def cry():',
            '    """Cry aloud.',
            '',
            '    Parameters',
            '    ----------',
            '',
            '    """',
            '    print("AAAaaargh")',
        ])
        tokens = condense(lex(program, self.config))
        docstring = parse(tokens)
        for node_name in ['arguments-section', 'arguments-header']:
            self.assertContains(docstring, node_name)

    def test_header_can_have_variable_length(self):
        for underline in [
            '-' * x
            for x in range(1, 15)
        ]:
            program = '\n'.join([
                'def cry():',
                '    """Cry aloud.',
                '',
                '    Parameters',
                '    {}',
                '',
                '    """',
                '    print("AAAaaargh")',
            ]).format(underline)
            tokens = condense(lex(program, self.config))
            docstring = parse(tokens)
            self.assertContains(docstring, 'arguments-section')

    def test_single_parameter(self):
        parameter_descriptions = [
            '    Something.',
            '    A slightly longer description which '
            'can contain a colon: yes.',
            '    A description over\n    two lines.',
            '    A description with two lines and newlines.\n\n'
            '    It\'s perfectly fine.',
        ]
        for parameter_description in parameter_descriptions:
            program = '\n'.join([
                'def process(x):',
                '    """Process some data.',
                '',
                '    Parameters',
                '    ----------',
                '    x',
                '        The data to process.',
                '',
                '    """',
                '    ...',
            ]).format(parameter_description)
            tokens = condense(lex(program, self.config))
            docstring = parse(tokens)
            for node_name in ['arguments-section', 'arguments']:
                self.assertContains(docstring, node_name)

    def test_multiple_parameters(self):
        program_pattern = '\n'.join([
              'def rename({}):',
              '    """Rename the items.',
              '',
              '    Parameters',
              '    ----------',
              '{}',
        ])
        number = random.randint(2, 10)
        names = string.ascii_letters[:number]
        descriptions = [
          '    {}\n        Something\n'.format(name)
          for name in names
        ]
        program = program_pattern.format(
            ', '.join(names),
            '\n'.join(descriptions),
        )
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        for node_name in ['arguments-section', 'arguments']:
            self.assertContains(docstring, node_name)
        self.assertIdentified(docstring, ArgumentIdentifier, set(names))

    @skip('Not collecting whitespace yet')
    def test_error_associated_with_no_whitespace_before_type(self):
        self.fail('Finish me!')

    def test_arguments_section_with_types(self):
        program = '\n'.join([
            'def fontainify(x):',
            '    """Turn the person into a Mr. Fontaine.',
            '',
            '    Parameters',
            '    ----------',
            '    x : Person',
            '        The person to fontainify.',
            '',
            '    """',
            '    pass',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertIdentified(docstring, ArgumentTypeIdentifier, {'x'})

    def test_two_combined_parameters(self):
        program = '\n'.join([
            'def cartesian_product(x1, x2):',
            '    """Get the cartesian product of two lists.',
            '',
            '    Parameters',
            '    ----------',
            '    x1, x2 : List[Any]',
            '        The lists to use for the product.',
            '',
            '    """',
            '    return []',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertIdentified(docstring, ArgumentIdentifier, {'x1', 'x2'})

    def test_returns_section(self):
        program = '\n'.join([
            'def the_number_two():',
            '    """Return the number two.',
            '',
            '    Returns',
            '    -------',
            '    {2}',
            '        The number two.',
            '',
            '    """',
            '    return 2',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'returns-section')

    @skip('Implement return type missing exception')
    def test_return_type_missing_exception(self):
        program = '\n'.join([
            'def the_number_three():',
            '    """Return the number three.',
            '',
            '    Returns',
            '    -------',
            '    The number three.',
            '',
            '    """',
            '    return 3',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'returns-section')
        # self.assertTrueHasIdentifier(docstring, ReturnTypeMissingException)

    @skip('implement return type identifier')
    def test_return_type_with_single_name(self):
        program = '\n'.join([
            'def the_number_four():',
            '    """Return the number four.',
            '',
            '    Returns',
            '    -------',
            '    number : int',
            '        A number to use.',
            '',
            '    """',
            '    return 4',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'returns-section')
        # self.assertIdentified(docstring, RetrunTypeIdentifier, {'int'})

    def test_return_type_with_multiple_names(self):
        program = '\n'.join([
            'def the_number_four():',
            '    """Return the number four.',
            '',
            '    Returns',
            '    -------',
            '    number : int',
            '        A number to use.',
            '    repr: str',
            '        The representation of the number.',
            '',
            '    """',
            '    return random.choice([4, "4"])',
            '',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'returns-section')
        # self.assertIdentified(
        #     docstring, RetrunTypeIdentifier, {'int', 'str'}
        # )

    def test_yields_section(self):
        program = '\n'.join([
            'def the_number_two():',
            '    """Yield the number two.',
            '',
            '    Yields',
            '    -------',
            '    {2}',
            '        The number two.',
            '',
            '    """',
            '    yield 2',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'yields-section')

    @skip('Implement yield type missing exception')
    def test_yield_type_missing_exception(self):
        program = '\n'.join([
            'def the_number_three():',
            '    """Yield the number three.',
            '',
            '    Yields',
            '    -------',
            '    The number three.',
            '',
            '    """',
            '    yield 3',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'yields-section')
        # self.assertTrueHasIdentifier(docstring, YieldTypeMissingException)

    @skip('implement yield type identifier')
    def test_yield_type_with_single_name(self):
        program = '\n'.join([
            'def the_number_four():',
            '    """Yield the number four.',
            '',
            '    Yields',
            '    -------',
            '    number : int',
            '        A number to use.',
            '',
            '    """',
            '    yield 4',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'yields-section')
        # self.assertIdentified(docstring, RetrunTypeIdentifier, {'int'})

    def test_yield_type_with_multiple_names(self):
        program = '\n'.join([
            'def the_number_four():',
            '    """Yield the number four.',
            '',
            '    Yields',
            '    -------',
            '    number : int',
            '        A number to use.',
            '    repr: str',
            '        The representation of the number.',
            '',
            '    """',
            '    yield random.choice([4, "4"])',
            '',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'yields-section')
        # self.assertIdentified(
        #     docstring, RetrunTypeIdentifier, {'int', 'str'}
        # )

    @skip('Implement the error!')
    def test_receives_without_yield_error(self):
        program = '\n'.join([
            'def the_number_four():',
            '    """Yield the number four.',
            '',
            '    Receives',
            '    -------',
            '    repr_or_number : {REPR, NUMB}',
            '        Whether to yield a representation or number.',
            '',
            '    """',
            '    repr_or_numb = REPR',
            '    while True:',
            '        if repr_or_numb == NUMB:',
            '            val = (yield 4)',
            '        elif repr_or_numb == REPR:',
            '            val = (yield "4")',
            '        else:',
            '            raise Exception("Unexpected format.")',
            '        if val:',
            '            repr_or_numb = val',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'yields-section')
        # self.assertHasIdentifier(
        #     docstring, ReceivesWithoutYieldException
        # )

    def test_receives_section(self):
        program = '\n'.join([
            'def counter(maximum=10):',
            '    """Count up to the number.',
            '',
            '    Receives',
            '    --------',
            '    maximum : int',
            '        The new maximum number.',
            '',
            '    Yields',
            '    ------',
            '    int',
            '        The next number up to the maximum.',
            '',
            '    """',
            '    i = 0',
            '    while i < maximum:',
            '        val = (yield i)',
            '        i += 1',
            '        if val:',
            '            maximum = val',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'receives-section')

    def test_other_parameters_section(self):
        program = '\n'.join([
            'def _(x, target="eng"):',
            '    """Translate the string to the target language.',
            '',
            '    Parameters',
            '    ----------',
            '    x : str',
            '        The string to translate.',
            '',
            '    Other Parameters',
            '    ----------------',
            '    target : str',
            '        The target language.',
            '',
            '    """',
            '    return "hur-dur"',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'other-parameters-section')

    def test_raises_section(self):
        program = '\n'.join([
            'def fail():',
            '    """Always fail.',
            '',
            '    Raises',
            '    ------',
            '    Exception',
            '        Under all conditions.',
            '',
            '    """',
            '    raise Exception("Failed!")',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'raises-section')

    def test_warns_section(self):
        program = '\n'.join([
            'def warn():',
            '    """Always warn.',
            '',
            '    Warns',
            '    -----',
            '    Warning',
            '        Under all conditions.',
            '',
            '    """',
            '    raise Warning("Warned!")',
        ])
        tokens = condense(lex(program, config=self.config))
        docstring = parse(tokens)
        self.assertContains(docstring, 'warns-section')
