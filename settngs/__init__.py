from __future__ import annotations

import argparse
import copy
import inspect
import json
import logging
import pathlib
import re
import sys
import typing
import warnings
from argparse import Namespace
from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import Generic
from typing import NoReturn
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union

logger = logging.getLogger(__name__)

if sys.version_info < (3, 11):  # pragma: no cover
    from typing_extensions import NamedTuple
else:  # pragma: no cover
    from typing import NamedTuple


if sys.version_info < (3, 9):  # pragma: no cover
    from typing import List
    from typing import _GenericAlias as types_GenericAlias

    def removeprefix(self: str, prefix: str, /) -> str:
        if self.startswith(prefix):
            return self[len(prefix):]
        else:
            return self[:]

    class BooleanOptionalAction(argparse.Action):
        def __init__(
            self,
            option_strings,
            dest,
            default=None,
            type=None,  # noqa: A002
            choices=None,
            required=False,
            help=None,  # noqa: A002
            metavar=None,
        ):

            _option_strings = []
            for option_string in option_strings:
                _option_strings.append(option_string)

                if option_string.startswith('--'):
                    option_string = '--no-' + option_string[2:]
                    _option_strings.append(option_string)

            if help is not None and default is not None and default is not argparse.SUPPRESS:
                help += ' (default: %(default)s)'

            super().__init__(
                option_strings=_option_strings,
                dest=dest,
                nargs=0,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar,
            )

        def __call__(self, parser, namespace, values, option_string=None):  # dead: disable
            if option_string in self.option_strings:
                setattr(namespace, self.dest, not option_string.startswith('--no-'))
else:  # pragma: no cover
    List = list
    from types import GenericAlias as types_GenericAlias
    from argparse import BooleanOptionalAction
    removeprefix = str.removeprefix


def _isnamedtupleinstance(x: Any) -> bool:
    t = type(x)
    b = t.__bases__

    if len(b) != 1 or b[0] != tuple:
        return False

    f = getattr(t, '_fields', None)
    if not isinstance(f, tuple):
        return False

    return all(isinstance(n, str) for n in f)


