from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys
from argparse import Namespace
from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from typing import Callable
from typing import Dict
from typing import Generic
from typing import NoReturn
from typing import overload
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union
logger = logging.getLogger(__name__)

if sys.version_info < (3, 11):  # pragma: no cover
    from typing_extensions import NamedTuple
else:  # pragma: no cover
    from typing import NamedTuple


if sys.version_info < (3, 9):  # pragma: no cover
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
    from argparse import BooleanOptionalAction
    removeprefix = str.removeprefix


class Setting:
    def __init__(
        self,
        # From argparse
        *names: str,
        action: type[argparse.Action] | None = None,
        nargs: str | int | None = None,
        const: str | None = None,
        default: str | None = None,
        type: Callable[..., Any] | None = None,  # noqa: A002
        choices: Sequence[Any] | None = None,
        required: bool | None = None,
        help: str | None = None,  # noqa: A002
        metavar: str | None = None,
        dest: str | None = None,
        # ComicTagger
        cmdline: bool = True,
        file: bool = True,
        group: str = '',
        exclusive: bool = False,
    ):
        if not names:
            raise ValueError('names must be specified')
        # We prefix the destination name used by argparse so that there are no conflicts
        # Argument names will still cause an exception if there is a conflict e.g. if '-f' is defined twice
        self.internal_name, dest, flag = self.get_dest(group, names, dest)
        args: Sequence[str] = names

        # We then also set the metavar so that '--config' in the group runtime shows as 'CONFIG' instead of 'RUNTIME_CONFIG'
        if not metavar and action not in ('store_true', 'store_false', 'count'):
            metavar = dest.upper()

        # If we are not a flag, no '--' or '-' in front
        # we prefix the first name with the group as argparse sets dest to args[0]
        # I believe internal name may be able to be used here
        if not flag:
            args = tuple((f'{group}_{names[0]}'.lstrip('_'), *names[1:]))

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
            'dest': self.internal_name if flag else None,
        }

    def __str__(self) -> str:  # pragma: no cover
        return f'Setting({self.argparse_args}, type={self.type}, file={self.file}, cmdline={self.cmdline}, kwargs={self.argparse_kwargs})'

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()

    def get_dest(self, prefix: str, names: Sequence[str], dest: str | None) -> tuple[str, str, bool]:
        dest_name = None
        flag = False

        for n in names:
            if n.startswith('--'):
                flag = True
                dest_name = sanitize_name(n)
                break
            if n.startswith('-'):
                flag = True

        if dest_name is None:
            dest_name = names[0]
        if dest:
            dest_name = dest
        if not dest_name.isidentifier():
            raise Exception('Cannot use {dest_name} in a namespace')

        internal_name = f'{prefix}_{dest_name}'.lstrip('_')
        return internal_name, dest_name, flag

    def filter_argparse_kwargs(self) -> dict[str, Any]:
        return {k: v for k, v in self.argparse_kwargs.items() if v is not None}

    def to_argparse(self) -> tuple[Sequence[str], dict[str, Any]]:
        return self.argparse_args, self.filter_argparse_kwargs()


class Group(NamedTuple):
    persistent: bool
    v: dict[str, Setting]


Values = Dict[str, Dict[str, Any]]
Definitions = Dict[str, Group]

T = TypeVar('T', Values, Namespace)


class Config(NamedTuple, Generic[T]):
    values: T
    definitions: Definitions


if TYPE_CHECKING:
    ArgParser = Union[argparse._MutuallyExclusiveGroup, argparse._ArgumentGroup, argparse.ArgumentParser]
    ns = Namespace | Config[T] | None


def sanitize_name(name: str) -> str:
    return re.sub('[' + re.escape(' -_,.!@#$%^&*(){}[]\',."<>;:') + ']+', '-', name).strip('-')


