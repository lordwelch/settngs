from __future__ import annotations

import argparse
import json

import pytest

import settngs
from testing.settngs import failure
from testing.settngs import success


@pytest.fixture
def settngs_manager():
    manager = settngs.Manager()
    yield manager


def test_settngs_manager():
    manager = settngs.Manager()
    defaults = manager.defaults()
    assert manager is not None and defaults is not None


@pytest.mark.parametrize('arguments, expected', success)
def test_setting_success(arguments, expected):
    assert vars(settngs.Setting(*arguments[0], **arguments[1])) == expected


@pytest.mark.parametrize('arguments, exception', failure)
def test_setting_failure(arguments, exception):
    with exception:
        settngs.Setting(*arguments[0], **arguments[1])


def test_add_setting(settngs_manager):
    assert settngs_manager.add_setting('--test') is None


def test_get_defaults(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults = settngs_manager.defaults()
    assert defaults['']['test'] == 'hello'


def test_get_namespace(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults = settngs_manager.get_namespace(settngs_manager.defaults())
    assert defaults.test == 'hello'


def test_get_defaults_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    defaults = settngs_manager.defaults()
    assert defaults['tst']['test'] == 'hello'


def test_get_namespace_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    defaults = settngs_manager.get_namespace(settngs_manager.defaults())
    assert defaults.tst_test == 'hello'


def test_cmdline_only(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
    settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

    file_normalized, _ = settngs_manager.normalize_config({}, file=True)
    cmdline_normalized, _ = settngs_manager.normalize_config({}, cmdline=True)

    assert 'test' in cmdline_normalized['tst']
    assert 'test2' not in cmdline_normalized['tst2']

    assert 'test' not in file_normalized['tst']
    assert 'test2' in file_normalized['tst2']


def test_normalize(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))

    defaults = settngs_manager.defaults()
    defaults['test'] = 'fail'  # Not defined in settngs_manager

    defaults_namespace = settngs_manager.get_namespace(defaults)
    defaults_namespace.test = 'fail'

    normalized, _ = settngs_manager.normalize_config(defaults, file=True)
    normalized_namespace = settngs_manager.get_namespace(settngs_manager.normalize_config(defaults, file=True)[0])

    assert 'test' not in normalized
    assert 'tst' in normalized
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'hello'

    assert not hasattr(normalized_namespace, 'test')
    assert hasattr(normalized_namespace, 'tst_test')
    assert normalized_namespace.tst_test == 'hello'


def test_clean_config(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', file=False))
    normalized = settngs_manager.defaults()
    normalized['tst']['test'] = 'success'
    normalized['fail'] = 'fail'

    cleaned = settngs_manager.clean_config(normalized, file=True)

    assert 'fail' not in cleaned
    assert 'tst2' not in cleaned
    assert cleaned['tst']['test'] == 'success'


def test_parse_cmdline(settngs_manager, tmp_path):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=True))

    normalized = settngs_manager.parse_cmdline(['--test', 'success'])

    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_parse_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text(json.dumps({'tst': {'test': 'success'}}))
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))

    normalized, success = settngs_manager.parse_file(settngs_file)

    assert success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_parse_non_existent_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))

    normalized, success = settngs_manager.parse_file(settngs_file)

    assert not success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'hello'


def test_parse_corrupt_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_file.write_text('{')
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))

    normalized, success = settngs_manager.parse_file(settngs_file)

    assert not success
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'hello'


def test_save_file(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    normalized = settngs_manager.defaults()
    normalized['tst']['test'] = 'success'

    success = settngs_manager.save_file(normalized, settngs_file)
    normalized, success_r = settngs_manager.parse_file(settngs_file)

    assert success and success_r
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


def test_save_file_not_seriazable(settngs_manager, tmp_path):
    settngs_file = tmp_path / 'settngs.json'
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=False))
    normalized = settngs_manager.defaults()
    normalized['tst']['test'] = {'fail'}  # Sets are not serializabl

    success = settngs_manager.save_file(normalized, settngs_file)
    normalized, success_r = settngs_manager.parse_file(settngs_file)

    assert not (success and success_r)
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'hello'


@pytest.mark.parametrize(
    'raw, raw2, expected',
    [
        ({'tst': {'test': 'fail'}}, argparse.Namespace(tst_test='success'), 'success'),
        # hello is default so is not used in raw_options_2
        ({'tst': {'test': 'success'}}, argparse.Namespace(tst_test='hello'), 'success'),
        (argparse.Namespace(tst_test='fail'), {'tst': {'test': 'success'}}, 'success'),
        (argparse.Namespace(tst_test='success'), {'tst': {'test': 'hello'}}, 'success'),
    ],
)
def test_normalize_merge(raw, raw2, expected, settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))

    normalized, _ = settngs_manager.normalize_config(raw, file=True, raw_options_2=raw2)

    assert normalized['tst']['test'] == expected


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
