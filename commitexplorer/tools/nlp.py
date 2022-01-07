import re
from abc import abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import spacy
from spacy.tokens import Token

from commitexplorer.tools.messagecleaner import clean_message

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


@dataclass(frozen=True)
class NounVerbSentence(ParsedCommitMessageSentence):
    subject: str
    verb: str
    aux: Optional[str] = None

    def get_core(self) -> str:
        return f'{self.subject} ({self.aux}) {self.verb}'

    @classmethod
    def from_tokens(cls, subject: Token, verb: Token, aux: Optional[Token] = None) -> 'NounVerbSentence':
        return cls(get_lemma(subject), get_lemma(verb), get_lemma(aux))


@dataclass(frozen=True)
class NounPhrase(ParsedCommitMessageSentence):
    noun: str
    mod: Optional[str]

    @classmethod
    def from_tokens(cls, noun: Token, mod: Optional[Token]) -> 'NounPhrase':
        return cls(get_lemma(noun), get_lemma(mod))

    def get_core(self) -> str:
        return f'{self.noun} ({self.mod})'


@dataclass(frozen=True)
class VerbPhrase(ParsedCommitMessageSentence):
    verb: str
    object: str

    @classmethod
    def from_tokens(cls, verb: Token, object: Token) -> 'VerbPhrase':
        return cls(get_lemma(verb), get_lemma(object))

    def get_core(self) -> str:
        return f'{self.verb} {self.object}'


@dataclass(frozen=True)
class GenericVerbPhrase(ParsedCommitMessageSentence):
    verb: str
    other: str

    @classmethod
    def from_tokens(cls, verb: Token, other: Token) -> 'GenericVerbPhrase':
        return cls(get_lemma(verb), get_lemma(other))

    def get_core(self) -> str:
        return f'{self.verb} + {self.other}'


@dataclass(frozen=True)
class ParsedCommitMessage:
    sentences: List[ParsedCommitMessageSentence]
    clean_message: str
    bag_of_words: Dict[str, int]
    issue: Optional[str] = None
    url: List[str] = field(default_factory=list)

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
    s = clean_message(s)

    doc = model(s)
    sentences = [parse_sentence(sentence) for sentence in doc.sents]
    bag_of_words = Counter([token.lemma_ for sentence in doc.sents for token in sentence if (token.pos_ != 'PUNCT' and token.is_alpha and not token.is_stop)])
    return ParsedCommitMessage(sentences, clean_message=s, bag_of_words=dict(bag_of_words), issue=issue, url=url)

# TODO should+must doesn't not, differentiate between exception class and method, bag of words