class Setting:
    def __init__(
        self,
        # From argparse
        *names: str,
        action: type[argparse.Action] | str | None = None,
        nargs: str | int | None = None,
        const: Any | None = None,
        default: Any | None = None,
        type: Callable[..., Any] | None = None,  # noqa: A002
        choices: Sequence[Any] | None = None,
        required: bool | None = None,
        help: str | None = None,  # noqa: A002
        metavar: str | None = None,
        dest: str | None = None,
        # ComicTagger
        display_name: str = '',
        cmdline: bool = True,
        file: bool = True,
        group: str = '',
        exclusive: bool = False,
    ):
        """
        Attributes:
        setting_name:     This is the name used to retrieve this Setting object from a `Config` Definitions dictionary.
                          This only differs from dest when a custom dest is given

        Args:
            *names:       Passed directly to argparse
            action:       Passed directly to argparse
            nargs:        Passed directly to argparse
            const:        Passed directly to argparse
            default:      Passed directly to argparse
            type:         Passed directly to argparse
            choices:      Passed directly to argparse
            required:     Passed directly to argparse
            help:         Passed directly to argparse
            metavar:      Passed directly to argparse, defaults to `dest` upper-cased
            dest:         This is the name used to retrieve the value from a `Config` object as a dictionary.
                          Default to `setting_name`.
            display_name: This is not used by settngs. This is a human-readable name to be used when generating a GUI.
                          Defaults to `dest`.
            cmdline:      If this setting can be set via the commandline
            file:         If this setting can be set via a file
            group:        The group this option is in.
                          This is an internal argument and should only be set by settngs
            exclusive:    If this setting is exclusive to other settings in this group.
                          This is an internal argument and should only be set by settngs
        """
        if not names:
            raise ValueError('names must be specified')
        # We prefix the destination name used by argparse so that there are no conflicts
        # Argument names will still cause an exception if there is a conflict e.g. if '-f' is defined twice
        self.internal_name, self.setting_name, dest, self.flag = self.get_dest(group, names, dest)
        args: Sequence[str] = names

        # We then also set the metavar so that '--config' in the group runtime shows as 'CONFIG' instead of 'RUNTIME_CONFIG'
        if not metavar and action not in ('store_true', 'store_false', 'count', 'help', 'version'):
            if not callable(action) or 'metavar' in inspect.signature(action).parameters.keys():
                metavar = dest.upper()

        # If we are not a flag, no '--' or '-' in front
        # we use internal_name as argparse sets dest to args[0]
        if not self.flag:
            args = tuple((self.internal_name, *names[1:]))

        self.action = action
        self.nargs = nargs
        self.const = const
        self.default = default
        self.type = type
        self.choices = choices
        self.required = required
        self.help = help
        self.metavar = metavar
        self.dest = dest
        self.cmdline = cmdline
        self.file = file
        self.argparse_args = args
        self.group = group
        self.exclusive = exclusive
        self.display_name = display_name or dest

        self.argparse_kwargs = {
            'action': action,
            'nargs': nargs,
            'const': const,
            'default': default,
            'type': type,
            'choices': choices,
            'required': required,
            'help': help,
            'metavar': metavar,
            'dest': self.internal_name if self.flag else None,
        }

    def __str__(self) -> str:  # pragma: no cover
        return f'Setting({self.argparse_args}, type={self.type}, file={self.file}, cmdline={self.cmdline}, kwargs={self.argparse_kwargs})'

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Setting):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def _guess_type(self) -> type | str | None:
        if self.type is None and self.action is None:
            if self.cmdline:
                if self.nargs in ('+', '*') or isinstance(self.nargs, int) and self.nargs > 1:
                    return List[str]
                return str
            else:
                if not self.cmdline and self.default is not None:
                    if not isinstance(self.default, str) and not _isnamedtupleinstance(self.default) and isinstance(self.default, Sequence) and self.default and self.default[0]:
                        try:
                            return cast(type, type(self.default)[type(self.default[0])])
                        except Exception:
                            ...
                    return type(self.default)
                return 'Any'

        if isinstance(self.type, type):
            return self.type

        if self.type is not None:
            type_hints = typing.get_type_hints(self.type)
            if 'return' in type_hints:
                t: type | str = type_hints['return']
                return t
            if self.default is not None:
                if not isinstance(self.default, str) and not _isnamedtupleinstance(self.default) and isinstance(self.default, Sequence) and self.default and self.default[0]:
                    try:
                        return cast(type, type(self.default)[type(self.default[0])])
                    except Exception:
                        ...
                return type(self.default)
            return 'Any'

        if self.action in ('store_true', 'store_false', BooleanOptionalAction):
            return bool

        if self.action in ('store_const',):
            return type(self.const)

        if self.action in ('count',):
            return int

        if self.action in ('append', 'extend'):
            return List[str]

        if self.action in ('append_const',):
            return list  # list[type(self.const)]

        if self.action in ('help', 'version'):
            return None
        return 'Any'

    def get_dest(self, prefix: str, names: Sequence[str], dest: str | None) -> tuple[str, str, str, bool]:
        setting_name = None
        flag = False

        prefix = sanitize_name(prefix)
        for n in names:
            if n.startswith('--'):
                flag = True
                setting_name = sanitize_name(n)
                break
            if n.startswith('-'):
                flag = True

        if setting_name is None:
            setting_name = names[0]
        if dest:
            dest_name = dest
        else:
            dest_name = setting_name
        if not dest_name.isidentifier():
            raise Exception(f'Cannot use {dest_name} in a namespace')

        internal_name = f'{prefix}__{dest_name}'.lstrip('_')
        return internal_name, setting_name, dest_name, flag

    def filter_argparse_kwargs(self) -> dict[str, Any]:
        return {k: v for k, v in self.argparse_kwargs.items() if v is not None}

    def to_argparse(self) -> tuple[Sequence[str], dict[str, Any]]:
        return self.argparse_args, self.filter_argparse_kwargs()


class TypedNS:
    def __init__(self) -> None:
        raise TypeError('TypedNS cannot be instantiated')


class Group(NamedTuple):
    persistent: bool
    v: dict[str, Setting]


