import subprocess
import functools
import re

from subprocess import Popen, PIPE

DEFAULT_VERSION = '1.0.0'


def write_version(file_name, version_tuple):
    fo = open(file_name, "w")
    fo.write('VERSION = ("%s", %s, "%s")\n' % tuple(version_tuple))
    fo.close()
    
def read_version(file_name):
    with open(file_name, "r") as f:
        match = re.match('^VERSION[^(]*\("([^"]+)", ([^,]+), "([^"]+)"\)', f.read())
        if match:
            return match.groups()
    


def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer


@memoize
def get_git_tag_list():
    # get existing tags reversed
    proc = Popen(['git', 'for-each-ref', '--format=%(refname)', '--sort=-taggerdate', 'refs/tags'], stdout=PIPE, stderr=PIPE)
    output = proc.communicate()[0].strip()
    tags = output.splitlines()

    for idx, tag in enumerate(tags):
        tags[idx] = tags[idx][10:]

    return tags


@memoize
def get_tag_rev_number(tag):
    proc = Popen(['git', 'rev-list', '--abbrev-commit', '-n 1', tag],
                 stdout=PIPE, stderr=PIPE)
    tag_rev = proc.communicate()[0].strip()
    return tag_rev


@memoize
def get_git_date():
    """Return git last commit date in YYYYMMDD format."""
    cmd = "git log -n 1 --pretty=format:%ci"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Not a git repository")
    lines = proc.stdout.read().strip().split("\n")
    return lines[0].split(" ")[0].replace("-", "")


@memoize
def get_git_version():
    """Return git abbreviated commit hash."""
    cmd = "git log -n 1 --pretty=format:%h"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Not a git repository")
    lines = proc.stdout.read().strip().split("\n")
    return lines[0]


def get_rpm_version(head_rev=None):
    # get current head hash
    if not head_rev:
        head_rev = get_git_version()

    # default
    version = DEFAULT_VERSION
    rel_number = 1

    for tag in get_git_tag_list():
        # get tag rev number
        tag_rev = get_tag_rev_number(tag)

        if head_rev == tag_rev:
            # we're on tag -> release number = 1
            version = tag
            rel_number = 1
            break
        else:
            proc = Popen(['git', 'rev-list',  '--no-merges', '%s..%s' % (tag, head_rev)],
                         stdout=PIPE, stderr=PIPE)
            output = proc.communicate()[0].strip().splitlines()
            count = len(output)
            if int(count) > 0:
                version = tag
                rel_number = count + 1
                break
    git_string = 'git%s.%s' % (get_git_date(), head_rev)
    return version, rel_number, git_string


def get_rpm_version_format(ver_tuple):
    if not ver_tuple:
        ver_tuple = get_rpm_version()
    (version, rel_number, git_string) = ver_tuple
    return '%s-%s.%s' % (version, rel_number, git_string)