def get_option(options: Values | Namespace, setting: Setting) -> tuple[Any, bool]:
    """
    Helper function to retrieve the value for a setting and if the value is the default value

    Args:
        options: Dictionary or namespace of options
        setting: The setting object describing the value to retrieve
    """
    if isinstance(options, dict):
        value = options.get(setting.group, {}).get(setting.dest, setting.default)
    else:
        value = getattr(options, setting.internal_name, setting.default)
    return value, value == setting.default


def get_options(options: Config[T], group: str) -> dict[str, Any]:
    """
    Helper function to retrieve all of the values for a group. Only to be used on persistent groups.

    Args:
        options: Dictionary or namespace of options
        group: The name of the group to retrieve
    """
    if isinstance(options[0], dict):
        values = options[0].get(group, {}).copy()
    else:
        internal_names = {x.internal_name: x for x in options[1][group].v.values()}
        values = {}
        v = vars(options[0])
        for name, value in v.items():
            if name.startswith(f'{group}_'):
                if name in internal_names:
                    values[internal_names[name].dest] = value
                else:
                    values[removeprefix(name, f'{group}_')] = value

    return values


def normalize_config(
    config: Config[T],
    file: bool = False,
    cmdline: bool = False,
    defaults: bool = True,
    persistent: bool = True,
) -> Config[Values]:
    """
    Creates an `OptionValues` dictionary with setting definitions taken from `self.definitions`
    and values taken from `raw_options` and `raw_options_2' if defined.
    Values are assigned so if the value is a dictionary mutating it will mutate the original.

    Args:
        raw_options: The dict or Namespace to normalize options from
        definitions: The definition of the options
        file: Include file options
        cmdline: Include cmdline options
        defaults: Include default values in the returned dict
        persistent: Include unknown keys in persistent groups
    """

    normalized: Values = {}
    options, definitions = config
    for group_name, group in definitions.items():
        group_options = {}
        if group.persistent and persistent:
            group_options = get_options(config, group_name)
        for setting_name, setting in group.v.items():
            if (setting.cmdline and cmdline) or (setting.file and file):
                # Ensures the option exists with the default if not already set
                value, default = get_option(options, setting)
                if not default or default and defaults:
                    group_options[setting_name] = value
                elif setting_name in group_options:
                    del group_options[setting_name]
        normalized[group_name] = group_options
    return Config(normalized, definitions)


