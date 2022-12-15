from __future__ import annotations

import pytest
success = [
    (
        (
            ('--test',),
            dict(
                group='tst',
                dest='testing',
            ),
        ),  # Equivalent to Setting("--test", group="tst")
        {
            'action': None,
            'choices': None,
            'cmdline': True,
            'const': None,
            'default': None,
            'dest': 'testing',  # dest is calculated by Setting and is not used by argparse
            'exclusive': False,
            'file': True,
            'group': 'tst',
            'help': None,
            'internal_name': 'tst_testing',  # Should almost always be "{group}_{dest}"
            'metavar': 'TESTING',  # Set manually so argparse doesn't use TST_TEST
            'nargs': None,
            'required': None,
            'type': None,
            'argparse_args': ('--test',),  # *args actually sent to argparse
            'argparse_kwargs': {
                'action': None,
                'choices': None,
                'const': None,
                'default': None,
                'dest': 'tst_testing',
                'help': None,
                'metavar': 'TESTING',
                'nargs': None,
                'required': None,
                'type': None,
            },  # Non-None **kwargs sent to argparse
        },
    ),
    (
        (
            ('--test',),
            dict(
                group='tst',
            ),
        ),  # Equivalent to Setting("--test", group="tst")
        {
            'action': None,
            'choices': None,
            'cmdline': True,
            'const': None,
            'default': None,
            'dest': 'test',  # dest is calculated by Setting and is not used by argparse
            'exclusive': False,
            'file': True,
            'group': 'tst',
            'help': None,
            'internal_name': 'tst_test',  # Should almost always be "{group}_{dest}"
            'metavar': 'TEST',  # Set manually so argparse doesn't use TST_TEST
            'nargs': None,
            'required': None,
            'type': None,
            'argparse_args': ('--test',),  # *args actually sent to argparse
            'argparse_kwargs': {
                'action': None,
                'choices': None,
                'const': None,
                'default': None,
                'dest': 'tst_test',
                'help': None,
                'metavar': 'TEST',
                'nargs': None,
                'required': None,
                'type': None,
            },  # Non-None **kwargs sent to argparse
        },
    ),
    (
        (
            ('--test',),
            dict(
                action='store_true',
                group='tst',
            ),
        ),  # Equivalent to Setting("--test", group="tst", action="store_true")
        {
            'action': 'store_true',
            'choices': None,
            'cmdline': True,
            'const': None,
            'default': None,
            'dest': 'test',  # dest is calculated by Setting and is not used by argparse
            'exclusive': False,
            'file': True,
            'group': 'tst',
            'help': None,
            'internal_name': 'tst_test',  # Should almost always be "{group}_{dest}"
            'metavar': None,  # store_true does not get a metavar
            'nargs': None,
            'required': None,
            'type': None,
            'argparse_args': ('--test',),  # *args actually sent to argparse
            'argparse_kwargs': {
                'action': 'store_true',
                'choices': None,
                'const': None,
                'default': None,
                'dest': 'tst_test',
                'help': None,
                'metavar': None,
                'nargs': None,
                'required': None,
                'type': None,
            },  # Non-None **kwargs sent to argparse
        },
    ),
    (
        (
            ('-t', '--test'),
            dict(
                group='tst',
            ),
        ),  # Equivalent to Setting("-t", "--test", group="tst")
        {
            'action': None,
            'choices': None,
            'cmdline': True,
            'const': None,
            'default': None,
            'dest': 'test',
            'exclusive': False,
            'file': True,
            'group': 'tst',
            'help': None,
            'internal_name': 'tst_test',
            'metavar': 'TEST',
            'nargs': None,
            'required': None,
            'type': None,
            'argparse_args': ('-t', '--test'),  # Only difference with above is here
            'argparse_kwargs': {
                'action': None,
                'choices': None,
                'const': None,
                'default': None,
                'dest': 'tst_test',
                'help': None,
                'metavar': 'TEST',
                'nargs': None,
                'required': None,
                'type': None,
            },
        },
    ),
    (
        (
            ('test',),
            dict(
                group='tst',
            ),
        ),  # Equivalent to Setting("test", group="tst")
        {
            'action': None,
            'choices': None,
            'cmdline': True,
            'const': None,
            'default': None,
            'dest': 'test',
            'exclusive': False,
            'file': True,
            'group': 'tst',
            'help': None,
            'internal_name': 'tst_test',
            'metavar': 'TEST',
            'nargs': None,
            'required': None,
            'type': None,
            'argparse_args': ('tst_test',),
            'argparse_kwargs': {
                'action': None,
                'choices': None,
                'const': None,
                'default': None,
                'dest': None,  # Only difference with #1 is here, argparse sets dest based on the *args passed to it
                'help': None,
                'metavar': 'TEST',
                'nargs': None,
                'required': None,
                'type': None,
            },
        },
    ),
    (
        (
            ('--test',),
            dict(),
        ),  # Equivalent to Setting("test")
        {
            'action': None,
            'choices': None,
            'cmdline': True,
            'const': None,
            'default': None,
            'dest': 'test',
            'exclusive': False,
            'file': True,
            'group': '',
            'help': None,
            'internal_name': 'test',  # No group, leading _ is stripped
            'metavar': 'TEST',
            'nargs': None,
            'required': None,
            'type': None,
            'argparse_args': ('--test',),
            'argparse_kwargs': {
                'action': None,
                'choices': None,
                'const': None,
                'default': None,
                'dest': 'test',
                'help': None,
                'metavar': 'TEST',
                'nargs': None,
                'required': None,
                'type': None,
            },
        },
    ),
]

failure = [
    (
        (
            (),
            dict(
                group='tst',
            ),
        ),  # Equivalent to Setting(group="tst")
        pytest.raises(ValueError),
    ),
]
