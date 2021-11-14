import re
from abc import abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, List, Dict

import spacy
from spacy.tokens import Token


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

METHOD_NAME_HIGH_PROB=re.compile(f'(?<!\w)({METHOD_NAME_WITH_BRACKETS}|{PATH}{METHOD_NAME}|({PATH})?{CLASS_NAME}[#.]{METHOD_NAME})(?!\w)')
CLASS_HIGH_PROB=re.compile(f'(?<!\w)({COMPOUND_CLASS_NAME}|{PATH}{CLASS_NAME})(?!\w)')
EXCEPTION_HIGH_PROB=re.compile(f'(?<!\w){CLASS_NAME}(Error|Exception)(?!\w)')
TEST_CLASS_HIGH_PROB=re.compile(f'(?<!\w){CLASS_NAME}Test(?!\w)')

nlp = spacy.load("en_core_web_sm")


def verb_looking(s: Token) -> bool:
    if s.lemma_ == "bug":
        return False
    return s.text.endswith("es") or s.text.endswith("ed") or s.pos_ == "VERB"


class ParsedCommitMessageSentence:

    @abstractmethod
    def get_core(self) -> str:
        pass

    def __str__(self):
        return f'({self.get_core()}, {type(self).__name__})'

    def __repr__(self):
        return str(self)


@dataclass
class NounVerbSentence(ParsedCommitMessageSentence):
    subject: str
    verb: str
    aux: Optional[str] = None

    def get_core(self) -> str:
        return f'{self.subject} ({self.aux}) {self.verb}'

    @classmethod
    def from_tokens(cls, subject: Token, verb: Token, aux: Optional[Token] = None) -> 'NounVerbSentence':
        return cls(get_lemma(subject), get_lemma(verb), get_lemma(aux))


@dataclass
class NounPhrase(ParsedCommitMessageSentence):
    noun: str
    mod: Optional[str]

    @classmethod
    def from_tokens(cls, noun: Token, mod: Optional[Token]) -> 'NounPhrase':
        return cls(get_lemma(noun), get_lemma(mod))

    def get_core(self) -> str:
        return f'{self.noun} ({self.mod})'


@dataclass
class VerbPhrase(ParsedCommitMessageSentence):
    verb: str
    object: str

    @classmethod
    def from_tokens(cls, verb: Token, object: Token) -> 'VerbPhrase':
        return cls(get_lemma(verb), get_lemma(object))

    def get_core(self) -> str:
        return f'{self.verb} {self.object}'


@dataclass
class GenericVerbPhrase(ParsedCommitMessageSentence):
    verb: str
    other: str

    @classmethod
    def from_tokens(cls, verb: Token, other: Token) -> 'GenericVerbPhrase':
        return cls(get_lemma(verb), get_lemma(other))

    def get_core(self) -> str:
        return f'{self.verb} + {self.other}'


@dataclass
class ParsedCommitMessage:
    sentences: List[ParsedCommitMessageSentence]
    clean_message: str
    bag_of_words: Dict[str, int]
    issue: Optional[str] = None
    url: [List[str]] = field(default_factory=list)

    def __str__(self):
        return str(self.sentences) + " " + str(self.bag_of_words) + f" [{self.issue}, {self.url}]"

    def __repr__(self):
        return str(self)


def parse_sentence(sentence) -> ParsedCommitMessageSentence:
    root_token = sentence.root
    children_list = [c for c in root_token.children]
    if verb_looking(root_token):
        for child in children_list:
            if child.dep_ in ["dobj", "nummod"]:
                return VerbPhrase.from_tokens(verb=root_token, object=child)
            elif child.dep_ == "nsubj" and not verb_looking(child):
                subject=child
                aux = None
                for child in children_list:
                    if child.dep_ == 'aux':
                        aux = child
                        break
                return NounVerbSentence.from_tokens(subject=subject, verb=root_token, aux=aux)
        return GenericVerbPhrase.from_tokens(
                   verb=root_token,
                   other=children_list[0] if len(children_list) > 0 else None,
               )
    else:
        for child in children_list:
            if (
                    child.dep_ in ["amod", "nsubj", "compound"]
                    and child.text == str(sentence[0])
                    and verb_looking(child)
            ):
                return VerbPhrase.from_tokens(verb=child, object=root_token)
        return NounPhrase.from_tokens(
                   noun=root_token,
                   mod=children_list[0] if len(children_list) > 0 else None,
               )


