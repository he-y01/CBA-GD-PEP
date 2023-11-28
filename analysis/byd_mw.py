####  IMPORTS ################################
from logging import Logger
import re

from spacy.matcher import Matcher
from spacy.tokens import Doc
from spacy import Language
from spacy.lang.char_classes import ALPHA, ALPHA_LOWER, ALPHA_UPPER, CONCAT_QUOTES, LIST_ELLIPSES, LIST_ICONS, HYPHENS
from spacy.util import compile_infix_regex

from analysis.helper import Statistics


#### PATTERNS ################################
# 1) binary: writing forms that include both female and male people but differ from the written out pair form.
# 2) gender-inclusive: writing forms that (aim to) include not only female and male people but also persons of other gender identities.
# 3) neopronouns: pronouns that are gender inclusive; these are not part of the official German language.
# 4) different gender conceptions: words referring to non-heteronormative gender conceptions, specifically transgender, intersex and non-binary/genderqueer

PATTERNS = {
    'binary': [{'TEXT': {'REGEX': r'[A-Z]\S*((Innen|In|eR)|/-?(in|innen|r)|\((in|innen|r)\))\b'}}],
    'gender_incl': [{'TEXT': {'REGEX': r'[A-Z]\S*(\*|_|:)(innen|in|r)\b'}}],
    'neopronouns': [{'LOWER': {'REGEX': r'^((hän|hen|ham)|(they|them)|(dey|demm)|(sie?(\*|_|:)?er)|xier)$'}}],
    'different_gender_conceptions': [{'LOWER': {'REGEX': r'((trans\*?-?(\*|gender|geschlechtlich(keit)?|ident|sexuell|sexualität|(-| )?mann|(-| )?frau|(-| )?person)|\btrans\b)|(inter-?(\*|geschlechtlich(keit)?|sex|sexuell|sexualität)|\binter\b)|(nicht-?binär|non-?binary|enby|gender-?fluid|poly-?gender)|(hetero-?normativität|hetero-?normativ|lgbtq?i?a?(2s)?\+?|lsbtt?i?a?q?\+|(gender.?)?queer))'}}], 
}


def match(file_name:str, matchers:dict[str,Matcher], doc:Doc, logger:Logger, statistics:Statistics):
    """
    Runs ``spacy.matcher.Matcher`s` provided in ``matchers`` to check for occurrences in ``doc``, counts occurences and saves occurrences including where they occured ``file_name``.

    Args:
        file_name (str): Name of file where the text content (``doc``) is from.
        matchers (dict[str,Matcher]): Dictionary of named regular expressions in the form of ``{patternname: (casesensitive, regex)}``.
        doc (Doc): Textual content to find matches in.
        logger (Logger): Instance of used ``Logger``.
        statistics (Statistics): Data object to directly save occurences to.
    """
    for name, matcher in matchers.items():
        matches = matcher(doc)
        
        for _, start, end in matches:
            span = doc[start:end].text + ' {' + file_name[:-5] + '}'
            if not name in statistics.byd_mw.match_lists.keys(): statistics.byd_mw.match_lists[name] = {}
            statistics.byd_mw.match_lists[name][span] = statistics.byd_mw.match_lists[name].get(span, 0) + 1
            statistics.byd_mw.num_matches[name] += 1
            
            logger.info(f"FOUND byd_mw: {span}")


def setup(nlp:Language, logger:Logger, patterns:dict[list[dict]]=None, adj_infixs=True) -> dict[str,Matcher]:
    """
    Helps with setting up ``spacy.matcher.Matcher``s to check for occurrences specified by ``patterns``.

    Args:
        nlp (Language): ``spacy.Language`` to adjust infixes for.
        logger (Logger): `Logger`` to use for logging.
        patterns (dict[list[dict]], optional): Patterns for which to create ``spacy.matcher.Matcher``s. Defaults to None.

    Returns:
        dict[str,Matcher]: Dictionary of named and setup ``spacy.matcher.Matcher``s.
    """
    if adj_infixs:
        infixes = (
            LIST_ELLIPSES
            + LIST_ICONS
            + [
                r"(?<=[0-9])[+\\-\\*^](?=[0-9-])",
                r"(?<=[{al}{q}])\\.(?=[{au}{q}])".format(
                    al=ALPHA_LOWER, au=ALPHA_UPPER, q=CONCAT_QUOTES
                ),
                r"(?<=[{a}]),(?=[{a}])".format(a=ALPHA),
                r"(?<=[{a}])(?:{h})(?=[{a}])".format(a=ALPHA, h=HYPHENS),
                # Account for symbols in gender writing forms (do not split them):
                # r"(?<=[{a}0-9])[:<>=/](?=[{a}])".format(a=ALPHA), # OLD
                r"(?<=[{a}0-9])[<>=](?=[{a}])".format(a=ALPHA),
                r"(?<=[{a}0-9])([:/]\s)(?=[{a}])".format(a=ALPHA),
            ]
        )

        infix_re = compile_infix_regex(infixes)
        nlp.tokenizer.infix_finditer = infix_re.finditer

    if not patterns: patterns = PATTERNS
    matchers = {}
    for name, pattern in patterns.items():
        try:
            matcher = Matcher(nlp.vocab)
            matcher.add(name, [pattern])
            matchers[name] = matcher
        except Exception as e:
            logger.warning(f"Matcher '{name}': {e}")
    return matchers
