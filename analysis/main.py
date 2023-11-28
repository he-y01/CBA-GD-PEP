#### IMPORTS #################################
import sys
import os
import re
import csv
from datetime import datetime, timezone
from typing import Callable
import logging
import logging.config

import spacy
from spacy.language import Language
from spacy.tokens import Doc
from spacy.matcher import Matcher

import coreferee

from analysis.helper import *
import analysis.fa_per as fa_per
import analysis.fa_prn as fa_prn
import analysis.byd_mw as byd_mw


#### CONSTANTS ###############################
PER_GENDER_MAPPING = {'PER:M':'PER:männlich', 'PER:F':'PER:weiblich'}

# input
DATA_DIR = 'data/articles/'
DEBUG_FILE_PATHS = [
    'f9aa0682-8152-36f1-aad8-f2e3613bcff7.json',
    'b9198689-c7a9-3add-b3d6-45029bfc8ed0.json',
    'c16cb0eb-0353-360b-bf50-cc498d674d55.json',
    '3c4d0e51-2d1c-3248-a681-5a3e3ed82588.json',
    '3a456899-60e1-3362-a7bb-5c5ca004c339.json',
    '47e98999-c61e-37c9-b4f7-f7e396a29030.json',
    '191f6142-c7dd-39c5-a12f-ec0f798d980b.json',
    'd6f09831-4612-3188-8e42-c3424caeb46f.json',    # Medienkompetenz in einer digitalen Welt
    #'0a94fdfc-fbda-309b-bd0b-33c8dcf6232b.json',    # Jüdisches Leben in der DDR
    #'ffe363d5-7bc0-3e85-9214-375ac175d50d.json'     # Sicherheit in einer Welt im Umbruch
]

# output
LOG_PATH = 'analysis/logs/'
STATS_PATH = 'analysis/stats/'
VERSION_EXT = '-X1'


#### LOGGING #################################
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': { 
        'standard': {
            'format': '{asctime} {levelname:<8} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d - %H:%M:%S' }
    },
    'handlers': {
        'console':  {'class': 'logging.StreamHandler', 
                     'formatter': "standard", 
                     'level': 'DEBUG', 
                     'stream': sys.stdout},
        'file':     {'class': 'logging.FileHandler', 
                     'formatter': "standard", 
                     'level': 'INFO', 
                     'filename': f"{LOG_PATH}izpb-analyzer_{int(datetime.now(timezone.utc).timestamp())}.log",
                     'mode': 'w',
                     'encoding': 'UTF-8'} 
    },
    'loggers': { 
        __name__:   {'level': 'INFO', 
                     'handlers': ['console', 'file'], 
                     'propagate': False}
    }
}

if not os.path.isdir(LOG_PATH):
    os.makedirs(LOG_PATH)

logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger(__name__)

log.info('IMPORT glean norm values')
import analysis.descr_pars as descr_pars


#### FUNC DEFINITIONS ########################
def resolve_coref(doc:Doc) -> Doc:
    """
    Resolves (i.e., replaces) coreferences in ``doc`` with the tokens they refer to.

    Args:
        doc (Doc): Pre-processed ``spacy.Doc``.

    Returns:
        Doc: Coreference-resolved ``Doc``.
    """
    resolved_text = ''
    for token in doc:
        repres = doc._.coref_chains.resolve(token)
        if repres:
            resolved_text += ' ' + ' und '.join([t.text for t in repres])
        else:
            resolved_text += ' ' + token.text
    return resolved_text


def setup_spacy_pipeline() -> Language:
    """
    Setup ``spacy.Language`` instance.

    Returns:
        Language: Return setup ``spacy.Language`` instance.
    """
    #sent_config = {'punct_chars': ['.', '?', '!', ';']}
    nlp = spacy.load('de_core_news_lg')

    nlp.add_pipe('merge_entities', after='ner')
    nlp.add_pipe('coreferee', after='merge_entities')
    nlp.add_pipe('gender_ner', after='coreferee')
    nlp.add_pipe('gender_prn', after='gender_ner')
    return nlp


def preprocess(input_str:str, statistics:Statistics) -> str:
    """
    Removes or corrects artefacts that can throw of various pipes (e.g., NER, POS-tagging) of the analysis.

    Args:
        input_str (str): String that shall be preprocessed.
        statistics (Statistics): Data object to count how often a slash and the following word were removed.

    Returns:
        str: Preprocessed string.
    """
    preprocessed_par = re.sub(r'[–]+', '-', input_str)
    preprocessed_par = re.sub(r'\n+', '', preprocessed_par)
    statistics.num_slashes += len(re.findall(r'/ ?[A-z]+', preprocessed_par))
    preprocessed_par = re.sub(r' ?/ ?((?!i)|(?!-i))[A-z]+', '', preprocessed_par)
    return preprocessed_par