def get_lemma(token: Token) -> str:
    return token.lemma_.lower() if token is not None else None


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


def extract_issue_at_start(s: str) -> (str, str):
    """
    >>> extract_issue_at_start('fix without issue reference')
    ('fix without issue reference', None)
    >>> extract_issue_at_start('PRJ-700: fix')
    ('fix', 'PRJ-700')
    >>> extract_issue_at_start('Fix bug #345: fix')
    ('fix', '345')
    """
    reg = re.compile(f'(Fix Bug )?#?({ISSUE_REGEX})(:?)(\s*)', flags=re.IGNORECASE)
    matcher = reg.search(s)
    if matcher:
        return s[:matcher.start()] + s[matcher.end():], matcher.group(3)
    else:
        return s, None


TEST_MESSAGE = "LUCENE-3820: Wrong trailing index calculation in PatternReplaceCharFilter.\n\ngit-svn-id: https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141 13f79535-47bb-0310-9956-ffa450edef68"

CLEANUP_REGEXES = [re.compile(r'git-svn-id: '), re.compile('[0-9a-f]{8}\-[0-9a-f]{4}\-[0-9a-f]{4}\-[0-9a-f]{4}\-[0-9a-f]{12}')]


def clean_up_garbage(s: str) -> str:
    """
    >>> clean_up_garbage('1     2 \\n\\n\\n 3 git-svn-id: https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141 13f79535-47bb-0310-9956-ffa450edef68')
    '1 2 3 https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141 '
    """
    for regex in CLEANUP_REGEXES:
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
    """
    s = TEST_CLASS_HIGH_PROB.sub('TESTCLASS', s)
    s = EXCEPTION_HIGH_PROB.sub('EXCEPTION', s)
    s = METHOD_NAME_HIGH_PROB.sub('METHOD', s)
    s = CLASS_HIGH_PROB.sub('CLASS', s)
    return s


def get_commit_cores(s: str, model) -> ParsedCommitMessage:
    """
    >>> get_commit_cores("fix some issues with code", nlp)
    [VerbPhrase(verb='fix', object='issue')] {'fix': 1, 'issue': 1, 'code': 1} [None, []]
    >>> get_commit_cores("fixed tricky bug", nlp)
    [VerbPhrase(verb='fix', object='bug')] {'fix': 1, 'tricky': 1, 'bug': 1} [None, []]
    >>> get_commit_cores("Fixes bug", nlp)
    [VerbPhrase(verb='fix', object='bug')] {'fix': 1, 'bug': 1} [None, []]
    >>> get_commit_cores("bug fix", nlp)
    [NounPhrase(noun='fix', mod='bug')] {'bug': 1, 'fix': 1} [None, []]
    >>> get_commit_cores("improvement", nlp)
    [NounPhrase(noun='improvement', mod=None)] {'improvement': 1} [None, []]
    >>> get_commit_cores(TEST_MESSAGE, nlp)
    [NounPhrase(noun='calculation', mod='trail')] {'wrong': 1, 'trail': 1, 'index': 1, 'calculation': 1, 'CLASS': 1} [LUCENE-3820, ['https://svn.apache.org/repos/asf/lucene/dev/trunk@1294141']]
    >>> get_commit_cores(t, nlp)
    [NounPhrase(noun='range', mod='unicode')] {'add': 1, 'Unicode': 1, 'range': 1, 'fix': 1, 'tokenization': 1, 'Korean': 1} [LUCENE-444, ['http://issues.apache.org/jira/browse/https://svn.apache.org/repos/asf/lucene/java/trunk@294982']]

    """
    s = s.rstrip("\n")
    s, issue = extract_issue_at_start(s)
    s = clean_up_garbage(s)
    s, url = extract_url(s)
    s = replace_identifiers(s)

    doc = model(s)
    sentences = [parse_sentence(sentence) for sentence in doc.sents]
    bag_of_words = Counter([token.lemma_ for sentence in doc.sents for token in sentence if (token.pos_ != 'PUNCT' and token.is_alpha and not token.is_stop)])
    return ParsedCommitMessage(sentences, clean_message=s, bag_of_words=dict(bag_of_words), issue=issue, url=url)

# TODO should+must doesn't not, differentiate between exception class and method, bag of words
