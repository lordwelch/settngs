[![CI](https://github.com/lordwelch/settngs/actions/workflows/build.yaml/badge.svg?branch=main&event=push)](https://github.com/lordwelch/settngs/actions/workflows/build.yaml)
[![GitHub release (latest by date)](https://img.shields.io/github/downloads/lordwelch/settngs/latest/total)](https://github.com/lordwelch/settngs/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/settngs)](https://pypi.org/project/settngs/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/settngs)](https://pypistats.org/packages/settngs)
[![PyPI - License](https://img.shields.io/pypi/l/settngs)](https://opensource.org/licenses/MIT)

# Settngs

This library is an attempt to merge reading flags/options from the commandline (argparse) and settings from a file (json).

It is a modified argparse inspired by how [flake8] loads their settings. Note that this does not attempt to be a drop-in replacement for argparse.

Install with pip
```console
pip install settngs
```


A trivial example is included at the bottom of settngs.py with the output below. For a more complete example see [ComicTagger].
```console
$ python -m settngs
Hello world
$ python -m settngs --hello lordwelch
Hello lordwelch
$ python -m settngs --hello lordwelch -s
Hello lordwelch
Successfully saved settngs to settngs.json
$ python -m settngs
Hello lordwelch
$ python -m settngs -v
Hello lordwelch
merged_namespace.example_verbose=True
$ python -m settngs -v -s
Hello lordwelch
Successfully saved settngs to settngs.json
merged_namespace.example_verbose=True
$ python -m settngs
Hello lordwelch
merged_namespace.example_verbose=True
$ python -m settngs --no-verbose
Hello lordwelch
$ python -m settngs --no-verbose -s
Hello lordwelch
Successfully saved settngs to settngs.json
$ python -m settngs --hello world --no-verbose -s
Hello world
Successfully saved settngs to settngs.json
$ python -m settngs
Hello world
```

settngs.json at the end:
```json
{
  "example": {
    "hello": "world",
    "verbose": false
  }
}
```

## What happened to the 'i'?
PyPi wouldn't let me use 'settings'

[flake8]: https://github.com/PyCQA/flake8
[ComicTagger]: https://github.com/comictagger/comictagger