Values = Dict[str, Dict[str, Any]]
Definitions = Dict[str, Group]

T = TypeVar('T', bound=Union[Values, Namespace, TypedNS])


class Config(NamedTuple, Generic[T]):
    values: T
    definitions: Definitions


if TYPE_CHECKING:
    ArgParser = Union[argparse._MutuallyExclusiveGroup, argparse._ArgumentGroup, argparse.ArgumentParser]
    ns = Namespace | TypedNS | Config[T] | None


def generate_ns(definitions: Definitions) -> tuple[str, str]:
    initial_imports = ['from __future__ import annotations', '', 'import settngs']
    imports: Sequence[str] | set[str]
    imports = set()

    attributes = []
    for group in definitions.values():
        for setting in group.v.values():
            t = setting._guess_type()
            if t is None:
                continue
            # Default to any
            type_name = 'Any'

            # Take a string as is
            if isinstance(t, str):
                type_name = t
            # Handle generic aliases eg dict[str, str] instead of dict
            elif isinstance(t, types_GenericAlias):
                type_name = str(t)
            # Handle standard type objects
            elif isinstance(t, type):
                type_name = t.__name__
                # Builtin types don't need an import
                if t.__module__ != 'builtins':
                    imports.add(f'import {t.__module__}')
                    # Use the full imported name
                    type_name = t.__module__ + '.' + type_name

            # Expand Any to typing.Any
            if type_name == 'Any':
                type_name = 'typing.Any'

            attribute = f'    {setting.internal_name}: {type_name}'
            if attribute not in attributes:
                attributes.append(attribute)
        # Add a blank line between groups
        if attributes and attributes[-1] != '':
            attributes.append('')

    ns = 'class SettngsNS(settngs.TypedNS):\n'
    # Add a '...' expression if there are no attributes
    if not attributes or all(x == '' for x in attributes):
        ns += '    ...\n'
        attributes = ['']

    # Add the tying import before extra imports
    if 'typing.' in '\n'.join(attributes):
        initial_imports.append('import typing')

    # Remove the possible duplicate typing import
    imports = sorted(list(imports - {'import typing'}))

    # Merge the imports the ns class definition and the attributes
    return '\n'.join(initial_imports + imports), ns + '\n'.join(attributes)


def generate_dict(definitions: Definitions) -> tuple[str, str]:
    initial_imports = ['from __future__ import annotations', '', 'import typing']
    imports: Sequence[str] | set[str]
    imports = set()

    groups_are_identifiers = all(n.isidentifier() for n in definitions.keys())
    classes = []
    for group_name, group in definitions.items():
        attributes = []
        for setting in group.v.values():
            t = setting._guess_type()
            if t is None:
                continue
            # Default to any
            type_name = 'Any'

            # Take a string as is
            if isinstance(t, str):
                type_name = t
            # Handle generic aliases eg dict[str, str] instead of dict
            elif isinstance(t, types_GenericAlias):
                type_name = str(t)
            # Handle standard type objects
            elif isinstance(t, type):
                type_name = t.__name__
                # Builtin types don't need an import
                if t.__module__ != 'builtins':
                    imports.add(f'import {t.__module__}')
                    # Use the full imported name
                    type_name = t.__module__ + '.' + type_name

            # Expand Any to typing.Any
            if type_name == 'Any':
                type_name = 'typing.Any'

            attribute = f'    {setting.dest}: {type_name}'
            if attribute not in attributes:
                attributes.append(attribute)
        if not attributes or all(x == '' for x in attributes):
            attributes = ['    ...']
        classes.append(
            f'class {sanitize_name(group_name)}(typing.TypedDict):\n'
            + '\n'.join(attributes) + '\n\n',
        )

    # Remove the possible duplicate typing import
    imports = sorted(list(imports - {'import typing'}))

    if groups_are_identifiers:
        ns = '\nclass SettngsDict(typing.TypedDict):\n'
        ns += '\n'.join(f'    {n}: {sanitize_name(n)}' for n in definitions.keys())
    else:
        ns = '\nSettngsDict = typing.TypedDict(\n'
        ns += "    'SettngsDict', {\n"
        for n in definitions.keys():
            ns += f'        {n!r}: {sanitize_name(n)},\n'
        ns += '    },\n'
        ns += ')\n'
    # Merge the imports the ns class definition and the attributes
    return '\n'.join(initial_imports + imports), '\n'.join(classes) + ns + '\n'


