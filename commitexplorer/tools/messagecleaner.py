import re
from collections import Counter
from dataclasses import field, dataclass
from typing import List, Optional, Dict

import nltk
import pydriller

from commitexplorer.common import Tool

from typing import Any, Set

import pandas as pd
from nltk import RegexpTokenizer


from nltk.corpus import stopwords
nltk.download('stopwords')
stop_words = set(stopwords.words('english'))


ISSUE_REGEX = '(([A-Z]+\-)?[0-9]+)'
URL_REGEX = "((http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-]))( )?"

IDENTIFIER_REGEX = "[_a-zA-Z][_a-zA-Z0-9]*"
COMPOUND_IDENTIFIER_REGEX = f"{IDENTIFIER_REGEX}[_A-Z][a-z]+[_a-zA-Z0-9]*"
PATH=f'({IDENTIFIER_REGEX}[./])+'
BRACKETS_WITH_PARAMETERS='\(.*\)'
CLASS_NAME=f'[A-Z]({IDENTIFIER_REGEX})?'
COMPOUND_CLASS_NAME=f'{CLASS_NAME}[_a-z]({CLASS_NAME})+'


METHOD_NAME_WITHOUT_BRACKETS=f'[_a-z]({IDENTIFIER_REGEX})?'
METHOD_NAME_WITH_BRACKETS=f'{METHOD_NAME_WITHOUT_BRACKETS}{BRACKETS_WITH_PARAMETERS}'
METHOD_NAME=f'{METHOD_NAME_WITHOUT_BRACKETS}({BRACKETS_WITH_PARAMETERS})?'
COMPOUND_METHOD_NAME=f'{METHOD_NAME_WITHOUT_BRACKETS}[A-Z]{METHOD_NAME_WITHOUT_BRACKETS}({BRACKETS_WITH_PARAMETERS})?'

METHOD_NAME_HIGH_PROB=re.compile(f'(?<!\w)({METHOD_NAME_WITH_BRACKETS}|{PATH}{METHOD_NAME}|({PATH})?{CLASS_NAME}[#.]{METHOD_NAME}|{COMPOUND_METHOD_NAME})(?!\w)')
CLASS_HIGH_PROB=re.compile(f'(?<!\w)({PATH}{CLASS_NAME}|{COMPOUND_CLASS_NAME})(?!\w)')
EXCEPTION_HIGH_PROB=re.compile(f'(?<!\w){CLASS_NAME}(Error|Exception)(?!\w)')
TEST_CLASS_HIGH_PROB=re.compile(f'(?<!\w){CLASS_NAME}Test(?!\w)')

# TODO file pattern !
# TODO version pattern!   orif semver regex: ^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$

from nltk import PorterStemmer

def safe_tokenize(text: Any) -> Set[str]:
   if text is None:
      return set()
   if pd.isna(text):
      return set()

   tokens = _tokenizer.tokenize(str(text).lower())
   return tokens


_tokenizer = RegexpTokenizer(r"[\s_\.,%#/\?!\-\'\"\)\(\]\[\:;]", gaps=True)


@dataclass(frozen=True)
class CleanedCommitMessage:
   clean_message: str
   bag_of_words: Dict[str, int]
   issue: Optional[str] = None
   url: List[str] = field(default_factory=list)

   def __str__(self):
      return self.clean_message + " " + str(self.bag_of_words) + f" [{self.issue}, {self.url}]"

   def __repr__(self):
      return str(self)


def extract_url(s: str) -> (str, Optional[str]):
   """
   >>> extract_url('implement feature #1 https://svn.apache.org/repos/asf/lucene/java/trunk@888780 (wip)')
   ('implement feature #1 (wip)', ['https://svn.apache.org/repos/asf/lucene/java/trunk@888780'])
   >>> extract_url('https://github.com and https://github.org')
   ('and ', ['https://github.org', 'https://github.com'])
   """
   reg = re.compile(URL_REGEX)
   matcher = reg.search(s)
   urls = []
   if matcher:
      st, urls = extract_url(s[matcher.end():])
      urls.append(matcher.group(1))
      s = s[:matcher.start()] + st
   return s, urls