def log_results(statistics:Statistics, logger:Callable=log.debug):
    """
    Logs some results from the analysis (saved in ```statistics``).

    Args:
        statistics (Statistics): Data object in which the result from the analysis are saved.
        logger (Callable, optional): Instance of used ``Logger``. Defaults to log.debug.
    """
    logger('')
    logger('Results')

    logger('\t%s', statistics.descr.num_matches_descr)
    logger('\t%s', [v/statistics.descr.num_matches_descr['DESCR:F'] if statistics.descr.num_matches_descr['DESCR:F'] > 0 else 0 for v in statistics.glean.female_glean])
    logger('\t%s', [v/statistics.descr.num_matches_descr['DESCR:M'] if statistics.descr.num_matches_descr['DESCR:M'] > 0 else 0 for v in statistics.glean.male_glean])
    logger('\t%s', [v/statistics.descr.num_matches_descr['DESCR:NA'] if statistics.descr.num_matches_descr['DESCR:NA'] > 0 else 0 for v in statistics.glean.ud_glean])

    logger('\t%s', statistics.per.num_matches_per)
    logger('\t%s', statistics.prn.num_matches_prn)


def save_results(statistics:Statistics, stats_list:list[list[int]]):
    """
    Saves all occurrences and counts to files.

    Args:
        statistics (Statistics): Occurrences and counts collected for the corpus as a whole.
        stats_list (list[list[int]]): Occurences and counts collected for each article individually.
    """
    log.info('='*150)
    log.info('SAVING statistics')

    if not os.path.isdir(STATS_PATH):
        os.makedirs(STATS_PATH)

    write_occurences_to_file(f"{STATS_PATH}per_female{VERSION_EXT}.csv", statistics.per.female_per)
    write_occurences_to_file(f"{STATS_PATH}per_male{VERSION_EXT}.csv", statistics.per.male_per)
    write_occurences_to_file(f"{STATS_PATH}per_amb{VERSION_EXT}.csv", statistics.per.amb_per)
    write_occurences_to_file(f"{STATS_PATH}per_nh{VERSION_EXT}.csv", statistics.per.nh_per)
    write_occurences_to_file(f"{STATS_PATH}per_ud{VERSION_EXT}.csv", statistics.per.ud_per)

    write_occurences_to_file(f"{STATS_PATH}prn_female{VERSION_EXT}.csv", statistics.prn.female_prn)
    write_occurences_to_file(f"{STATS_PATH}prn_male{VERSION_EXT}.csv", statistics.prn.male_prn)
    
    write_occurences_to_file(f"{STATS_PATH}descr_female{VERSION_EXT}.csv", statistics.descr.female_descriptors)
    write_occurences_to_file(f"{STATS_PATH}descr_male{VERSION_EXT}.csv", statistics.descr.male_descriptors)
    write_occurences_to_file(f"{STATS_PATH}descr_ud{VERSION_EXT}.csv", statistics.descr.ud_descriptors)

    for n, m in statistics.byd_mw.match_lists.items():
        write_occurences_to_file(f"{STATS_PATH}matches-{n}{VERSION_EXT}.csv", m)

    with open(f"{STATS_PATH}stats_table{VERSION_EXT}.csv", mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        header = ['article', 'token_num', 'num_slashes',
                  'num_PER_F', 'num_PER_M', 'num_PER_NA', 'num_PER_AMB',
                  'num_PRN_F', 'num_PRN_M',
                  'num_DESCR_F', 'num_DESCR_M', 'num_DESCR_NA', 'num_NEG',
                  'F_AROU', 'F_VAL', 'F_IMA', 'F_CONC',
                  'M_AROU', 'M_VAL', 'M_IMA', 'M_CONC',
                  'UD_AROU', 'UD_VAL', 'UD_IMA', 'UD_CONC',
                  'num_noGLEAN_F', 'num_noGLEAN_M', 'num_noGLEAN_NA']
        header.extend(list(k for k in statistics.byd_mw.num_matches.keys()))
        writer.writerow(header)
        writer.writerows(stats_list)


#### RUN ANALYSIS ############################
def analyze(nlp:Language, file_name:str, article_content:list[str], statistics:Statistics, matchers:dict[str,Matcher]=None):
    """
    Runs analysis of a single article (paragraph by paragraph).

    Args:
        nlp (Language): Already setup spaCy NLP ``Language`` object.
        file_name (str): Name of the file of the article to be analyzed.
        article_content (list[str]): Text content of the article to be analyzed
        statistics (Statistics): Data object to directly save occurrences and counts to.
        matchers (dict[str,Matcher], optional): Dictionary of named ``spacy.matcher.Matcher``s that shall be used analysis as well. Defaults to None.
    """
    for par in article_content:
        pre_anno_par = nlp(preprocess(par, statistics))
        resolved_par = resolve_coref(pre_anno_par)
        anno_par = nlp(resolved_par)
        statistics.token_num += len(anno_par)

        if matchers: byd_mw.match(file_name, matchers, anno_par, log, statistics)

        fa_per.count_per(anno_par, statistics, log)
        fa_prn.count_prn(anno_par, statistics, log)
        descr_pars.parse_descriptors(anno_par, statistics, log)

def main():
    log.info('SETUP spaCy Pipeline')
    nlp = setup_spacy_pipeline()
    log.info('+  setup prn pipe')
    fa_prn.setup('analysis/prn_list_v21_adjusted.csv', log)
    log.info('+  setup per pipe')
    fa_per.setup(log)
    log.info('SETUP byd_mw pipe')
    matchers = byd_mw.setup(nlp, log)

    log.info(f"START ANALYSIS ({VERSION_EXT})")
    prev_stats = Statistics(Statistics.PER({}, {}, {}, {}, {}),
                            Statistics.PRN({}, {}), 
                            Statistics.DESCR({}, {}, {}), 
                            Statistics.GLEAN(),
                            Statistics.BYD_MW({}, {name:0 for name in matchers.keys()}))

    articles = os.listdir(DATA_DIR)
    if log.level == logging.DEBUG:
        if DEBUG_FILE_PATHS:
            articles = DEBUG_FILE_PATHS
        else:
            articles = articles[:50]

    stats_list = []
    num_articles = len(articles)
    for n, file_name in enumerate(articles):
        log.info('='*150)
        log.info(f"Loading...    Article No:{n+1:>4} / {num_articles}       {file_name}")

        if raw_text := load_text(f"{DATA_DIR}{file_name}"):
            statistics = Statistics(Statistics.PER(prev_stats.per.female_per, prev_stats.per.male_per, prev_stats.per.amb_per, prev_stats.per.nh_per, prev_stats.per.ud_per), 
                                    Statistics.PRN(prev_stats.prn.female_prn, prev_stats.prn.male_prn), 
                                    Statistics.DESCR(prev_stats.descr.female_descriptors, prev_stats.descr.male_descriptors, prev_stats.descr.ud_descriptors), 
                                    Statistics.GLEAN(),
                                    Statistics.BYD_MW(prev_stats.byd_mw.match_lists, {name:0 for name in matchers.keys()}))
            analyze(nlp, file_name, raw_text, statistics, matchers)
            info = [
                file_name[:-5], statistics.token_num, statistics.num_slashes,
                statistics.per.num_matches_per[PER_GENDER_MAPPING['PER:F']], statistics.per.num_matches_per[PER_GENDER_MAPPING['PER:M']], statistics.per.num_matches_per['PER:NA'], statistics.per.num_matches_per['PER:AMB'],
                statistics.prn.num_matches_prn['PRN:F'], statistics.prn.num_matches_prn['PRN:M'],
                statistics.descr.num_matches_descr['DESCR:F'], statistics.descr.num_matches_descr['DESCR:M'], statistics.descr.num_matches_descr['DESCR:NA'], statistics.descr.num_neg, #sum(statistics.descr.female_descriptors.values())-sum(prev_stats.descr.female_descriptors.values()), sum(statistics.descr.male_descriptors.values()), sum(statistics.descr.ud_descriptors.values()), statistics.descr.num_neg,
                statistics.glean.female_glean[0], statistics.glean.female_glean[1], statistics.glean.female_glean[2], statistics.glean.female_glean[3],
                statistics.glean.male_glean[0], statistics.glean.male_glean[1], statistics.glean.male_glean[2],  statistics.glean.male_glean[3],       
                statistics.glean.ud_glean[0], statistics.glean.ud_glean[1], statistics.glean.ud_glean[2], statistics.glean.ud_glean[3],
                statistics.glean.glean_not_found['DESCR:F'], statistics.glean.glean_not_found['DESCR:M'], statistics.glean.glean_not_found['DESCR:NA']                   
            ]
            info.extend((v for v in statistics.byd_mw.num_matches.values()))
            stats_list.append(info)
            prev_stats = statistics
        else:
            log.info(f"SKIPPED bibliography|imprint")
        
        log_results(prev_stats)

    save_results(prev_stats, stats_list)


if __name__ == '__main__':
    main()