def sanitize_name(name: str) -> str:
    return re.sub('[' + re.escape(' -_,.!@#$%^&*(){}[]\',."<>;:') + ']+', '_', name).strip('_')


def get_option(options: Values | Namespace | TypedNS, setting: Setting) -> tuple[Any, bool]:
    """
    Helper function to retrieve the value for a setting and if the current value is the default value

    Args:
        options: Dictionary or namespace of options
        setting: The setting object describing the value to retrieve
    """
    if isinstance(options, dict):
        value = options.get(setting.group, {}).get(setting.dest, setting.default)
    else:
        value = getattr(options, setting.internal_name, setting.default)
    return value, value == setting.default


def get_options(config: Config[T], group: str) -> dict[str, Any]:
    """
    Helper function to retrieve all of the values for a group. Only to be used on persistent groups.

    Args:
        config: Dictionary or namespace of options
        group: The name of the group to retrieve
    """
    if isinstance(config[0], dict):
        values: dict[str, Any] = config[0].get(group, {}).copy()
    else:
        internal_names = {x.internal_name: x for x in config[1][group].v.values()}
        values = {}
        v = vars(config[0])
        for name, value in v.items():
            if name.startswith(f'{group}_'):
                if name in internal_names:
                    values[internal_names[name].dest] = value
                else:
                    values[removeprefix(name, f'{group}').lstrip('_')] = value
    return values


def get_groups(values: Values | Namespace | TypedNS) -> list[str]:
    if isinstance(values, dict):
        return [x[0] for x in values.items() if isinstance(x[1], dict)]
    if isinstance(values, Namespace):
        groups = set()
        for name in values.__dict__:
            if '__' in name:
                group, _, _ = name.partition('__')
                groups.add(group.replace('_', ' '))
            else:
                groups.add('')
        return list(groups)
    return []


def _get_internal_definitions(config: Config[T], persistent: bool) -> Definitions:
    definitions = copy.deepcopy(dict(config.definitions))
    if persistent:
        for group_name in get_groups(config.values):
            if group_name not in definitions:
                definitions[group_name] = Group(True, {})
    return defaultdict(lambda: Group(False, {}), definitions)


def normalize_config(
    config: Config[T],
    file: bool = False,
    cmdline: bool = False,
    default: bool = True,
    persistent: bool = True,
) -> Config[Values]:
    """
    Creates an `OptionValues` dictionary with setting definitions taken from `self.definitions`
    and values taken from `raw_options` and `raw_options_2' if defined.
    Values are assigned so if the value is a dictionary mutating it will mutate the original.

    Args:
        config: The Config object to normalize options from
        file: Include file options
        cmdline: Include cmdline options
        default: Include default values in the returned Config object
        persistent: Include unknown keys in persistent groups and unknown groups
    """

    if not file and not cmdline:
        raise ValueError('Invalid parameters: you must set either file or cmdline to True')

    normalized: Values = {}
    options = config.values
    definitions = _get_internal_definitions(config=config, persistent=persistent)
    for group_name, group in definitions.items():
        group_options = {}
        if group.persistent and persistent:
            group_options = get_options(Config(options, definitions), group_name)
        for setting_name, setting in group.v.items():
            if (setting.cmdline and cmdline) or (setting.file and file):
                # Ensures the option exists with the default if not already set
                value, is_default = get_option(options, setting)
                if not is_default or default:
                    # User has set a custom value or has requested the default value
                    group_options[setting.dest] = value
                elif setting.dest in group_options:
                    # default values have been requested to be removed
                    del group_options[setting.dest]
            elif setting.dest in group_options:
                # Setting type (file or cmdline) has not been requested and should be removed for persistent groups
                del group_options[setting.dest]
        normalized[group_name] = group_options

    return Config(normalized, config.definitions)