BUGTRACKER1 = 'https://issues.apache.org/bugzilla'
BUGTRACKER2 = 'http://bugzilla.mozilla.org'


PROJECT_SPECIFIC_ISSUE_REGEXES = [
   re.compile(f'Fix(ing|ed)? (?P<issue>({BUGTRACKER1}|{BUGTRACKER2})/show_bug.cgi\?id=\d+)', flags=re.IGNORECASE),
   re.compile(f'(port (of )?)?(fix(ing|ed)? )?(for )?(bug |((jira )?issue ))?#?(?P<issue>[\[\(]?{ISSUE_REGEX}[\]\)]?)(:?)(\s*)', flags=re.IGNORECASE),
]

TEST_CASE_ISSUE_1 = '''Fix https://issues.apache.org/bugzilla/show_bug.cgi?id=47997
Process changes to the naming resources for all JNDI contexts, not just the global one.
Patch by Michael Allman

git-svn-id: https://svn.apache.org/repos/asf/tomcat/trunk@883134 13f79535-47bb-0310-9956-ffa450edef68'''

TEST_CASE_ISSUE_2 = '''Fix for Bug 415508 Ð PolicySecurityController bug: it creates lots of SecureCallerImpl instances!'''

TEST_CASE_ISSUE_3 = '''fixed jira issue JCR-19: package org.apache.xml.utils does not exist (JDK 1.5.0) 

git-svn-id: https://svn.apache.org/repos/asf/incubator/jackrabbit/trunk@76005 13f79535-47bb-0310-9956-ffa450edef68'''


def extract_issue(s: str) -> (str, str):
   """
   >>> extract_issue('fix without issue reference')
   ('fix without issue reference', None)
   >>> extract_issue('PRJ-700: fix')
   ('fix', 'PRJ-700')
   >>> extract_issue('Fix bug #345: fix')
   ('fix', '345')
   >>> extract_issue(TEST_CASE_ISSUE_1)
   ('\\nProcess changes to the naming resources for all JNDI contexts, not just the global one.\\nPatch by Michael Allman\\n\\ngit-svn-id: https://svn.apache.org/repos/asf/tomcat/trunk@883134 13f79535-47bb-0310-9956-ffa450edef68', 'https://issues.apache.org/bugzilla/show_bug.cgi?id=47997')
   >>> extract_issue(TEST_CASE_ISSUE_2)
   ('Ð PolicySecurityController bug: it creates lots of SecureCallerImpl instances!', '415508')
   >>> extract_issue(TEST_CASE_ISSUE_3)
   ('package org.apache.xml.utils does not exist (JDK 1.5.0) \\n\\ngit-svn-id: https://svn.apache.org/repos/asf/incubator/jackrabbit/trunk@76005 13f79535-47bb-0310-9956-ffa450edef68', 'JCR-19')

   """
   for reg in PROJECT_SPECIFIC_ISSUE_REGEXES:
      matcher = reg.search(s)
      if matcher:
         return s[:matcher.start()] + s[matcher.end():], matcher.group('issue')

   return s, None


TEST_MESSAGE = "LUCENE-3820: Wrong trailing index calculation in PatternReplaceCharFilter.\n\ngit-svn-id: https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141 13f79535-47bb-0310-9956-ffa450edef68"

PROJECT_SPECIFIC_CLEANUP_REGEXES = {
   "lucene_solr": [re.compile(r'git-svn-id: '), re.compile('[0-9a-f]{8}\-[0-9a-f]{4}\-[0-9a-f]{4}\-[0-9a-f]{4}\-[0-9a-f]{12}')],
   "tomcat": [re.compile('Patch (provided )?by [^\n]*')]
}



