#!/usr/bin/env python3

from setuptools import setup


def scm_config():
    def scheme(version):
        if version.distance is None:
            version.distance = 0

        return version.format_with('{tag}.{distance}')

    return {'version_scheme': scheme,
            'write_to': "schedules_tools/version.py",
            'local_scheme': 'dirty-tag'
            }


setup(
    use_scm_version=scm_config
)
