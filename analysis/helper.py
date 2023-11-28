#### IMPORTS #################################
import re
import csv
import json

from dataclasses import dataclass, field
from collections.abc import Iterator


#### HELPER CONSTANTS ########################
PRN_LIST_INDICATOR_FEMALE = 'f'
PRN_LIST_INDICATOR_MALE = 'm'


#### STATISTICS DATA CLASS ###################
GLEAN_INIT = [0.0, 0.0, 0.0, 0.0]

@dataclass
class Statistics:
    """
    Helper class to structure collected data during analysis of the articles.
    """
    per:'PER'
    prn:'PRN'
    descr:'DESCR'
    glean:'GLEAN'
    byd_mw:'BYD_MW'
    token_num:int=0
    num_slashes:int=0

    @dataclass
    class PER:
        female_per:dict[str,int]
        male_per:dict[str,int]
        amb_per:dict[str,int]
        nh_per:dict[str, int]
        ud_per:dict[str,int]
        num_matches_per:dict = field(default_factory=lambda: {'PER:weiblich':0, 'PER:männlich':0, 'PER:NA':0, 'PER:AMB':0})

    @dataclass
    class PRN:
        female_prn:dict[str,int]
        male_prn:dict[str,int]
        num_matches_prn:dict = field(default_factory=lambda: {'PRN:F':0, 'PRN:M':0})
    
    @dataclass
    class DESCR:
        female_descriptors:dict[str,int]
        male_descriptors:dict[str,int]
        ud_descriptors:dict[str,int]
        num_matches_descr:dict = field(default_factory=lambda: {'DESCR:F':0, 'DESCR:M':0, 'DESCR:NA':0})
        num_neg:int = 0

    @dataclass
    class GLEAN:
        female_glean:list[float] = field(default_factory=lambda: GLEAN_INIT)
        male_glean:list[float] = field(default_factory=lambda: GLEAN_INIT)
        ud_glean:list[float] = field(default_factory=lambda: GLEAN_INIT)
        glean_not_found:dict = field(default_factory=lambda: {'DESCR:F':0, 'DESCR:M':0, 'DESCR:NA':0})

    @dataclass
    class BYD_MW:
        match_lists:dict[dict[str,int]]
        num_matches:dict[str,int]

#### FUNCs FOR HANDLING ARTICLES #############
def flatten_article(article_dict:dict) -> Iterator[str]:
    """
    Flatten hierarchically structured article via an iterator over strings, with a speparate string for each heading (keys of the article_dict) or paragraph (values of article_dict).

    Args:
        article_dict (dict): Hierarchically structured article.

    Yields:
        Iterator[str]: Iterator over strings (headings and paragraphs).
    """
    for elem in getattr(article_dict, 'values', lambda: article_dict)():
        if isinstance(elem, str):
            yield re.sub('\xad', '', elem)
        elif isinstance(elem, dict):
            yield list(elem.keys())[0]
            yield from flatten_article(elem)
        elif elem is not None:
            yield from flatten_article(elem)


def load_text(path:str, include_meta:bool=False) -> list[str]:
    """
    Load article in path saved as json-file.

    Args:
        path (str): Path to article.
        include_meta (bool, optional): If False excludes literature references and imprints. Defaults to False.

    Returns:
        list[str]: Article content as a flatt list of paragraphs (json hierarchy not maintained).
    """
    with open(path, mode='r', encoding='utf-8') as file:
        rt = json.load(file) 
    if not include_meta and re.match('.*Literatur(angaben|hinweise|verzeichnis)?.*|Literatur und Internetadressen|.*Quellen.*|.*Impressum.*', next(iter(rt))): return None 
    frt = list(flatten_article(rt))
    frt.insert(0, list(rt)[0])
    return frt

#### FUNC FOR SAVING TOKEN OCCURRENCES #######
def write_occurences_to_file(path:str, data:dict[str,int], remove_zero:bool = True, header:list[str] = ['word', 'num_occurrences']):
    """
    Saves tokens and their numbers of occurrences provided as dictionary (``data``) to file @ ``path``.

    Args:
        path (str): File path to where the occurences shall be written to.
        data (dict[str,int]): Dictionary of occurrences in the form of ``{token_string:number_of_occurences``.
        remove_zero (bool, optional): If true, removes tokens which occur 0 times before writing to file. Defaults to True.
        header (list[str], optional): List of two strings specifying the column names. Defaults to ['word', 'num_occurrences'].
    """
    with open(path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f) 
        writer.writerow(header)
        writer.writerows([(k,v) for (k,v) in data.items() if not remove_zero or v>0])