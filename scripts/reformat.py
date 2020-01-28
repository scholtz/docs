#!/usr/bin/env python3
# rm -rf goal && mkdir goal && goal generate-docs goal && ./reformat.py -path goal

import argparse    
import os    
import os.path
import pprint
import re
import shutil
import sys
import tempfile
from pathlib import Path
pp = pprint.PrettyPrinter(indent=4)

parser = argparse.ArgumentParser(description='Reformat markdown files to display in mkdocs.')    
parser.add_argument('-doc-dir', required=True, help='Path to document directory.')
parser.add_argument('-cmd', required=False, help='Full path to command. If provided the doc-dir will be emptied and new markdown files will be generated with \'cmd generate-docs <doc-dir>\'')

def process_markdown_file(new_file, original_name, goal_depth, with_subcommand):
    """ Update markdown links to use relative paths in different directories. """
    with tempfile.NamedTemporaryFile(mode='w', dir='.', delete=False) as tmp, \
            open(new_file, 'r') as f:
        title=original_name.split('.')[0].replace('_', ' ')
        tmp.write("title: %s\n---\n" % title)

        for line in f:
            result = line
            m = re.search('(^\* \[.*\]\()(.*)(\).*$)', result)
            # Most lines wont match, write them unmodified
            if m != None:
                # Grab the command, i.e. 'goal' in 'goal.md', or 'delete' in 'goal_account_multisig_delete.md'

                # Find out how many levels away the link is (siblings need ../, parents need ../../)
                link_parts = m.group(2).split('.')[0].split('_')
                subcommand = link_parts[-1]
                prefix_mul = goal_depth - link_parts.index(subcommand) + 2

                # Subcommands have an extra level of nesting
                if subcommand in with_subcommand:
                    link = '../'*prefix_mul + ((subcommand + '/')*2)
                else:
                    link = '../'*prefix_mul + subcommand + '/'
                result = "%s%s%s" % (m.group(1), link, m.group(3))
            tmp.write(result + "\n")
        os.replace(tmp.name, new_file)
    

def process(dirpath):
    """ move files into a directory structure and add .pages files. """
    with_subcommand = []
    moved_files = []
    files = os.listdir(dirpath)
    for f in files:
        parts = f.split('_')
        new_name=parts.pop()
        root_path='/'.join(parts)

        # If this is a "root" file, append one more directory.
        # For example "goal_account.md" is a root because of commands like "goal_account_new.md"
        root_check = parts.copy()
        root_check.append(re.sub('\.md', '', new_name))
        extended_path = '_'.join(root_check) + '_'
        is_root = any(extended_path in s for s in files)
        if is_root:
            with_subcommand.append(root_check[-1])
            parts=root_check
            root_path='/'.join(parts)
        try:
            os.makedirs(dirpath + '/' + root_path)
        except FileExistsError:
            pass # this is expected to happen.

        new_file = dirpath + '/' + root_path + '/' + new_name
        os.rename(dirpath + '/' + f, new_file)
        moved_files.append((new_file, len(parts)-1, f))

        # Make sure root file is displayed first in the navigation par
        if is_root:
            with open(dirpath + '/' + root_path + '/.pages', 'w') as f:
                f.write('title: %s\n' % ' '.join(parts))
                f.write('arrange:\n - %s' % new_name)
    # Fix the links at the very end so that we know which ones have subcommands
    for f,depth,original_name in moved_files:
        process_markdown_file(f, original_name, depth, with_subcommand)
    return len(moved_files)

def fix_root(num_files_modified, path):
    """
    The algorithm puts everything one directory too deep, move it up.
    """
    files=[f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    directories=[f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]

    if num_files_modified == 1 and len(files) == 1:
        p=Path(path)
        pp.pprint(p)
        shutil.move(os.path.join(path, files[0]), os.path.join(Path(path).parents[0], files[0]))
        shutil.rmtree(path)
        return

    if len(files) != 0:
        print("WRONG NUMBER OF FILES IN ROOT PATH: %d" % len(files))
        return
    if len(directories) != 1:
        print("WRONG NUMBER OF DIRECTORIES IN ROOT PATH: %d" % len(directories))
        return

    extra_dir = path + '/' + directories[0]
    shutil.move(extra_dir, path + '.tmp')
    os.rmdir(path)
    shutil.move(path + '.tmp', path)


if __name__ == "__main__":
    args = parser.parse_args()

    if os.sep != '/':
        print("Wont work on this system.")
        sys.exit(1)
    if not os.path.isdir(args.doc_dir):
        os.makedirs(args.doc_dir)

    # Don't break if a trailing slash is provided.
    if args.doc_dir[-1] is '/':
        args.doc_dir = args.doc_dir[:-1]

    # Check if we should regenerate the markdown files
    if args.cmd != None:
        print("Deleting directory: %s" % args.doc_dir)
        shutil.rmtree(args.doc_dir)
        os.makedirs(args.doc_dir)
        os.system('%s generate-docs %s' % (args.cmd, args.doc_dir))

    num_files_modified = process(args.doc_dir)
    # No need to fix_root if there are subcommands.
    fix_root(num_files_modified, args.doc_dir)

    print("Finished formatting %d files." % num_files_modified)