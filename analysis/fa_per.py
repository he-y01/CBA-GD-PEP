#### IMPORTS #################################
import sys
import time
from logging import Logger
from urllib.error import HTTPError
import pandas as pd

from spacy.language import Language
from spacy.tokens import Doc, Span

from SPARQLWrapper import SPARQLWrapper, JSON#
from SPARQLWrapper.SPARQLExceptions import EndPointInternalError

from analysis.helper import Statistics


# Wikdiata endpoint URL for querying the gender of well-known people
ENDPOINT_URL = 'https://query.wikidata.org/sparql'


#### FUNC DEFINITIONS ########################
def count_per(doc:Doc, statistics:Statistics, logger:Logger) -> None:
    """
    Counts gender of recognized people (male, female, and -- if present -- other) based on (customized) NER-annotations in ``doc``. 
    If ``statistics`` is provided -- creates lists of people's names for female, male and other.

    Args:
        doc (Doc): ``spacy.tokens.Doc`` for which people's gender shall be counted.
        statistics (Statistics): ``Statistics`` to directly save counts.
        logger (Logger): ``Logger`` to use for logging.
    """
    for ent in doc.ents:
        if not ent.label_.startswith('PER:'): continue
        #logger.debug(f"\t{ent.text:-<60}{ent.label_:->8}")
        for label, value in statistics.per.num_matches_per.items():
            if ent.label_ == label:
                statistics.per.num_matches_per[label] = value + 1
        statistics.per.female_per[ent.text] = statistics.per.female_per.get(ent.text, 0) + (ent.label_ == 'PER:weiblich')
        statistics.per.male_per[ent.text] = statistics.per.male_per.get(ent.text, 0) + (ent.label_ == 'PER:männlich')
        statistics.per.amb_per[ent.text] = statistics.per.amb_per.get(ent.text, 0) + (ent.label_ == 'PER:AMB')
        statistics.per.nh_per[ent.text + ' {' + ent.label_ + '}'] = statistics.per.nh_per.get(ent.text + ' {' + ent.label_ + '}', 0) + (ent.label_ not in {'PER:weiblich', 'PER:männlich', 'PER:NA', 'PER:AMB'})
        statistics.per.ud_per[ent.text] = statistics.per.ud_per.get(ent.text, 0) + (ent.label_ == 'PER:NA')

        if (ent.label_ not in {'PER:weiblich', 'PER:männlich', 'PER:NA', 'PER:AMB'}):
            logger.info(f"FOUND non-heteronormative per: {ent.text} --- {ent.label_}")

def get_wikidata_results(endpoint_url:str, query:str) -> pd.DataFrame:
    """
    Gets matching entries on Wikidata for specified ``query``.

    Args:
        endpoint_url (str): URL to Wikidata query API.
        query (str): Wikidata SPARQL query.

    Returns:
        pd.DataFrame: Table of matching Wikidata entries with the columns specified in the ``query``.
    """
    user_agent = f"BT-ObtainGender (yhess@uni-osnabrueck.de) Python/{sys.version_info[0]}.{sys.version_info[1]}"
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.addExtraURITag
    result = sparql.query().convert()
    return pd.json_normalize(result['results']['bindings'])


def gender_unambiguous(s:pd.Series) -> bool:
    """
    Returns if the gender values listed in ``s`` are all equal, i.e., unambiguous.

    Args:
        s (pd.Series): A series of gender values.

    Returns:
        bool: ``True`` if listed values are all equal.
    """
    a = s.to_numpy()
    return (a[0] == a).all()