def clean_up_garbage(s: str) -> str:
   """
   >>> clean_up_garbage('1     2 \\n\\n\\n 3 git-svn-id: https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141 13f79535-47bb-0310-9956-ffa450edef68')
   '1 2 3 https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141 '
   >>> clean_up_garbage('title \\n Patch provided by James Cook \\n details')
   'title details'
   """
   for regexes in PROJECT_SPECIFIC_CLEANUP_REGEXES.values():
      for regex in regexes:
         s = regex.sub('', s)
   s = re.compile('\s+').sub(' ', s)
   return s

t = "- Added Unicode range to fix tokenization of Korean - http://issues.apache.org/jira/browse/LUCENE-444\n\ngit-svn-id: https://svn.apache.org/repos/asf/lucene/java/trunk@294982 13f79535-47bb-0310-9956-ffa450edef68"


def replace_identifiers(s: str) -> str:
   """
   >>> replace_identifiers('add CommitExplorer#verify() method')
   'add METHOD method'
   >>> replace_identifiers('close() method')
   'METHOD method'
   >>> replace_identifiers('Class#close() method')
   'METHOD method'
   >>> replace_identifiers('Class#close(int a) method')
   'METHOD method'
   >>> replace_identifiers('Class#close method')
   'METHOD method'
   >>> replace_identifiers('Close class')
   'Close class'
   >>> replace_identifiers('java.Close class')
   'CLASS class'
   >>> replace_identifiers('java.dot.Close class')
   'CLASS class'
   >>> replace_identifiers('CloseClass class')
   'CLASS class'
   >>> replace_identifiers('CloseTest class')
   'TESTCLASS class'
   >>> replace_identifiers('CloseException class')
   'EXCEPTION class'
   >>> replace_identifiers('CloseTestClass class')
   'CLASS class'
   >>> replace_identifiers('fix JCR')
   'fix JCR'
   >>> replace_identifiers('fix isCurrent')
   'fix METHOD'
   >>> replace_identifiers('enable FieldCache.Parser')
   'enable CLASS'
   """
   s = TEST_CLASS_HIGH_PROB.sub('TESTCLASS', s)
   s = EXCEPTION_HIGH_PROB.sub('EXCEPTION', s)
   s = METHOD_NAME_HIGH_PROB.sub('METHOD', s)
   s = CLASS_HIGH_PROB.sub('CLASS', s)
   return s


TEST_CASE1 = '''fix FieldCache holding hard ref to readers: LUCENE-754

git-svn-id: https://svn.apache.org/repos/asf/lucene/java/trunk@488908 13f79535-47bb-0310-9956-ffa450edef68'''


def clean_message(s: str) -> CleanedCommitMessage:
   """
   >>> m = clean_message("fix some issues with code")
   >>> m # doctest: +ELLIPSIS
   fix some issues with code {...} [None, []]
   >>> sorted(m.bag_of_words.items())
   [('code', 1), ('fix', 1), ('issues', 1)]
   >>> m = clean_message(TEST_CASE1)
   >>> m # doctest: +ELLIPSIS
   fix CLASS holding hard ref to readers:  {...} [LUCENE-754, ['https://svn.apache.org/repos/asf/lucene/java/trunk@488908']]
   >>> sorted(m.bag_of_words.items())
   [('class', 1), ('fix', 1), ('hard', 1), ('holding', 1), ('readers', 1), ('ref', 1)]

   """
   s = s.rstrip("\n")
   s, issue = extract_issue(s)
   s = clean_up_garbage(s)
   s, url = extract_url(s)
   s = replace_identifiers(s)

   bag_of_words = Counter({t for t in safe_tokenize(s) if t not in stop_words})
   return CleanedCommitMessage(clean_message=s, bag_of_words=dict(bag_of_words), issue=issue, url=url)


class CommitMessageCleaner(Tool):
   def run_on_commit(self, commit: pydriller.Commit):
      cleaned_commit = clean_message(commit.msg)
      return cleaned_commit
