from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys
from collections import defaultdict
from typing import Generator

import pytest

import settngs
from settngs import Group
from testing.settngs import example
from testing.settngs import failure
from testing.settngs import success


if sys.version_info < (3, 9):  # pragma: no cover
    from typing import List
else:  # pragma: no cover
    List = list


@pytest.fixture
def settngs_manager() -> Generator[settngs.Manager, None, None]:
    manager = settngs.Manager()
    yield manager


def test_settngs_manager():
    manager = settngs.Manager()
    defaults = manager.defaults()
    assert manager is not None and defaults is not None


def test_settngs_manager_config():
    manager = settngs.Manager(
        definitions=settngs.Config[settngs.Namespace](
            settngs.Namespace(),
            {'tst': Group(False, {'test': settngs.Setting('--test', default='hello', group='tst', exclusive=False)})},
        ),
    )

    defaults = manager.defaults()
    assert manager is not None and defaults is not None
    assert defaults.values['tst']['test'] == 'hello'


@pytest.mark.parametrize('arguments, expected', success)
def test_setting_success(arguments, expected):
    assert vars(settngs.Setting(*arguments[0], **arguments[1])) == expected


@pytest.mark.parametrize('arguments, exception', failure)
def test_setting_failure(arguments, exception):
    with exception:
        settngs.Setting(*arguments[0], **arguments[1])


def test_add_setting(settngs_manager):
    assert settngs_manager.add_setting('--test') is None


