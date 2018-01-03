'''
Created on Feb 15, 2012

@author: pslama
'''
import datetime

from subprocess import Popen, PIPE
from setup_utils import get_rpm_version, get_rpm_version_format, get_git_tag_list


CHANGELOG_FILENAME_PATH = 'spec/changelog.txt'

def get_last_changelog_commit(filename):
    """
    Get last string sequence after dot character from the first line of the filename.
    Returns None if the file does not exist.
    """
    try:
        fd = open(filename, 'r')
    except IOError:
        return None

    first_line = fd.readline().strip()
    fd.close()
    last_commit = first_line.rsplit('.')[-1]
    return last_commit


def get_rpm_log():
    # get existing tags reversed
    try:
        first_tag_commit = get_git_tag_list()[-1]
    except IndexError:
        # no tag - version 1.0.0
        print 'NO git tag where to take version from! Pls set tag.'
        exit()
    
    last_commit =  get_last_changelog_commit(CHANGELOG_FILENAME_PATH)
    if last_commit:
        first_tag_commit = last_commit
    
    proc = Popen(['git', 'log', "--branches='master or stable'",
                  "--pretty=format:* %ct %an <%ae> %h%n- %s%n",
                  '%s..' % first_tag_commit],
                 stdout=PIPE, stderr=PIPE)
    output, err = proc.communicate()
    ver_lines = output.splitlines()
    out = {}
    
    for ver_line in ver_lines:
        if not len(ver_line):
            continue
        elif ver_line[0] == '*':
            timestamp, sep, rest = ver_line[2:].partition(' ')
            actual_ts = timestamp
            rest, sep, commit_hash = rest.rpartition(' ')
            #TODO:3 git log -3 --pretty --walk-reflogs master stable
            date = datetime.date.fromtimestamp(float(timestamp))
            beg_date = date.strftime('%a %b %d %Y')
            ver_date = date.strftime('%Y%m%d')
            new_line = '* %s %s %s' % (
                    beg_date, rest, get_rpm_version_format(get_rpm_version(commit_hash)))
            out[actual_ts] = new_line + '\n'
        elif actual_ts:
            out[actual_ts] += ver_line + '\n'
    
    output = [out[key] for key in sorted(out.iterkeys(), reverse=True)]
    output.append('')
    output = "\n".join(output)
    
    if last_commit:
        fd = open(CHANGELOG_FILENAME_PATH, 'r')
        old_changelog = fd.read()
        fd.close()
        output = "{0}{1}".format(output if output else '', old_changelog)
    
        fd = open(CHANGELOG_FILENAME_PATH, 'w')
        fd.write(output)
        fd.close()
    else:
        fd = open(CHANGELOG_FILENAME_PATH, 'w')
        fd.write(output)
        fd.close()
    
    return output

if __name__ == '__main__':
    print(get_rpm_log())
    
