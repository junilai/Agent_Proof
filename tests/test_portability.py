"""Incorporation cost of each framework (spec F4, §8; counting rule D-014)."""

from textwrap import dedent

from experiments.portability import logical_lines, physical_lines


def src(text: str) -> str:
    return dedent(text).lstrip("\n")


def test_blank_lines_and_comments_do_not_count():
    source = src(
        """
        # a comment

        x = 1  # an inline comment does not remove the code

            # an indented comment
        """
    )
    assert logical_lines(source) == 1
    assert physical_lines(source) == 1


def test_module_class_and_function_docstrings_do_not_count():
    source = src(
        '''
        """Module docstring,
        on two lines."""


        class A:
            """Class docstring."""

            def f(self):
                """Function
                docstring."""
                return 1


        async def g():
            "single-quoted docstring"
            return 2
        '''
    )
    # class A, def f, return 1, async def g, return 2
    assert logical_lines(source) == 5
    assert physical_lines(source) == 5


def test_a_multiline_string_that_is_not_a_docstring_counts():
    source = src(
        '''
        def f():
            x = 1
            """Not a docstring: it is not the first statement."""
            return x


        TEXT = """
        first line

        third line
        """
        '''
    )
    # def, x = 1, the bare string, return, TEXT = ...
    assert logical_lines(source) == 5
    # the string assigned to TEXT spans five physical lines, the blank one included
    assert physical_lines(source) == 4 + 5


def test_a_statement_split_across_lines_is_one_logical_line():
    source = src(
        """
        total = 1 + \\
            2
        call(
            1,  # a comment inside the brackets
            2,
        )
        a = 1; b = 2
        """
    )
    assert logical_lines(source) == 3
    assert physical_lines(source) == 2 + 4 + 1


def test_a_docstring_alone_or_an_empty_source_counts_zero():
    assert logical_lines('"""Only a docstring."""\n') == 0
    assert logical_lines("") == 0
    assert physical_lines("# only a comment\n") == 0


def test_a_source_without_a_final_newline_still_counts_its_last_line():
    assert logical_lines("x = 1\ny = 2") == 2
    assert physical_lines("x = 1\ny = 2") == 2


def test_a_one_line_function_keeps_its_header_but_not_its_docstring():
    source = 'def f(): "docstring"\n\n\ndef g():\n    "docstring"; x = 1\n'
    # def f, def g, x = 1 (the docstring shares its logical line with code)
    assert logical_lines(source) == 2 + 1
    assert physical_lines(source) == 2 + 1