class TestValues:

    def test_invalid_normalize(self, settngs_manager):
        with pytest.raises(ValueError) as excinfo:
            settngs_manager.add_setting('--test', default='hello')
            defaults, _ = settngs_manager.normalize_config({}, file=False, cmdline=False)
        assert str(excinfo.value) == 'Invalid parameters: you must set either file or cmdline to True'

    def test_get_defaults(self, settngs_manager):
        settngs_manager.add_setting('--test', default='hello')
        defaults, _ = settngs_manager.defaults()
        assert defaults['']['test'] == 'hello'

    def test_get_defaults_group(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        defaults, _ = settngs_manager.defaults()
        assert defaults['tst']['test'] == 'hello'

    def test_get_defaults_group_space(self, settngs_manager):
        settngs_manager.add_group('Testing tst', lambda parser: parser.add_setting('--test', default='hello'))
        defaults, _ = settngs_manager.defaults()
        assert defaults['Testing tst']['test'] == 'hello'

    def test_cmdline_only(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
        settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

        file_normalized, _ = settngs_manager.normalize_config(settngs_manager.defaults(), file=True)
        cmdline_normalized, _ = settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True)

        assert 'test' not in file_normalized['tst']  # cmdline option not in normalized config
        assert 'test2' in file_normalized['tst2']  # file option in normalized config

        assert 'test' in cmdline_normalized['tst']  # cmdline option in normalized config
        assert 'test2' not in cmdline_normalized['tst2']  # file option not in normalized config

    def test_cmdline_only_persistent_group(self, settngs_manager):
        settngs_manager.add_persistent_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
        settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

        file_normalized, _ = settngs_manager.normalize_config(settngs_manager.defaults(), file=True)
        cmdline_normalized, _ = settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True)

        assert 'test' not in file_normalized['tst']
        assert 'test2' in file_normalized['tst2']

        assert 'test' in cmdline_normalized['tst']
        assert 'test2' not in cmdline_normalized['tst2']

    def test_normalize_defaults(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='hello'))
        settngs_manager.add_persistent_group('tst_persistent', lambda parser: parser.add_setting('--test', default='hello'))

        defaults = settngs_manager.defaults()
        defaults_normalized = settngs_manager.normalize_config(defaults, file=True, default=False)
        assert defaults_normalized.values['tst'] == {}
        assert defaults_normalized.values['tst_persistent'] == {}

        non_defaults = settngs_manager.defaults()
        non_defaults.values['tst']['test'] = 'world'
        non_defaults.values['tst_persistent']['test'] = 'world'
        non_defaults_normalized = settngs_manager.normalize_config(non_defaults, file=True, default=False)

        assert non_defaults_normalized.values['tst'] == {'test': 'world'}
        assert non_defaults_normalized.values['tst_persistent'] == {'test': 'world'}

    def test_normalize(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        defaults = settngs_manager.defaults()
        defaults.values['test'] = 'fail'  # Not defined in settngs_manager, should be removed
        defaults.values['persistent']['hello'] = 'success'  # Not defined in settngs_manager, should stay

        normalized, _ = settngs_manager.normalize_config(defaults, file=True)

        assert 'test' not in normalized
        assert 'tst' in normalized
        assert 'test' in normalized['tst']
        assert normalized['tst']['test'] == 'hello'
        assert normalized['persistent']['hello'] == 'success'
        assert normalized['persistent']['world'] == 'world'


class TestNamespace:

    def test_invalid_normalize(self, settngs_manager):
        with pytest.raises(ValueError) as excinfo:
            settngs_manager.add_setting('--test', default='hello')
            defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=False, cmdline=False)
        assert str(excinfo.value) == 'Invalid parameters: you must set either file or cmdline to True'

    def test_get_defaults(self, settngs_manager):
        settngs_manager.add_setting('--test', default='hello')
        defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        assert defaults.test == 'hello'

    def test_get_defaults_group(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        assert defaults.tst_test == 'hello'

    def test_get_defaults_group_space(self, settngs_manager):
        settngs_manager.add_group('Testing tst', lambda parser: parser.add_setting('--test', default='hello'))
        defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        assert defaults.Testing_tst_test == 'hello'

    def test_cmdline_only(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
        settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

        file_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), file=True), file=True)
        cmdline_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True), cmdline=True)

        assert 'tst_test' not in file_normalized.__dict__
        assert 'tst2_test2' in file_normalized.__dict__

        assert 'tst_test' in cmdline_normalized.__dict__
        assert 'tst2_test2' not in cmdline_normalized.__dict__

    def test_cmdline_only_persistent_group(self, settngs_manager):
        settngs_manager.add_persistent_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
        settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

        file_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), file=True), file=True)
        cmdline_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True), cmdline=True)

        assert 'tst_test' not in file_normalized.__dict__
        assert 'tst2_test2' in file_normalized.__dict__

        assert 'tst_test' in cmdline_normalized.__dict__
        assert 'tst2_test2' not in cmdline_normalized.__dict__

    def test_normalize_defaults(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='hello'))
        settngs_manager.add_persistent_group('tst_persistent', lambda parser: parser.add_setting('--test', default='hello'))

        defaults = settngs_manager.defaults()
        defaults_normalized = settngs_manager.get_namespace(settngs_manager.normalize_config(defaults, file=True, default=False), file=True, default=False)
        assert defaults_normalized.values.__dict__ == {}

        non_defaults = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        non_defaults.values.tst_test = 'world'
        non_defaults.values.tst_persistent_test = 'world'
        non_defaults_normalized = settngs_manager.get_namespace(settngs_manager.normalize_config(non_defaults, file=True, default=False), file=True, default=False)

        assert non_defaults_normalized.values.tst_test == 'world'
        assert non_defaults_normalized.values.tst_persistent_test == 'world'

    def test_normalize(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        defaults = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        defaults.values.test = 'fail'  # Not defined in settngs_manager, should be removed
        defaults.values.persistent_hello = 'success'  # Not defined in settngs_manager, should stay

        normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(defaults, file=True), file=True)

        assert not hasattr(normalized, 'test')
        assert hasattr(normalized, 'tst_test')
        assert normalized.tst_test == 'hello'
        assert normalized.persistent_hello == 'success'
        assert normalized.persistent_world == 'world'


def test_get_namespace_with_namespace(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults, _ = settngs_manager.get_namespace(argparse.Namespace(test='success'), file=True)
    assert defaults.test == 'success'


def test_get_namespace_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=True)
    assert defaults.tst_test == 'hello'


def test_clean_config(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', file=False))
    settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))
    normalized, _ = settngs_manager.defaults()
    normalized['tst']['test'] = 'success'
    normalized['persistent']['hello'] = 'success'
    normalized['fail'] = 'fail'

    cleaned = settngs_manager.clean_config(normalized, file=True)

    assert 'fail' not in cleaned
    assert 'tst2' not in cleaned
    assert cleaned['tst']['test'] == 'success'
    assert cleaned['persistent']['hello'] == 'success'


def test_parse_cmdline(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=True))

    normalized, _ = settngs_manager.parse_cmdline(['--test', 'success'])

    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


namespaces = (
    lambda definitions: settngs.Config({'tst': {'test': 'fail', 'test2': 'success'}}, definitions),
    lambda definitions: settngs.Config(argparse.Namespace(tst_test='fail', tst_test2='success'), definitions),
    lambda definitions: argparse.Namespace(tst_test='fail', tst_test2='success'),
)


@pytest.mark.parametrize('ns', namespaces)
def test_parse_cmdline_with_namespace(settngs_manager, ns):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=True))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='fail', cmdline=True))

    normalized, _ = settngs_manager.parse_cmdline(
        ['--test', 'success'], config=ns(settngs_manager.definitions),
    )

    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'
    assert normalized['tst']['test2'] == 'success'


