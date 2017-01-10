#!/usr/bin/python
# -*- coding: utf-8 -*-
import os

from setuptools import setup, find_packages

from scripts.setup_utils import write_version, get_rpm_version


project_name = "schedules-tools"
save_version_dirs = ["schedules_tools"]
project_url = "https://github.com/RedHat-Eng-PGM/schedules-tools"
project_author = "Red Hat, Inc."
project_author_email = "pslama@redhat.com"
project_description = "Schedules tools to handle various formats"
package_name = project_name
package_module_name = "schedules_tools"
package_version = ['5.30.0', 1, 'git']  # default


# VERSION - write version only when building from git
if os.path.isdir(".git"):
    # we're building from a git repo -> store version tuple to __init__.py
    if package_version[2] == "git":
        force = True
        package_version[0], package_version[1], package_version[2] = get_rpm_version()

    for i in save_version_dirs:
        file_name = os.path.join(i, "version.py")
        write_version(file_name, package_version)


try:
    f = open('build/version.txt', 'w')
    f.write(package_version[0])
    f = open('build/release.txt', 'w')
    f.write(str(package_version[1]))
    f = open('build/checkout.txt', 'w')
    f.write(package_version[2])
    f.close()
except:
    pass



setup(
    name=package_name,
    url=project_url,
    version=package_version[0],
    author=project_author,
    author_email=project_author_email,
    description=project_description,
    packages=find_packages(exclude=('scripts',)),
    include_package_data=True,
)