def parse_file(definitions: Definitions, filename: pathlib.Path) -> tuple[Config[Values], bool]:
    """
    Helper function to read options from a json dictionary from a file.
    This is purely a convenience function.
    If _anything_ more advanced is desired this should be handled by the application.

    Args:
        definitions: A set of setting definitions. See `Config.definitions` and `Manager.definitions`
        filename: A pathlib.Path object to read a json dictionary from
    """
    options: Values = {}
    success = True
    if filename.exists():
        try:
            with filename.open() as file:
                opts = json.load(file)
            if isinstance(opts, dict):
                options = opts
            else:  # pragma: no cover
                raise Exception('Loaded file is not a JSON Dictionary')
        except Exception:  # pragma: no cover
            logger.exception('Failed to load config file: %s', filename)
            success = False
    else:
        logger.info('No config file found')
        success = True

    return normalize_config(Config(options, definitions), file=True), success


def clean_config(
    config: Config[T], file: bool = False, cmdline: bool = False, default: bool = True, persistent: bool = True,
) -> Values:
    """
    Normalizes options and then cleans up empty groups. The returned value is probably JSON serializable.
    Args:
        config: The Config object to normalize options from
        file: Include file options
        cmdline: Include cmdline options
        default: Include default values in the returned Config object
        persistent: Include unknown keys in persistent groups and unknown groups
    """

    cleaned, _ = normalize_config(config, file=file, cmdline=cmdline, default=default, persistent=persistent)
    for group in list(cleaned.keys()):
        if not cleaned[group]:
            del cleaned[group]
    return cleaned


def defaults(definitions: Definitions) -> Config[Values]:
    return normalize_config(Config(Namespace(), definitions), file=True, cmdline=True)


def get_namespace(
    config: Config[T], file: bool = False, cmdline: bool = False, default: bool = True, persistent: bool = True,
) -> Config[Namespace]:
    """
    Returns a Namespace object with options in the form "{group_name}_{setting_name}"
    `config` should already be normalized or be a `Config[Namespace]`.

    Args:
        config: The Config object to turn into a namespace
        file: Include file options
        cmdline: Include cmdline options
        default: Include default values in the returned Config object
        persistent: Include unknown keys in persistent groups and unknown groups
    """
    if not file and not cmdline:
        raise ValueError('Invalid parameters: you must set either file or cmdline to True')

    options: Values
    definitions = _get_internal_definitions(config=config, persistent=persistent)
    if isinstance(config.values, dict):
        options = config.values
    else:
        cfg = normalize_config(config, file=file, cmdline=cmdline, default=default, persistent=persistent)
        options = cfg.values
    namespace = Namespace()
    for group_name, group in definitions.items():

        group_options = get_options(Config(options, definitions), group_name)
        if group.persistent and persistent:
            for name, value in group_options.items():
                if name in group.v:
                    setting_file, setting_cmdline = group.v[name].file, group.v[name].cmdline
                    value, is_default = get_option(options, group.v[name])
                    internal_name = group.v[name].internal_name
                else:
                    setting_file = setting_cmdline = True
                    internal_name, is_default = f'{group_name}__' + sanitize_name(name), None

                if ((setting_cmdline and cmdline) or (setting_file and file)) and (not is_default or default):
                    setattr(namespace, internal_name, value)

        for setting in group.v.values():
            if (setting.cmdline and cmdline) or (setting.file and file):
                value, is_default = get_option(options, setting)

                if not is_default or default:
                    # User has set a custom value or has requested the default value
                    setattr(namespace, setting.internal_name, value)
    return Config(namespace, config.definitions)


def save_file(
    config: Config[T], filename: pathlib.Path,
) -> bool:
    """
    Helper function to save options from a json dictionary to a file
    This is purely a convenience function.
    If _anything_ more advanced is desired this should be handled by the application.

    Args:
        config: The options to save to a json dictionary
        filename: A pathlib.Path object to save the json dictionary to
    """
    file_options = clean_config(config, file=True)
    try:
        if not filename.exists():
            filename.parent.mkdir(exist_ok=True, parents=True)
            filename.touch()

        json_str = json.dumps(file_options, indent=2)
        filename.write_text(json_str + '\n', encoding='utf-8')
    except Exception:
        logger.exception('Failed to save config file: %s', filename)
        return False
    return True


