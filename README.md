# Schedules Tools
Library to handle various schedule sources and storage

[![Test](https://github.com/RedHat-Eng-PGM/python-schedules-tools/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/RedHat-Eng-PGM/python-schedules-tools/actions/workflows/test.yml)
[![Pypi Upload](https://github.com/RedHat-Eng-PGM/python-schedules-tools/actions/workflows/pypi.yml/badge.svg)](https://github.com/RedHat-Eng-PGM/python-schedules-tools/actions/workflows/pypi.yml)
[![Pypi Version](https://img.shields.io/pypi/v/schedules-tools.svg)](https://pypi.org/project/schedules-tools/)

## Pypi Package
https://pypi.org/project/schedules-tools/

## Tests
Smartsheet tests need SMARTSHEET_API_TOKEN env variable.
Run as either:
- tox
- tox -e py
- tox -e py specific.test
- tox -p
- pytest
- pytest specific.test

To regenerate test data:
- tox -e regenerate
