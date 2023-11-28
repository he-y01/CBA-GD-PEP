#### IMPORTS #################################
from logging import Logger
import pandas as pd

from spacy.language import Language
from spacy.tokens import Doc, Token

from analysis.helper import Statistics, PRN_LIST_INDICATOR_FEMALE, PRN_LIST_INDICATOR_MALE


#### FUNC DEFINITIONS ########################
def count_prn(doc:Doc, statistics:Statistics=None, logger:Logger=None) -> dict[str,int]:
    """
    Count female and male people-related nouns (PRNs) based on custom annotations in ``doc``. 
    If ``statistics`` is provided -- creates lists for of the female and male PRNs.

    Args:
        doc (Doc): ``spacy.tokens.Doc`` for which PRNs shall be counted.
        statistics (Statistics, optional): ``Statistics`` to directly save counts. Defaults to None.
        logger (Logger, optional): ``Logger`` to use for logging; no logging if not provided. Defaults to None.

    Returns:
        dict[str,int]: ``dict`` with counts of female and male PRNs.
    """
    if statistics:
        for token in doc:
            if g := token._.gender:
                #if logger: logger.debug(f"\t{token.text:-<30}{token.lemma_:-<30}{g:->8}")
                for label, value in statistics.prn.num_matches_prn.items():
                    if g == label:
                        statistics.prn.num_matches_prn[label] = value + 1
                statistics.prn.female_prn[token.lemma_] = statistics.prn.female_prn.get(token.lemma_, 0) + (g == 'PRN:F')
                statistics.prn.male_prn[token.lemma_] = statistics.prn.male_prn.get(token.lemma_, 0) + (g == 'PRN:M')
        return {'PRN:F':statistics.prn.num_matches_prn['PRN:F'], 'PRN:M':statistics.prn.num_matches_prn['PRN:M']}
    else:
        num_matches_prn = {'PRN:F':0, 'PRN:M':0}
        for token in doc:
            if g := token._.gender:
                if logger: logger.debug(f"\t{token.text:-<30}{token.lemma_:-<30}{g:->8}")
                for label in num_matches_prn.keys():
                    num_matches_prn[label] += (g == label)
        return num_matches_prn 


@Language.component('gender_prn')
def gender_prn(doc:Doc) -> Doc:
    """
    ``spacy`` pipeline component for annotating people-related nound (PRNs) with a custom ```Token`` label "gender" (only female or male marker) according to ``Doc`` extensions ``prn_female`` and ``prn_male``.

    Args:
        doc (Doc): ``Doc`` object forwarded by previous component.

    Returns:
        Doc: PRN-annotated ``Doc`` object.
    """
    for token in doc:
        if token.pos_ != 'NOUN' and token.pos_ != 'PROPN': continue

        if token.lemma_ in doc._.prn_male:
            token._.gender = 'PRN:M'
        elif token.lemma_ in doc._.prn_female:
            token._.gender = 'PRN:F'

    return doc


def setup(path_prn_list:str, logger:Logger) -> None:
    """
    Helps with setting up the prn-annotating ``spacy`` pipeline component 'gender_prn'.
    Initializes the ``Doc`` extensions ``prn_female`` and ``prn_male`` used by 'gender_prn'.

    Args:
        path_prn_list (str): Path to comma separated PRN list with 'w' and 'm' as gender specifiers.
        logger (Logger): `Logger`` to use for logging.
    """
    prn_male = []
    prn_female = []

    # read in pre-compiled list of people-related nouns
    with open(path_prn_list, mode='r', encoding='utf-8') as file:
        reader = pd.read_csv(file, comment='#').to_numpy()
        for row in reader:
            if row[0] == PRN_LIST_INDICATOR_FEMALE:
                prn_female.append(row[1])
            elif row[0] == PRN_LIST_INDICATOR_MALE:
                prn_male.append(row[1])
            else:
                logger.warning(f"unknown gender specifier in prn-list: {row[0]} for word {row[1]}")
    
    Doc.set_extension('prn_female', default=prn_female)
    Doc.set_extension('prn_male', default=prn_male)
    Token.set_extension('gender', default=None)