def obtain_gender(name_str:str, logger:Logger=None) -> str:
    """
    Forms Wikidata queries to obtain gender based on ``name_str``.

    Args:
        name_str (str): Name of person for whom gender information shall be obtained.
        logger (Logger, optional): Instance of used ``Logger``. Defaults to None.

    Returns:
        str: Gender information: ``f'PER:{gender}'`` if unambiguous ``'PER:NA'`` otherwise.
    """    
    gender = 'PER:NA'

    name = name_str.split()
    if len(name) > 12: 
        if logger: logger.info(f"\tUNRESOLVED name exceeds maximum length (12): {name_str}")
        return gender
    
    # first order query
    query = f"""
    SELECT ?item ?itemLabel ?gender ?genderLabel
    WHERE {{
        ?item wdt:P31 wd:Q5.
        
        VALUES ?p2 {{ wdt:P734 }}
        VALUES ?surname {{ {' '.join([f'''"{n.replace('"', '')}"@de''' for n in name[1:]] if len(name) > 1 else ['""@de'])}{f''' "{name[-3].replace('"', '') + ' ' if name[-3].islower() else ''}{name[-2].replace('"', '')} {name[-1].replace('"', '')}"@de''' if len(name) > 2 and (name[-2].islower() or name[-3].islower) else ''} }}
        ?item ?p2 ?partial2 .
        ?partial2 rdfs:label|skos:altLabel ?surname .

        VALUES ?p {{ wdt:P735 wdt:P1449 wdt:P742 }}
        VALUES ?name {{ {' '.join([f'''"{n.replace('"', '')}"@de''' for n in name[:-1]] if len(name) > 1 else ['""@de'])} }}
        ?item ?p ?partial .
        ?partial rdfs:label|skos:altLabel ?name .

        ?item wdt:P21 ?gender .
            
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],de". }}
    }}
    LIMIT 100
    """

    wd_results = get_wikidata_results(ENDPOINT_URL, query)

    # second order query
    if wd_results.empty or not gender_unambiguous(wd_results['gender.value']):
        query = f"""
        SELECT ?item ?itemLabel ?prefLabel ?gender ?genderLabel
        WHERE {{
            ?item wdt:P31 wd:Q5.
                
            VALUES ?prefLabel {{"{name_str.replace('"', '')}"@de "{name_str.replace('"', '')}"@en}}
            ?item rdfs:label|skos:altLabel ?prefLabel .
            
            ?item wdt:P21 ?gender .

            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],de". }}
        }}
        LIMIT 100
        """
        wd_results = get_wikidata_results(ENDPOINT_URL, query)
  
    # if unambiguous, create return string
    if (not wd_results.empty) and gender_unambiguous(wd_results['gender.value']):
        gender = 'PER:' + wd_results.iloc[0]['genderLabel.value'] 
    
    # if ambiguous, create 'PER:AMB' as return string
    elif (not wd_results.empty) and (not gender_unambiguous(wd_results['gender.value'])):
        gender = 'PER:AMB'

    # if no result, try without potential possessive s
    elif gender == 'PER:NA' and name_str[-1] == 's':
        gender = obtain_gender(name_str[:-1], logger)

    if logger:
        if gender == 'PER:NA' and wd_results.empty:
            logger.info(f"\tUNRESOLVED named entity not found: {name_str}")
        elif gender == 'PER:NA' and not gender_unambiguous(wd_results['gender.value']):
            logger.info(f"\tUNRESOLVED gender ambiguous: {name_str}")
    
    return gender


@Language.component('gender_ner')
def gender_ner(doc:Doc) -> Doc:
    """
    ``spacy`` pipeline component for annotating named entity PER with their gender based on inference via wikidata information.

    Args:
        doc (Doc): ``Doc`` object forwarded by previous component.

    Returns:
        Doc: Gender NER annotated ``Doc`` object.
    """
    new_ents = []
    for old_ent in doc.ents:
        if old_ent.label_ == 'PER':
            try:
                new_ent = Span(doc, old_ent.start, old_ent.end, obtain_gender(old_ent.text, doc._.logger))
            except (EndPointInternalError, HTTPError):
                time.sleep(60000)
                try:
                    new_ent = Span(doc, old_ent.start, old_ent.end, obtain_gender(old_ent.text, doc._.logger))
                except (EndPointInternalError, HTTPError) as e:
                    doc._.logger.warning(f"SPARQL EndPointInternalError/HTTPError (Timeout): {old_ent} --- {e}")
                    new_ent = Span(doc, old_ent.start, old_ent.end, 'PER:NA')
            new_ents.append(new_ent)
    doc.ents = new_ents
    return doc


def setup(logger:Logger):
    """
    Helps with setting up the gender-ner-annotating ``spacy`` pipeline component 'gender_ner'.
    Initializes the ``Doc`` extension ``logger`` used by 'gender_ner'.

    Args:
        logger (Logger): `Logger`` to use for logging
    """
    Doc.set_extension('logger', default=logger)
