from __future__ import annotations

import argparse
import json
from collections import defaultdict

import pytest

import settngs
from settngs import Group
from testing.settngs import example
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


def test_get_defaults(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults, _ = settngs_manager.defaults()
    assert defaults['']['test'] == 'hello'


def test_get_namespace(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults())
    assert defaults.test == 'hello'


def test_get_namespace_with_namespace(settngs_manager):
    settngs_manager.add_setting('--test', default='hello')
    defaults, _ = settngs_manager.get_namespace(argparse.Namespace(test='hello'))
    assert defaults.test == 'hello'


def test_get_defaults_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    defaults, _ = settngs_manager.defaults()
    assert defaults['tst']['test'] == 'hello'


def test_get_namespace_group(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    defaults, _ = settngs_manager.get_namespace(settngs_manager.defaults())
    assert defaults.tst_test == 'hello'


def test_cmdline_only(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', file=False))
    settngs_manager.add_group('tst2', lambda parser: parser.add_setting('--test2', default='hello', cmdline=False))

    file_normalized, _ = settngs_manager.normalize_config(settngs_manager.defaults(), file=True)
    cmdline_normalized, _ = settngs_manager.normalize_config(settngs_manager.defaults(), cmdline=True)

    assert 'test' in cmdline_normalized['tst']
    assert 'test2' not in cmdline_normalized['tst2']

    assert 'test' not in file_normalized['tst']
    assert 'test2' in file_normalized['tst2']


def test_normalize(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello'))
    settngs_manager.add_persistent_group('persistent', lambda parser: parser.add_setting('--world', default='world'))

    defaults = settngs_manager.defaults()
    defaults.values['test'] = 'fail'  # Not defined in settngs_manager, should be removed
    defaults.values['persistent']['hello'] = 'success'  # Not defined in settngs_manager, should stay

    defaults_namespace = settngs_manager.get_namespace(settngs_manager.defaults())
    defaults_namespace.values.test = 'fail'  # Not defined in settngs_manager, should be removed
    defaults_namespace.values.persistent_hello = 'success'  # Not defined in settngs_manager, should stay

    normalized, _ = settngs_manager.normalize_config(defaults, file=True)
    normalized_from_namespace = settngs_manager.normalize_config(defaults_namespace, file=True)
    normalized_namespace, _ = settngs_manager.get_namespace(normalized_from_namespace)

    assert 'test' not in normalized
    assert 'tst' in normalized
    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'hello'
    assert normalized['persistent']['hello'] == 'success'

    assert not hasattr(normalized_namespace, 'test')
    assert hasattr(normalized_namespace, 'tst_test')
    assert normalized_namespace.tst_test == 'hello'
    assert normalized_namespace.persistent_hello == 'success'


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


def test_parse_cmdline_with_namespace(settngs_manager):
    settngs_manager.add_group('tst', lambda parser: parser.add_setting('--test', default='hello', cmdline=True))

    normalized, _ = settngs_manager.parse_cmdline(
        ['--test', 'success'], namespace=settngs.Config({'tst': {'test': 'fail'}}, settngs_manager.definitions),
    )

    assert 'test' in normalized['tst']
    assert normalized['tst']['test'] == 'success'


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


def test_adding_to_existing_persistent_group(settngs_manager, tmp_path):
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


def test_example(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings_file = tmp_path / 'settings.json'
    settings_file.touch()

    i = 0
    for args, expected_out, expected_file in example:
        if args == ['manual settings.json']:
            settings_file.unlink()
            settings_file.write_text('{\n  "example": {\n    "hello": "lordwelch",\n    "verbose": true\n  },\n  "persistent": {\n    "test": false,\n    "hello": "world"\n  }\n}\n')
        else:
            settngs._main(args)
            captured = capsys.readouterr()
        assert captured.out == expected_out, f'{i}, {args}'
        assert settings_file.read_text() == expected_file, f'{i}, {args}'
        i += 1