def test_parse_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text(json.dumps({'tst': {'test': 'success'}, 'persistent': {'hello': 'success'}}))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

    normalized, success = settngs_manager.parse_file(settngs_file)

    assert success
    assert 'test' in normalized[0]['tst']
    assert normalized[0]['tst']['test'] == 'success'
    assert normalized[0]['persistent']['hello'] == 'success'


def test_parse_non_existent_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))

    normalized, success = settngs_manager.parse_file(settngs_file)

    assert success
    assert 'test' in normalized[0]['tst']
    assert normalized[0]['tst']['test'] == 'hello'


def test_parse_corrupt_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text('{')
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))

    normalized, success = settngs_manager.parse_file(settngs_file)

    assert not success
    assert 'test' in normalized[0]['tst']
    assert normalized[0]['tst']['test'] == 'hello'


def test_save_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))
    normalized, _ = settngs_manager.defaults()
    normalized['tst']['test'] = 'success'
    normalized['persistent']['hello'] = 'success'

    success = settngs_manager.save_file(normalized, settngs_file)
    normalized_r, success_r = settngs_manager.parse_file(settngs_file)

    assert success and success_r
    assert 'test' in normalized_r[0]['tst']
    assert normalized_r[0]['tst']['test'] == 'success'
    assert normalized_r[0]['persistent']['hello'] == 'success'


def test_save_file_not_seriazable(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    normalized, _ = settngs_manager.defaults()
    normalized['tst']['test'] = {'fail'}  # Sets are not serializabl

    success = settngs_manager.save_file(normalized, settngs_file)
    normalized_r, success_r = settngs_manager.parse_file(settngs_file)
    # normalized_r will be the default settings

    assert not success
    assert not success_r
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == {'fail'}

    assert 'test' in normalized_r[0]['tst']
    assert normalized_r[0]['tst']['test'] == 'hello'


def test_cli_set(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text(json.dumps({}))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))

    config, success = settngs_manager.parse_config(settngs_file, ['--test', 'success'])
    normalized = config[0]

    assert success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_file_set(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text(json.dumps({'tst': {'test': 'success'}}))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))

    config, success = settngs_manager.parse_config(settngs_file, [])
    normalized = config[0]

    assert success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_cli_override_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text(json.dumps({'tst': {'test': 'fail'}}))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))

    config, success = settngs_manager.parse_config(settngs_file, ['--test', 'success'])
    normalized = config[0]

    assert success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_cli_explicit_default(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text(json.dumps({'tst': {'test': 'fail'}}))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='success'))

    config, success = settngs_manager.parse_config(settngs_file, ['--test', 'success'])
    normalized = config[0]

    assert success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_adding_to_existing_group(settngs_manager, tmp_path):
    def default_to_regular(d):
        if isinstance(d, defaultdict):
            d = {k: default_to_regular(v) for k, v in d.items()}
        return d
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='success'))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='success'))

    def tst(parser):
        parser.add_setting('--test', default='success')
        parser.add_setting('--test2', default='success')

    settngs_manager2 = settngs.Manager()
    settngs_manager2.add_group('tst', tst)

    assert default_to_regular(settngs_manager.definitions) == default_to_regular(settngs_manager2.definitions)


def test_adding_to_existing_persistent_group(settngs_manager: settngs.Manager, tmp_path: pathlib.Path) -> None:
    def default_to_regular(d):
        if isinstance(d, defaultdict):
            d = {k: default_to_regular(v) for k, v in d.items()}
        return d
    settngs_manager.add_persistent_group('tst', lambda parser: parser.add_setting('--test', default='success'))
    settngs_manager.add_persistent_group('tst', lambda parser: parser.add_setting('--test2', default='success'))

    def tst(parser):
        parser.add_setting('--test', default='success')
        parser.add_setting('--test2', default='success')

    settngs_manager2 = settngs.Manager()
    settngs_manager2.add_persistent_group('tst', tst)

    assert default_to_regular(settngs_manager.definitions) == default_to_regular(settngs_manager2.definitions)


class test_type(int):
    ...


def _typed_function(something: str) -> test_type:  # pragma: no cover
    return test_type()


def _untyped_function(something):
    ...


class _customAction(argparse.Action):  # pragma: no cover

    def __init__(
        self,
        option_strings,
        dest,
        const=None,
        default=None,
        required=False,
        help=None,  # noqa: A002
        metavar=None,
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            required=required,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, 'Something')


