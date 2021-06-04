#!/usr/bin/env python3

version_tuple = (1, 1)

with open('schedules_tools/version.py') as ver_file:
    exec(ver_file.read())

print(f"%define version {version_tuple[0]}.{version_tuple[1]}")
print(f"%define release_number {version_tuple[2]}")
