from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys
from collections import defaultdict
from collections.abc import Generator
from enum import auto
from enum import Enum
from typing import NamedTuple

import pytest

import settngs
from settngs import Group
from testing.settngs import example
from testing.settngs import failure
from testing.settngs import success


if sys.version_info >= (3, 10):  # pragma: no cover
    List = list
    Set = set
    help_output = '''\
usage: __main__.py [-h] [TEST ...]

positional arguments:
  TEST

options:
  -h, --help  show this help message and exit
'''
else:  # pragma: no cover
    List = list
    Set = set
    help_output = '''\
usage: __main__.py [-h] [TEST ...]

positional arguments:
  TEST

optional arguments:
  -h, --help  show this help message and exit
'''


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


def test_add_setting_invalid_name(settngs_manager):
    with pytest.raises(Exception, match='Cannot use test¥ in a namespace'):
        assert settngs_manager.add_setting('--test¥') is None


def test_sub_group(settngs_manager):
    with pytest.raises(Exception, match='Sub groups are not allowed'):
        settngs_manager.add_group('tst', lambda parser: parser.add_group('tst', lambda parser: parser.add_setting('--test2', default='hello')))


def test_sub_persistent_group(settngs_manager):
    with pytest.raises(Exception, match='Sub groups are not allowed'):
        settngs_manager.add_persistent_group('tst', lambda parser: parser.add_persistent_group('tst', lambda parser: parser.add_setting('--test2', default='hello')))


def test_redefine_persistent_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='hello'))
    with pytest.raises(Exception, match='Group already exists and is not persistent'):
        settngs_manager.add_persistent_group('tst', None)


def test_exclusive_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'), exclusive_group=True)
    settngs_manager.create_argparser()
    args = settngs_manager.argparser.parse_args(['--test', 'never'])
    assert args.tst__test == 'never'

    with pytest.raises(SystemExit):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='hello'), exclusive_group=True)
        settngs_manager.create_argparser()
        args = settngs_manager.argparser.parse_args(['__main__.py', '--test', 'never', '--test2', 'never'])


def test_files_group(capsys, settngs_manager):
    settngs_manager.add_group('runtime', lambda parser: parser.add_setting('test', default='hello', nargs='*'))
    settngs_manager.prog = '__main__.py'
    settngs_manager.create_argparser()
    settngs_manager.prog = '__main__.py'
    settngs_manager.argparser.print_help()
    captured = capsys.readouterr()
    assert captured.out == help_output


