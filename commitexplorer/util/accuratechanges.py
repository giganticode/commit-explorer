# code by @furunkel
from difflib import SequenceMatcher
import whatthepatch
import pandas as pd
from io import StringIO
import numpy as np

class ChangeDiffer:
    def __init__(self, source, target):
        self.nl = "<NL>"
        self.del_tag = "<del>%s</del>"
        self.ins_tag = "<ins>%s</ins>"
        self.rep_tag = "<re>%s</re>"
        self.eql_tag = "<eq>%s</eq>"
        self.rep_sep_tag = "<to>"
        self.source = source  # .replace("\n", "\n%s" % self.nl).split()
        self.target = target  # .replace("\n", "\n%s" % self.nl).split()
        self.change = None
        self.matcher = SequenceMatcher(None, self.source,
                                       self.target)
        self._run()

    def _run(self):
        output = StringIO()
        for tag, i1, i2, j1, j2 in self.matcher.get_opcodes():
            before, after = self.source[i1:i2], self.target[j1:j2]
            if tag == 'replace':
                # Text replaced = deletion + insertion
                output.write(self.rep_tag %
                             (before + self.rep_sep_tag + after))
            elif tag == 'delete':
                # Text deleted
                output.write(self.del_tag % before)
            elif tag == 'insert':
                # Text inserted
                output.write(self.ins_tag % after)
            elif tag == 'equal':
                output.write(self.eql_tag % after)
            else:
                raise ValueError()
        #  # No change
        #  output.append(" ".join(self.source[alo:ahi]))
        self.change = output.getvalue()
    #  diffText = " ".join(diffText.split())
    #  self.change = diffText.replace(self.nl, "\n")

    def get_change(self):
        return self.change


def calculate_changes(patch):
    out_changes = []

    #print("\n"*5)
    #print(patch)
    if pd.isna(patch): return np.nan

    def get_change_type(change):
        if change.old is not None and change.new is None: return 'deleted'
        if change.old is None and change.new is not None: return 'inserted'
        if change.old is not None and change.new is not None: return 'equal'

    for diff in whatthepatch.parse_patch(patch):
        changes = list(diff.changes)
        changes_iter = enumerate(changes)

        while True:
            i, change = next(changes_iter, (-1, None))
            if i == -1: break

            change_type = get_change_type(change)
            line = change.line.strip()

            if i + 1 < len(changes):
                next_change = changes[i+1]
                next_change_type = get_change_type(next_change)
                next_line = next_change.line.strip()
            else:
                next_change = None
                next_change_type = None
                next_line = ''

            if change_type == 'deleted':
                if next_change_type == 'inserted':
                    out_changes.append(ChangeDiffer(line, next_line).get_change())
                    # skip next change
                    i, next_change = next(changes_iter, (-1, None))
                else:
                    out_changes.append(ChangeDiffer(line, '').get_change())
            elif change_type == 'inserted':
                out_changes.append(ChangeDiffer('', line).get_change())
            elif change_type == 'equal':
                pass


    out_changes = ' '.join(out_changes)
    #print(out_changes)
    #print("\n"*5)
    return out_changes