def create_argparser(definitions: Definitions, description: str, epilog: str) -> argparse.ArgumentParser:
    """Creates an :class:`argparse.ArgumentParser` from all cmdline settings"""
    groups: dict[str, ArgParser] = {}
    argparser = argparse.ArgumentParser(
        description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter,
    )

    def get_current_group(setting: Setting) -> ArgParser:

        if not setting.group:
            return argparser

        # Hard coded exception for positional arguments
        # Ensures that the option shows at the top of the help output
        if 'runtime' in setting.group.casefold() and setting.nargs == '*' and not setting.flag:
            return argparser

        if setting.group not in groups:
            if setting.exclusive:
                groups[setting.group] = argparser.add_argument_group(
                    setting.group,
                ).add_mutually_exclusive_group()
            else:
                groups[setting.group] = argparser.add_argument_group(setting.group)
        return groups[setting.group]
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message="'metavar", category=DeprecationWarning, module='argparse')

        for group in definitions.values():
            for setting in group.v.values():
                if not setting.cmdline:
                    continue
                argparse_args, argparse_kwargs = setting.to_argparse()
                current_group: ArgParser = get_current_group(setting)

                current_group.add_argument(*argparse_args, **argparse_kwargs)
    return argparser


def parse_cmdline(
    definitions: Definitions,
    description: str,
    epilog: str,
    args: list[str] | None = None,
    config: ns[T] = None,
) -> Config[Values]:
    """
    Creates an `argparse.ArgumentParser` from cmdline settings in `self.definitions`.
    `args` and `namespace` are passed to `argparse.ArgumentParser.parse_args`

    Args:
        definitions: A set of setting definitions. See `Config.definitions` and `Manager.definitions`
        description: Passed to argparse.ArgumentParser
        epilog: Passed to argparse.ArgumentParser
        args: Passed to argparse.ArgumentParser.parse_args
        config: The Config or Namespace object to use as a Namespace passed to argparse.ArgumentParser.parse_args
    """
    namespace: Namespace | TypedNS | None = None
    if isinstance(config, Config):
        if isinstance(config.values, Namespace):
            namespace = config.values
        else:
            namespace = get_namespace(config, file=True, cmdline=True, default=False)[0]
    else:
        namespace = config

    argparser = create_argparser(definitions, description, epilog)
    ns = argparser.parse_args(args, namespace=namespace)

    return normalize_config(Config(ns, definitions), cmdline=True, file=True)


def parse_config(
    definitions: Definitions,
    description: str,
    epilog: str,
    config_path: pathlib.Path,
    args: list[str] | None = None,
) -> tuple[Config[Values], bool]:
    """
    Convenience function to parse options from a json file and passes the resulting Config object to parse_cmdline.
    This is purely a convenience function.
    If _anything_ more advanced is desired this should be handled by the application.

    Args:
        definitions: A set of setting definitions. See `Config.definitions` and `Manager.definitions`
        description: Passed to argparse.ArgumentParser
        epilog: Passed to argparse.ArgumentParser
        config_path: A `pathlib.Path` object
        args: Passed to argparse.ArgumentParser.parse_args
    """
    file_options, success = parse_file(definitions, config_path)
    cmdline_options = parse_cmdline(
        definitions, description, epilog, args, file_options,
    )

    final_options = normalize_config(cmdline_options, file=True, cmdline=True)
    return final_options, success