def parse_file(definitions: Definitions, filename: pathlib.Path) -> tuple[Config[Values], bool]:
    """
    Helper function to read options from a json dictionary from a file
    Args:
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
        except Exception:
            logger.exception('Failed to load config file: %s', filename)
            success = False
    else:
        logger.info('No config file found')
        success = True

    return (normalize_config(Config(options, definitions), file=True), success)


def clean_config(
    config: Config[T], file: bool = False, cmdline: bool = False,
) -> Values:
    """
    Normalizes options and then cleans up empty groups
    Args:
        options:
        file:
        cmdline:

    Returns:

    """

    clean_options, definitions = normalize_config(config, file=file, cmdline=cmdline)
    for group in list(clean_options.keys()):
        if not clean_options[group]:
            del clean_options[group]
    return clean_options


def defaults(definitions: Definitions) -> Config[Values]:
    return normalize_config(Config(Namespace(), definitions), file=True, cmdline=True)


def get_namespace(config: Config[T], defaults: bool = True, persistent: bool = True) -> Config[Namespace]:
    """
    Returns an Namespace object with options in the form "{group_name}_{setting_name}"
    `options` should already be normalized.
    Throws an exception if the internal_name is duplicated

    Args:
        options: Normalized options to turn into a Namespace
        defaults: Include default values in the returned dict
        persistent: Include unknown keys in persistent groups
    """

    if isinstance(config.values, Namespace):
        options, definitions = normalize_config(config)
    else:
        options, definitions = config
    namespace = Namespace()
    for group_name, group in definitions.items():
        if group.persistent and persistent:
            group_options = get_options(config, group_name)
            for name, value in group_options.items():
                if name in group.v:
                    internal_name, default = group.v[name].internal_name, group.v[name].default == value
                else:
                    internal_name, default = f'{group_name}_' + sanitize_name(name), None

                if hasattr(namespace, internal_name):
                    raise Exception(f'Duplicate internal name: {internal_name}')

                if not default or default and defaults:
                    setattr(namespace, internal_name, value)

        else:
            for setting_name, setting in group.v.items():
                if hasattr(namespace, setting.internal_name):
                    raise Exception(f'Duplicate internal name: {setting.internal_name}')
                value, default = get_option(options, setting)

                if not default or default and defaults:
                    setattr(namespace, setting.internal_name, value)
    return Config(namespace, definitions)


def save_file(
    config: Config[T], filename: pathlib.Path,
) -> bool:
    """
    Helper function to save options from a json dictionary to a file
    Args:
        options: The options to save to a json dictionary
        filename: A pathlib.Path object to save the json dictionary to
    """
    file_options = clean_config(config, file=True)
    if not filename.exists():
        filename.parent.mkdir(exist_ok=True, parents=True)
        filename.touch()

    try:
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
    for group_name, group in definitions.items():
        for setting_name, setting in group.v.items():
            if setting.cmdline:
                argparse_args, argparse_kwargs = setting.to_argparse()
                current_group: ArgParser = argparser
                if setting.group:
                    if setting.group not in groups:
                        if setting.exclusive:
                            groups[setting.group] = argparser.add_argument_group(
                                setting.group,
                            ).add_mutually_exclusive_group()
                        else:
                            groups[setting.group] = argparser.add_argument_group(setting.group)

                    # hard coded exception for files
                    if not (setting.group == 'runtime' and setting.nargs == '*'):
                        current_group = groups[setting.group]
                current_group.add_argument(*argparse_args, **argparse_kwargs)
    return argparser


def parse_cmdline(
    definitions: Definitions,
    description: str,
    epilog: str,
    args: list[str] | None = None,
    config: Namespace | Config[T] | None = None,
) -> Config[Values]:
    """
    Creates an `argparse.ArgumentParser` from cmdline settings in `self.definitions`.
    `args` and `namespace` are passed to `argparse.ArgumentParser.parse_args`

    Args:
        args: Passed to argparse.ArgumentParser.parse
        namespace: Passed to argparse.ArgumentParser.parse
    """
    namespace = None
    if isinstance(config, Config):
        if isinstance(config.values, Namespace):
            namespace = config.values
        else:
            namespace = get_namespace(config, defaults=False)[0]
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
    file_options, success = parse_file(definitions, config_path)
    cmdline_options = parse_cmdline(
        definitions, description, epilog, args, get_namespace(file_options, defaults=False),
    )

    final_options = normalize_config(cmdline_options, file=True, cmdline=True)
    return (final_options, success)


class Manager:
    """docstring for Manager"""

    def __init__(self, description: str = '', epilog: str = '', definitions: Definitions | Config[T] | None = None):
        # This one is never used, it just makes MyPy happy
        self.argparser = argparse.ArgumentParser(description=description, epilog=epilog)
        self.description = description
        self.epilog = epilog

        if isinstance(definitions, Config):
            self.definitions = definitions.definitions
        else:
            self.definitions = defaultdict(lambda: Group(False, {}), definitions or {})

        self.exclusive_group = False
        self.current_group_name = ''

    def create_argparser(self) -> None:
        self.argparser = create_argparser(self.definitions, self.description, self.epilog)

    def add_setting(self, *args: Any, **kwargs: Any) -> None:
        """Takes passes all arguments through to `Setting`, `group` and `exclusive` are already set"""
        setting = Setting(*args, **kwargs, group=self.current_group_name, exclusive=self.exclusive_group)
        self.definitions[self.current_group_name].v[setting.dest] = setting

    def add_group(self, name: str, group: Callable[[Manager], None], exclusive_group: bool = False) -> None:
        """
        The primary way to add define options on this class

        Args:
            name: The name of the group to define
            group: A function that registers individual options using :meth:`add_setting`
            exclusive_group: If this group is an argparse exclusive group
        """
        self.current_group_name = name
        self.exclusive_group = exclusive_group
        group(self)
        self.current_group_name = ''
        self.exclusive_group = False

    def add_persistent_group(self, name: str, group: Callable[[Manager], None], exclusive_group: bool = False) -> None:
        """
        The primary way to add define options on this class

        Args:
            name: The name of the group to define
            group: A function that registers individual options using :meth:`add_setting`
            exclusive_group: If this group is an argparse exclusive group
        """
        self.current_group_name = name
        self.exclusive_group = exclusive_group
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
        self, options: T | Config[T], file: bool = False, cmdline: bool = False,
    ) -> Values:
        if isinstance(options, Config):
            config = options
        else:
            config = Config(options, self.definitions)
        return clean_config(config, file=file, cmdline=cmdline)

    def normalize_config(
        self,
        options: T | Config[T],
        file: bool = False,
        cmdline: bool = False,
        defaults: bool = True,
    ) -> Config[Values]:
        if isinstance(options, Config):
            config = options
        else:
            config = Config(options, self.definitions)
        return normalize_config(
            config=config,
            file=file,
            cmdline=cmdline,
            defaults=defaults,
        )

    @overload
    def get_namespace(self, options: Values, defaults: bool = True) -> Namespace:
        ...

    @overload
    def get_namespace(self, options: Config[Values], defaults: bool = True) -> Config[Namespace]:
        ...

    def get_namespace(self, options: Values | Config[Values], defaults: bool = True) -> Config[Namespace] | Namespace:
        if isinstance(options, Config):
            self.definitions = options[1]
            return get_namespace(options, defaults=defaults)
        else:
            return get_namespace(Config(options, self.definitions), defaults=defaults)

    def parse_file(self, filename: pathlib.Path) -> tuple[Config[Values], bool]:
        return parse_file(filename=filename, definitions=self.definitions)

    def save_file(self, options: T | Config[T], filename: pathlib.Path) -> bool:
        if isinstance(options, Config):
            return save_file(options, filename=filename)
        return save_file(Config(options, self.definitions), filename=filename)

    def parse_cmdline(self, args: list[str] | None = None, namespace: ns[T] = None) -> Config[Values]:
        return parse_cmdline(self.definitions, self.description, self.epilog, args, namespace)

    def parse_config(self, config_path: pathlib.Path, args: list[str] | None = None) -> tuple[Config[Values], bool]:
        return parse_config(self.definitions, self.description, self.epilog, config_path, args)


def example(manager: Manager) -> None:
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
        action=BooleanOptionalAction,  # Added in Python 3.9
    )


def persistent(manager: Manager) -> None:
    manager.add_setting(
        '--test', '-t',
        default=False,
        action=BooleanOptionalAction,  # Added in Python 3.9
    )


def _main(args: list[str] | None = None) -> None:
    settings_path = pathlib.Path('./settings.json')
    manager = Manager(description='This is an example', epilog='goodbye!')

    manager.add_group('example', example)
    manager.add_persistent_group('persistent', persistent)

    file_config, success = manager.parse_file(settings_path)
    file_namespace = manager.get_namespace(file_config)

    merged_config = manager.parse_cmdline(args=args, namespace=file_namespace)
    merged_namespace = manager.get_namespace(merged_config)

    print(f'Hello {merged_config.values["example"]["hello"]}')  # noqa: T201
    if merged_namespace.values.example_save:
        if manager.save_file(merged_config, settings_path):
            print(f'Successfully saved settings to {settings_path}')  # noqa: T201
        else:
            print(f'Failed saving settings to a {settings_path}')  # noqa: T201
    if merged_namespace.values.example_verbose:
        print(f'{merged_namespace.values.example_verbose=}')  # noqa: T201


if __name__ == '__main__':
    _main()