types = (
    (settngs.Setting('-t', '--test'), str),
    (settngs.Setting('-t', '--test', cmdline=False), 'Any'),
    (settngs.Setting('-t', '--test', default=1, file=True, cmdline=False), int),
    (settngs.Setting('-t', '--test', action='count'), int),
    (settngs.Setting('-t', '--test', action='append'), List[str]),
    (settngs.Setting('-t', '--test', action='extend'), List[str]),
    (settngs.Setting('-t', '--test', action='store_const', const=1), int),
    (settngs.Setting('-t', '--test', action='append_const', const=1), list),
    (settngs.Setting('-t', '--test', action='store_true'), bool),
    (settngs.Setting('-t', '--test', action='store_false'), bool),
    (settngs.Setting('-t', '--test', action=settngs.BooleanOptionalAction), bool),
    (settngs.Setting('-t', '--test', action=_customAction), 'Any'),
    (settngs.Setting('-t', '--test', action='help'), None),
    (settngs.Setting('-t', '--test', action='version'), None),
    (settngs.Setting('-t', '--test', type=int), int),
    (settngs.Setting('-t', '--test', type=_typed_function), test_type),
    (settngs.Setting('-t', '--test', type=_untyped_function, default=1), int),
    (settngs.Setting('-t', '--test', type=_untyped_function), 'Any'),
)


@pytest.mark.parametrize('setting,typ', types)
def test_guess_type(setting, typ):
    guessed_type = setting._guess_type()
    assert guessed_type == typ


settings = (
    (lambda parser: parser.add_setting('-t', '--test'), 'str'),
    (lambda parser: parser.add_setting('-t', '--test', cmdline=False), 'typing.Any'),
    (lambda parser: parser.add_setting('-t', '--test', default=1, file=True, cmdline=False), 'int'),
    (lambda parser: parser.add_setting('-t', '--test', action='count'), 'int'),
    (lambda parser: parser.add_setting('-t', '--test', action='append'), List[str]),
    (lambda parser: parser.add_setting('-t', '--test', action='extend'), List[str]),
    (lambda parser: parser.add_setting('-t', '--test', action='store_const', const=1), 'int'),
    (lambda parser: parser.add_setting('-t', '--test', action='append_const', const=1), 'list'),
    (lambda parser: parser.add_setting('-t', '--test', action='store_true'), 'bool'),
    (lambda parser: parser.add_setting('-t', '--test', action='store_false'), 'bool'),
    (lambda parser: parser.add_setting('-t', '--test', action=settngs.BooleanOptionalAction), 'bool'),
    (lambda parser: parser.add_setting('-t', '--test', action=_customAction), 'typing.Any'),
    (lambda parser: parser.add_setting('-t', '--test', action='help'), None),
    (lambda parser: parser.add_setting('-t', '--test', action='version'), None),
    (lambda parser: parser.add_setting('-t', '--test', type=int), 'int'),
    (lambda parser: parser.add_setting('-t', '--test', type=_typed_function), 'tests.settngs_test.test_type'),
    (lambda parser: parser.add_setting('-t', '--test', type=_untyped_function, default=1), 'int'),
    (lambda parser: parser.add_setting('-t', '--test', type=_untyped_function), 'typing.Any'),
)


@pytest.mark.parametrize('set_options,typ', settings)
def test_generate_ns(settngs_manager, set_options, typ):
    settngs_manager.add_group('test', set_options)

    src = '''\
from __future__ import annotations
import typing
import settngs
'''
    if typ == 'tests.settngs_test.test_type':
        src += 'import tests.settngs_test\n'
    src += '''
class settngs_namespace(settngs.TypedNS):
'''
    if typ is None:
        src += '    ...\n'
    else:
        src += f'    {settngs_manager.definitions["test"].v["test"].internal_name}: {typ}\n'

    generated_src = settngs_manager.generate_ns()

    assert generated_src == src

    ast.parse(generated_src)


def test_example(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings_file = tmp_path / 'settings.json'
    settings_file.touch()

    i = 0
    for args, expected_out, expected_file in example:
        if args == ['manual settings.json']:
            settings_file.unlink()
            settings_file.write_text('{\n  "Example Group": {\n    "hello": "lordwelch",\n    "verbose": true\n  },\n  "persistent": {\n    "test": false,\n    "hello": "world"\n  }\n}\n')
            i += 1
            continue
        else:
            settngs._main(args)
            captured = capsys.readouterr()
        assert captured.out == expected_out, f'{i}, {args}'
        assert settings_file.read_text() == expected_file, f'{i}, {args}'
        i += 1