class Manager:
    """docstring for Manager"""

    def __init__(self, description: str = '', epilog: str = '', definitions: Definitions | Config[T] | None = None):
        # This one is never used, it just makes MyPy happy
        self.argparser = argparse.ArgumentParser(description=description, epilog=epilog)
        self.description = description
        self.epilog = epilog

        self.definitions: Definitions
        if isinstance(definitions, Config):
            self.definitions = defaultdict(lambda: Group(False, {}), dict(definitions.definitions) or {})
        else:
            self.definitions = defaultdict(lambda: Group(False, {}), dict(definitions or {}))

        self.exclusive_group = False
        self.current_group_name = ''

    def _get_config(self, c: T | Config[T]) -> Config[T]:
        if not isinstance(c, Config):
            return Config(c, self.definitions)
        return c

    def generate_ns(self) -> tuple[str, str]:
        return generate_ns(self.definitions)

    def generate_dict(self) -> tuple[str, str]:
        return generate_dict(self.definitions)

    def create_argparser(self) -> None:
        self.argparser = create_argparser(self.definitions, self.description, self.epilog)

    def add_setting(self, *args: Any, **kwargs: Any) -> None:
        """Passes all arguments through to `Setting`, `group` and `exclusive` are already set"""

        setting = Setting(*args, **kwargs, group=self.current_group_name, exclusive=self.exclusive_group)
        self.definitions[self.current_group_name].v[setting.setting_name] = setting

    def add_group(self, name: str, group: Callable[[Manager], None], exclusive_group: bool = False) -> None:
        """
        The primary way to add define options on this class.

        Args:
            name: The name of the group to define
            group: A function that registers individual options using :meth:`add_setting`
            exclusive_group: If this group is an argparse exclusive group
        """

        if self.current_group_name != '':
            raise ValueError('Sub groups are not allowed')
        self.current_group_name = name
        self.exclusive_group = exclusive_group
        group(self)
        self.current_group_name = ''
        self.exclusive_group = False

    def add_persistent_group(self, name: str, group: Callable[[Manager], None], exclusive_group: bool = False) -> None:
        """
        The primary way to add define options on this class.
        This group allows existing values to persist even if there is no corresponding setting defined for it.

        Args:
            name: The name of the group to define
            group: A function that registers individual options using :meth:`add_setting`
            exclusive_group: If this group is an argparse exclusive group
        """

        if self.current_group_name != '':
            raise ValueError('Sub groups are not allowed')
        self.current_group_name = name
        self.exclusive_group = exclusive_group
        if self.current_group_name in self.definitions:
            if not self.definitions[self.current_group_name].persistent:
                raise ValueError('Group already exists and is not persistent')
        else:
            self.definitions[self.current_group_name] = Group(True, {})
        group(self)
        self.current_group_name = ''
        self.exclusive_group = False

    def exit(self, *args: Any, **kwargs: Any) -> NoReturn:
        """See :class:`~argparse.ArgumentParser`"""
        self.argparser.exit(*args, **kwargs)
        raise SystemExit(99)

    def defaults(self) -> Config[Values]:
        return defaults(self.definitions)

    def clean_config(
        self, config: T | Config[T], file: bool = False, cmdline: bool = False,
    ) -> Values:
        """
        Normalizes options and then cleans up empty groups. The returned value is probably JSON serializable.
        Args:
            config: The Config object to normalize options from
            file: Include file options
            cmdline: Include cmdline options
        """

        return clean_config(self._get_config(config), file=file, cmdline=cmdline)

    def normalize_config(
        self,
        config: T | Config[T],
        file: bool = False,
        cmdline: bool = False,
        default: bool = True,
        persistent: bool = True,
    ) -> Config[Values]:
        """
        Creates an `OptionValues` dictionary with setting definitions taken from `self.definitions`
        and values taken from `raw_options` and `raw_options_2' if defined.
        Values are assigned so if the value is a dictionary mutating it will mutate the original.

        Args:
            config: The Config object to normalize options from
            file: Include file options
            cmdline: Include cmdline options
            default: Include default values in the returned Config object
            persistent: Include unknown keys in persistent groups and unknown groups
        """

        return normalize_config(
            config=self._get_config(config),
            file=file,
            cmdline=cmdline,
            default=default,
            persistent=persistent,
        )

    def get_namespace(
        self,
        config: T | Config[T],
        file: bool = False,
        cmdline: bool = False,
        default: bool = True,
        persistent: bool = True,
    ) -> Config[Namespace]:
        """
        Returns a Namespace object with options in the form "{group_name}_{setting_name}"
        `options` should already be normalized or be a `Config[Namespace]`.
        Throws an exception if the internal_name is duplicated

        Args:
            config: The Config object to turn into a namespace
            file: Include file options
            cmdline: Include cmdline options
            default: Include default values in the returned Config object
            persistent: Include unknown keys in persistent groups and unknown groups
        """

        return get_namespace(
            self._get_config(config), file=file, cmdline=cmdline, default=default, persistent=persistent,
        )

    def parse_file(self, filename: pathlib.Path) -> tuple[Config[Values], bool]:
        """
        Helper function to read options from a json dictionary from a file.
        This is purely a convenience function.
        If _anything_ more advanced is desired this should be handled by the application.

        Args:
            filename: A pathlib.Path object to read a JSON dictionary from
        """

        return parse_file(filename=filename, definitions=self.definitions)

    def save_file(self, config: T | Config[T], filename: pathlib.Path) -> bool:
        """
        Helper function to save options from a json dictionary to a file.
        This is purely a convenience function.
        If _anything_ more advanced is desired this should be handled by the application.

        Args:
            config: The options to save to a json dictionary
            filename: A pathlib.Path object to save the json dictionary to
        """

        return save_file(self._get_config(config), filename=filename)

    def parse_cmdline(self, args: list[str] | None = None, config: ns[T] = None) -> Config[Values]:
        """
        Creates an `argparse.ArgumentParser` from cmdline settings in `self.definitions`.
        `args` and `config` are passed to `argparse.ArgumentParser.parse_args`

        Args:
            args: Passed to argparse.ArgumentParser.parse_args
            config: The Config or Namespace object to use as a Namespace passed to argparse.ArgumentParser.parse_args
        """
        return parse_cmdline(self.definitions, self.description, self.epilog, args, config)

    def parse_config(self, config_path: pathlib.Path, args: list[str] | None = None) -> tuple[Config[Values], bool]:
        """
        Convenience function to parse options from a json file and passes the resulting Config object to parse_cmdline.
        This is purely a convenience function.
        If _anything_ more advanced is desired this should be handled by the application.

        Args:
            config_path: A `pathlib.Path` object
            args: Passed to argparse.ArgumentParser.parse_args
        """
        return parse_config(self.definitions, self.description, self.epilog, config_path, args)


