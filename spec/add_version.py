#!/usr/bin/python3

with open('schedules_tools/version.py') as ver_file:
    exec(ver_file.read())

print("%define version {}\n%define release_number {}\n%define checkout {}".format(*VERSION))