def test_setting_without_group(capsys, settngs_manager):
    settngs_manager.add_setting('test', default='hello', nargs='*')
    settngs_manager.prog = '__main__.py'
    settngs_manager.create_argparser()
    settngs_manager.prog = '__main__.py'
    settngs_manager.argparser.print_help()
    captured = capsys.readouterr()
    assert captured.out == help_output


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

    def test_normalize_dest(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', dest='test', default='hello'))
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

    def test_unknown_group(self):
        manager = settngs.Manager()
        manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        manager_unknown = settngs.Manager()
        manager_unknown.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        # This manager doesn't know about this group
        # manager_unknown.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        defaults = manager.defaults()
        defaults.values['test'] = 'fail'  # type: ignore[index] # Not defined in manager, should be removed
        defaults.values['persistent']['hello'] = 'success'  # Group is not defined in manager_unknown, should stay

        normalized, _ = manager_unknown.normalize_config(defaults.values, file=True)

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
        assert defaults.tst__test == 'hello'

    def test_get_defaults_group_space(self, settngs_manager):
        settngs_manager.add_group('Testing tst', lambda parser: parser.add_setting('--test', default='hello'))
        defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        assert defaults.Testing_tst__test == 'hello'

    def test_cmdline_only(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
        settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

        file_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), file=True), file=True)
        cmdline_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True), cmdline=True)

        assert 'tst__test' not in file_normalized.__dict__
        assert 'tst2__test2' in file_normalized.__dict__

        assert 'tst__test' in cmdline_normalized.__dict__
        assert 'tst2__test2' not in cmdline_normalized.__dict__

    def test_cmdline_only_persistent_group(self, settngs_manager):
        settngs_manager.add_persistent_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
        settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

        file_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), file=True), file=True)
        cmdline_normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True), cmdline=True)

        assert 'tst__test' not in file_normalized.__dict__
        assert 'tst2__test2' in file_normalized.__dict__

        assert 'tst__test' in cmdline_normalized.__dict__
        assert 'tst2__test2' not in cmdline_normalized.__dict__

    def test_normalize_defaults(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', default='hello'))
        settngs_manager.add_persistent_group('tst_persistent', lambda parser: parser.add_setting('--test', default='hello'))

        defaults = settngs_manager.defaults()
        defaults_normalized = settngs_manager.get_namespace(settngs_manager.normalize_config(defaults, file=True, default=False), file=True, default=False)
        assert defaults_normalized.values.__dict__ == {}

        non_defaults = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        non_defaults.values.tst__test = 'world'
        non_defaults.values.tst_persistent__test = 'world'
        non_defaults_normalized = settngs_manager.get_namespace(settngs_manager.normalize_config(non_defaults, file=True, default=False), file=True, default=False)

        assert non_defaults_normalized.values.tst__test == 'world'
        assert non_defaults_normalized.values.tst_persistent__test == 'world'

    def test_normalize_dest(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test2', dest='test', default='hello'))
        settngs_manager.add_persistent_group('tst_persistent', lambda parser: parser.add_setting('--test', default='hello'))

        defaults = settngs_manager.defaults()
        defaults_normalized = settngs_manager.get_namespace(settngs_manager.normalize_config(defaults, file=True, default=False), file=True, default=False)
        assert defaults_normalized.values.__dict__ == {}

        non_defaults = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        non_defaults.values.tst__test = 'world'
        non_defaults.values.tst_persistent__test = 'world'
        non_defaults_normalized = settngs_manager.get_namespace(settngs_manager.normalize_config(non_defaults, file=True, default=False), file=True, default=False)

        assert non_defaults_normalized.values.tst__test == 'world'
        assert non_defaults_normalized.values.tst_persistent__test == 'world'

    def test_normalize(self, settngs_manager):
        settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        defaults = settngs_manager.get_namespace(settngs_manager.defaults(), file=True, cmdline=True)
        defaults.values.test = 'fail'  # Not defined in settngs_manager, should be removed
        defaults.values.persistent__hello = 'success'  # Not defined in settngs_manager, should stay

        normalized, _ = settngs_manager.get_namespace(settngs_manager.normalize_config(defaults, file=True), file=True)

        assert not hasattr(normalized, 'test')
        assert hasattr(normalized, 'tst__test')
        assert normalized.tst__test == 'hello'
        assert normalized.persistent__hello == 'success'
        assert normalized.persistent__world == 'world'

    def test_normalize_unknown_group(self, settngs_manager):
        manager = settngs.Manager()
        manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        manager_unknown = settngs.Manager()
        manager_unknown.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
        # This manager doesn't know about this group
        # manager_unknown.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

        defaults = manager.get_namespace(manager.defaults(), file=True, cmdline=True)
        defaults.values.test = 'fail'  # Not defined in manager, should be removed
        defaults.values.persistent__hello = 'success'  # Not defined in manager, should stay

        normalized, _ = manager_unknown.get_namespace(defaults.values, file=True)

        assert not hasattr(normalized, 'test')
        assert hasattr(normalized, 'tst__test')
        assert normalized.tst__test == 'hello'
        assert normalized.persistent__hello == 'success'
        assert normalized.persistent__world == 'world'


def test_get_namespace_with_namespace(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults, _ = settngs_manager.get_namespace(argparse.Namespace(test='success'), file=True)
    assert defaults.test == 'success'


def test_get_namespace_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults(), file=True)
    assert defaults.tst__test == 'hello'


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
    lambda definitions: settngs.Config(argparse.Namespace(tst__test='fail', tst__test2='success'), definitions),
    lambda definitions: argparse.Namespace(tst__test='fail', tst__test2='success'),
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


class test_enum(Enum):
    test = auto()


class test_type(int):
    ...


def _typed_function(something: str) -> test_type:  # pragma: no cover
    return test_type()


def _typed_list_generic_function(something: test_type) -> List[test_type]:  # pragma: no cover
    return [test_type()]


def _typed_list_function() -> List:   # type: ignore[type-arg] # pragma: no cover
    return []


def _typed_set_function() -> Set:  # type: ignore[type-arg] # pragma: no cover
    return set()


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

    def __call__(self, parser, namespace, values, option_string=None):  # pragma: no cover
        setattr(namespace, self.dest, 'Something')


types = (
    (0, settngs.Setting('-t', '--test'), str, True),
    (1, settngs.Setting('-t', '--test', cmdline=False), 'Any', True),
    (2, settngs.Setting('-t', '--test', default=1, file=True, cmdline=False), int, False),
    (3, settngs.Setting('-t', '--test', default='test'), str, False),
    (4, settngs.Setting('-t', '--test', default='test', file=True, cmdline=False), str, False),
    (5, settngs.Setting('-t', '--test', action='count'), int, True),
    (6, settngs.Setting('-t', '--test', action='append'), List[str], True),
    (7, settngs.Setting('-t', '--test', action='extend'), List[str], True),
    (8, settngs.Setting('-t', '--test', nargs='+'), List[str], True),
    (9, settngs.Setting('-t', '--test', nargs='+', type=pathlib.Path), List[pathlib.Path], True),
    (10, settngs.Setting('-t', '--test', nargs='+', type=test_enum), List[test_enum], True),
    (11, settngs.Setting('-t', '--test', action='store_const', const=1), int, True),
    (12, settngs.Setting('-t', '--test', action='append_const', const=1), List[int], True),
    (13, settngs.Setting('-t', '--test', action='store_true'), bool, False),
    (14, settngs.Setting('-t', '--test', action='store_false'), bool, False),
    (15, settngs.Setting('-t', '--test', action=argparse.BooleanOptionalAction), bool, True),
    (16, settngs.Setting('-t', '--test', action=_customAction), 'Any', True),
    (17, settngs.Setting('-t', '--test', type=test_enum), test_enum, True),
    (18, settngs.Setting('-t', '--test', type=int), int, True),
    (19, settngs.Setting('-t', '--test', type=int, nargs='+'), List[int], True),
    (20, settngs.Setting('-t', '--test', type=_typed_function), test_type, True),
    (21, settngs.Setting('-t', '--test', type=_untyped_function, default=1), int, False),
    (22, settngs.Setting('-t', '--test', type=_untyped_function, default=[1]), List[int], False),
    (23, settngs.Setting('-t', '--test', type=_untyped_function), 'Any', True),
    (24, settngs.Setting('-t', '--test', type=_untyped_function, default={1}), Set[int], False),
    (25, settngs.Setting('-t', '--test', action='append', type=int), List[int], True),
    (26, settngs.Setting('-t', '--test', action='extend', type=int, nargs=2), List[int], True),
    (27, settngs.Setting('-t', '--test', action='append', type=int, nargs=2), List[List[int]], True),
    (28, settngs.Setting('-t', '--test', action='extend', nargs='+'), List[str], True),
    (29, settngs.Setting('-t', '--test', action='extend', type=_typed_list_generic_function), List[test_type], True),
    (30, settngs.Setting('-t', '--test', action='extend', type=_typed_list_function), List, True),
    (31, settngs.Setting('-t', '--test', action='extend', type=_typed_set_function), Set, True),
    (32, settngs.Setting('-t', '--test', action='help'), None, True),
    (33, settngs.Setting('-t', '--test', action='version'), None, True),
)


@pytest.mark.parametrize('num,setting,typ,noneable_expected', types)
def test_guess_type(num, setting, typ, noneable_expected):
    x = setting._guess_type()
    guessed_type, noneable = x
    assert guessed_type == typ
    assert noneable == noneable_expected


class TypeResult(NamedTuple):
    extra_imports: str
    typ: str


expected_src = '''from __future__ import annotations

import settngs
{extra_imports}

class SettngsNS(settngs.TypedNS):
    test__test: {typ}
'''

settings = (
    (0, lambda parser: parser.add_setting('-t', '--test'), TypeResult(extra_imports='', typ='str | None')),
    (1, lambda parser: parser.add_setting('-t', '--test', cmdline=False), TypeResult(extra_imports='import typing\n', typ='typing.Any')),
    (2, lambda parser: parser.add_setting('-t', '--test', default=1, file=True, cmdline=False), TypeResult(extra_imports='', typ='int')),
    (3, lambda parser: parser.add_setting('-t', '--test', default='test'), TypeResult(extra_imports='', typ='str')),
    (4, lambda parser: parser.add_setting('-t', '--test', default='test', file=True, cmdline=False), TypeResult(extra_imports='', typ='str')),
    (5, lambda parser: parser.add_setting('-t', '--test', action='count'), TypeResult(extra_imports='', typ='int | None')),
    (6, lambda parser: parser.add_setting('-t', '--test', action='append'), TypeResult(extra_imports='', typ=f'{List[str]} | None')),
    (7, lambda parser: parser.add_setting('-t', '--test', action='extend'), TypeResult(extra_imports='', typ=f'{List[str]} | None')),
    (8, lambda parser: parser.add_setting('-t', '--test', nargs='+'), TypeResult(extra_imports='', typ=f'{List[str]} | None')),
    (9, lambda parser: parser.add_setting('-t', '--test', nargs='+', type=pathlib.Path), TypeResult(extra_imports='import pathlib._local\n' if sys.version_info[:2] == (3, 13) else 'import pathlib\n', typ=f'{List[pathlib.Path]} | None')),
    (10, lambda parser: parser.add_setting('-t', '--test', nargs='+', type=test_enum), TypeResult(extra_imports='import tests.settngs_test\n', typ=f'{List[test_enum]} | None')),
    (11, lambda parser: parser.add_setting('-t', '--test', action='store_const', const=1), TypeResult(extra_imports='', typ='int | None')),
    (12, lambda parser: parser.add_setting('-t', '--test', action='append_const', const=1), TypeResult(extra_imports='', typ=f'{List[int]} | None')),
    (13, lambda parser: parser.add_setting('-t', '--test', action='store_true'), TypeResult(extra_imports='', typ='bool')),
    (14, lambda parser: parser.add_setting('-t', '--test', action='store_false'), TypeResult(extra_imports='', typ='bool')),
    (15, lambda parser: parser.add_setting('-t', '--test', action=argparse.BooleanOptionalAction), TypeResult(extra_imports='', typ='bool | None')),
    (16, lambda parser: parser.add_setting('-t', '--test', action=_customAction), TypeResult(extra_imports='import typing\n', typ='typing.Any')),
    (17, lambda parser: parser.add_setting('-t', '--test', type=test_enum), TypeResult(extra_imports='import tests.settngs_test\n', typ='tests.settngs_test.test_enum | None')),
    (18, lambda parser: parser.add_setting('-t', '--test', type=int), TypeResult(extra_imports='', typ='int | None')),
    (19, lambda parser: parser.add_setting('-t', '--test', type=int, nargs='+'), TypeResult(extra_imports='', typ=f'{List[int]} | None')),
    (20, lambda parser: parser.add_setting('-t', '--test', type=_typed_function), TypeResult(extra_imports='import tests.settngs_test\n', typ='tests.settngs_test.test_type | None')),
    (21, lambda parser: parser.add_setting('-t', '--test', type=_untyped_function, default=1), TypeResult(extra_imports='', typ='int')),
    (22, lambda parser: parser.add_setting('-t', '--test', type=_untyped_function, default=[1]), TypeResult(extra_imports='', typ=f'{List[int]}')),
    (23, lambda parser: parser.add_setting('-t', '--test', type=_untyped_function), TypeResult(extra_imports='import typing\n', typ='typing.Any')),
    (24, lambda parser: parser.add_setting('-t', '--test', type=_untyped_function, default={1}), TypeResult(extra_imports='', typ=f'{Set[int]}')),
    (25, lambda parser: parser.add_setting('-t', '--test', action='append', type=int), TypeResult(extra_imports='', typ=f'{List[int]} | None')),
    (26, lambda parser: parser.add_setting('-t', '--test', action='extend', type=int, nargs=2), TypeResult(extra_imports='', typ=f'{List[int]} | None')),
    (27, lambda parser: parser.add_setting('-t', '--test', action='append', type=int, nargs=2), TypeResult(extra_imports='', typ=f'{List[List[int]]} | None')),
    (28, lambda parser: parser.add_setting('-t', '--test', action='extend', nargs='+'), TypeResult(extra_imports='', typ=f'{List[str]} | None')),
    (29, lambda parser: parser.add_setting('-t', '--test', action='extend', type=_typed_list_generic_function), TypeResult(extra_imports='import tests.settngs_test\n', typ=f'{List[test_type]} | None')),
    (30, lambda parser: parser.add_setting('-t', '--test', action='extend', type=_typed_list_function), TypeResult(extra_imports='', typ=f'{settngs._type_to_string(List)[0]} | None')),
    (31, lambda parser: parser.add_setting('-t', '--test', action='extend', type=_typed_set_function), TypeResult(extra_imports='', typ=f'{settngs._type_to_string(Set)[0]} | None')),
)


@pytest.mark.parametrize('num,set_options,expected', settings)
def test_generate_ns(settngs_manager, num, set_options, expected):
    settngs_manager.add_group('test', set_options)

    imports, types = settngs_manager.generate_ns()
    generated_src = '\n\n\n'.join((imports, types))

    assert generated_src == expected_src.format(**expected._asdict())

    ast.parse(generated_src)


expected_src_dict = '''from __future__ import annotations

{extra_imports}

class test(typing.TypedDict):
    test: {typ}


class SettngsDict(typing.TypedDict):
    test: test
'''


@pytest.mark.parametrize('num,set_options,expected', settings)
def test_generate_dict(settngs_manager, num, set_options, expected):
    settngs_manager.add_group('test', set_options)

    imports, types = settngs_manager.generate_dict()
    generated_src = '\n\n\n'.join((imports, types))

    if 'import typing' not in expected.extra_imports:
        expected = TypeResult('import typing\n' + expected.extra_imports, expected.typ)
    assert generated_src == expected_src_dict.format(**expected._asdict())

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