__all__ = [
    'Setting',
    'TypedNS',
    'Group',
    'Values',
    'Definitions',
    'Config',
    'generate_ns',
    'sanitize_name',
    'get_option',
    'get_options',
    'normalize_config',
    'parse_file',
    'clean_config',
    'defaults',
    'get_namespace',
    'save_file',
    'create_argparser',
    'parse_cmdline',
    'parse_config',
    'Manager',
]


def example_group(manager: Manager) -> None:
    manager.add_setting(
        '--hello',
        default='world',
    )
    manager.add_setting(
        '--save', '-s',
        default=False,
        action='store_true',
        file=False,
    )
    manager.add_setting(
        '--verbose', '-v',
        default=False,
        metavar='nothing',
        action=BooleanOptionalAction,  # Added in Python 3.9
    )


def persistent_group(manager: Manager) -> None:
    manager.add_setting(
        '--test', '-t',
        default=False,
        action=BooleanOptionalAction,  # Added in Python 3.9
    )


def _main(args: list[str] | None = None) -> None:
    settings_path = pathlib.Path('./settings.json')
    manager = Manager(description='This is an example', epilog='goodbye!')

    manager.add_group('Example Group', example_group)
    manager.add_persistent_group('persistent', persistent_group)

    file_config, success = manager.parse_file(settings_path)
    file_namespace = manager.get_namespace(file_config, file=True, cmdline=True)

    merged_config = manager.parse_cmdline(args=args, config=file_namespace)
    merged_namespace = manager.get_namespace(merged_config, file=True, cmdline=True)

    print(f'Hello {merged_config.values["Example Group"]["hello"]}')  # noqa: T201
    if merged_namespace.values.Example_Group__save:
        if manager.save_file(merged_config, settings_path):
            print(f'Successfully saved settings to {settings_path}')  # noqa: T201
        else:  # pragma: no cover
            print(f'Failed saving settings to a {settings_path}')  # noqa: T201
    if merged_namespace.values.Example_Group__verbose:
        print(f'{merged_namespace.values.Example_Group__verbose=}')  # noqa: T201


if __name__ == '__main__':
    _main()
