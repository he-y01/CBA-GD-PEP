#### IMPORTS #################################
# misc
import sys
import logging
import logging.config
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
import csv
import json
import re
import traceback

# webscraping libraries
import requests
from selenium import webdriver
from bs4 import BeautifulSoup, Tag

# spaCy (nlp tool)
import spacy
from spacy.language import Language

# own modules
from analysis.helper import flatten_article
from analysis.fa_per import obtain_gender
import analysis.fa_prn as fa_prn


#### CONSTANTS & GLOABAL VARIABLES ###########
# webscraping
BASE_URL = 'https://www.bpb.de'
list_url = lambda p: BASE_URL + '/bpbapi/filter/generic?page=' + str(p) + '&sort[direction]=descending&language=de&query[field_filter_thema]=all&query[field_date_content]=all&query[d]=1&payload[nid]=122&payload[type]=default'
HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.41'}

# data storage
DATA_PATH = 'data/'
DATA_PATH_ARTICLES = f"{DATA_PATH}articles/"

# author gender inference
PER_GENDER_MAPPING = {'männlich':'M', 'weiblich':'F', 'NA':'NA', 'AMB':'AMB'}
PER_GENDER_DEFAULT = 'O' 
PRN_LIST_PATH = 'analysis/prn_list_v21_adjusted.csv'


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
                     'filename': f"{DATA_PATH}logs/izpb-scraper_{int(datetime.now(timezone.utc).timestamp())}.log",
                     'mode': 'w',
                     'encoding': 'UTF-8'} 
    },
    'loggers': { 
        __name__:   {'level': 'INFO', 
                     'handlers': ['console', 'file'], 
                     'propagate': False}
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger(__name__)


#### CLASS AND FUNC DEFINITIONS ##############
@dataclass
class Volume:
    """
    Helper class to structure the data retrieved for each issue of the IzpB magazine.
    """
    title:str
    id:str
    uuid:str
    url:str
    authors:list[str]
    abstract_short:str
    series:str
    language:str
    created:datetime
    modified:datetime
    price:int
    availability:dict[str,bool]         # {'online':False/True, 'pdf':False/True}
    abstract_long:list[str] = None
    note:str = None
    place:str = None
    vol:str = None
    pages:int = None
    published:datetime = None

def get_content(elem:Tag, h_level:int, heading:bool) -> list[dict]:
    """
    Recursively retrieves and structures an article's content in a json-like format according to the respective HTML-tags (``p`` and ``h1``-``h6``).
    Example Structure (only the value for 'title' will be returned, the title has to be added manually: ``{title: article_content}``)::
    
        {'title': [
            {'h3': ['p', 'p']},
            {'h3': [
                'p', 'p',
                {'h4': ['p', 'p', 'p']}, 
                {'h4': [
                    {'h6': ['p']}  # there might be a jump in headings
                ]}
            ]}
        ]}

    Args:
        elem (Tag): HTML content parsed with ``bs4``.
        h_level (int): Current heading level if elem is a paragraph, previous heading level is elem is a heading itself.
        heading (bool): Helper variable to mitigate duplicate processing of the same paragraph; search for headings on the same level and avoid multiple recursive calls.

    Raises:
        Exception: Raised if elem is not in the proper HTML (bs4.Tag) format.

    Returns:
        list[dict]: Json-like representation of the article's content (or parts of it during recursion).
    """
    if elem is None:
        return [] # Recursion anchor: no more content existent
    
    # elem is a paragraph
    elif 'p' in elem.name:
        next_elem = elem.find_next_sibling([re.compile('^h[1-6]$'), 'p'], slot="", recursive=False)
        if heading:
            return get_content(next_elem, h_level, True)
        
        succ = get_content(next_elem, h_level, False)

        # cleaning
        for br in elem.find_all('br'):
            br.replace_with('\n' + br.text.strip())
        res = [s.strip() for s in re.split('\n\s*\n\s*\n?', elem.text.strip())] 

        if isinstance(succ, list):
            res.extend(succ)
        else:
            res.append(succ)
        return res  
    
    # elem is a heading
    elif 'h' in elem.name:
        next_elem = elem.find_next_sibling([re.compile('^h[1-6]$'), 'p'], slot="", recursive=False)
        if h_level == int(elem.name[-1]): # New heading is on same level as the previous heading
            h_level = int(elem.name[-1])
            res = [{elem.text.strip(): get_content(next_elem, h_level+1, False)}]
            x = get_content(next_elem, h_level, True)
            res.extend(x) 
            return res
        elif h_level < int(elem.name[-1]): # New heading is a subheading of the previous heading
            return get_content(next_elem, h_level, True)
        else: # New heading is not on the same level as the previous one and netiher a subheading of it
            return [] # Recursion anchor: go upward in hierarchy
    
    # elem is not in the proper format (bs4.Tag)
    else:
        raise Exception('FormatException: The HTML article is not in the proper format.')


def infer_gender(nlp:Language, name:str, info:str) -> tuple[int,int,int]:
    """
    Collects gender information based on pronouns and people-related nouns in info as well as Wikidata entries for ``name``.

    Args:
        nlp (Language): Already setup spaCy NLP ``Language`` object.
        name (str): Person's / Author's name.
        info (str): Information text about that person / author (``name``).

    Returns:
        tuple[int,int,int]: 3-tuple with a gender descriptor ('AIG:M'/'AIG:F'/'AIG:AMB/'AIG:NA') for each method (pronouns, people-related nouns, Wikidata).
    """
    doc = nlp(info)

    gender_prn = 'AIG:NA'
    gender_ppn = 'AIG:NA'
    gender_ppn_set = set()

    # --- wikidata ----------------------
    gender_wikidata = 'AIG:' + PER_GENDER_MAPPING.get(obtain_gender(name)[4:], PER_GENDER_DEFAULT)
    num_matches_prn = fa_prn.count_prn(doc)

    # --- pronouns -----------------------
    for token in doc:
        if token.tag_ in ['PPER', 'PPOSAT']:
            if token.lemma_.lower()  in ['sie', 'ihr', 'ihre']:
                gender_ppn_set.add('AIG:F')
            elif token.lemma_.lower() in ['er', 'sein', 'seine', 'ihn', 'ihm']:
                gender_ppn_set.add('AIG:M')

    if len(gender_ppn_set) == 1:
        gender_ppn = gender_ppn_set.pop()
    elif len(gender_ppn_set) > 1:
        gender_ppn = 'AIG:AMB'
    
    # --- people-related ouns -----------
    if num_matches_prn['PRN:F'] == 0 and num_matches_prn['PRN:M'] != 0:
        gender_prn = 'AIG:M'
    elif num_matches_prn['PRN:F'] != 0 and num_matches_prn['PRN:M'] == 0:
        gender_prn = 'AIG:F'
    elif num_matches_prn['PRN:F'] != 0 and num_matches_prn['PRN:M'] != 0:
        log.info(f"AIG; prn ambiguous: {name} --- {num_matches_prn}")
        gender_prn = 'AIG:AMB'
        return gender_wikidata, gender_ppn, gender_prn

    # --- no-conflict check -------------
    if (gender_wikidata == 'AIG:NA' or gender_wikidata == 'AIG:AMB') and gender_ppn == 'AIG:NA' and gender_prn == 'AIG:NA':
        log.info(f"AIG; no information found: {name}")
    elif ((gender_wikidata != gender_ppn and 'AIG:NA' not in {gender_wikidata, gender_ppn}) or 
          (gender_wikidata != gender_prn and 'AIG:NA' not in {gender_wikidata, gender_prn}) or
          (gender_ppn != gender_prn and 'AIG:NA' not in {gender_ppn, gender_prn})):
        log.info(f"AIG; information ambigiuous: {name} --- wd:{gender_wikidata}, ppn:{gender_ppn}, prn:{gender_prn} {num_matches_prn}")
    else:
        log.debug(f"AIG; found: {name} --- wd:{gender_wikidata}, ppn:{gender_ppn}, prn:{gender_prn}, {num_matches_prn}")

    return gender_wikidata, gender_ppn, gender_prn


#### EXECUTE WEBSCRAPING #####################
def run():
    # --- setup -------------------------
    log.info(f"SETUP")
    corpus = []

    api_page = 0
    response = json.loads(requests.get(list_url(api_page), HEADER).content)

    browser = webdriver.Firefox(executable_path=r'C:\Program Files (x86)\geckodriver-v0.33.0-win64\geckodriver.exe')

    authors = set()
    articles = []

    nlp = spacy.load('de_core_news_lg')
    nlp.add_pipe('gender_prn')
    fa_prn.setup(PRN_LIST_PATH, log)  

    # --- page loop ---------------------
    # iterate pages listing the volumes
    log.info(f"GET VOLUMES")
    teasers = []
    while response['offset'] < response['count']:
        teasers.extend(response['teaser'])
        api_page += 1
        response = json.loads(requests.get(list_url(api_page), HEADER).content)

    if log.level == logging.DEBUG:
        teasers = teasers[:5]
    volume_ids = [teaser['meta']['id'] for teaser in teasers]
    num_volumes = len(volume_ids)
    log.info(f"-> {len(set(volume_ids))} volumes found.")

    # --- volume loop -------------------
    # iterate through the volumes listed on each page
    for i, teaser in enumerate(teasers):
        # collect volume information
        log.info('='*150)
        log.info(f"Loading {i+1:>2} / {num_volumes:>2}\t{teaser['teaser']['title']}")
        info, meta, ext = teaser['teaser'], teaser['meta'], teaser['extension']
        
        v = Volume(
            title = info['title'],
            id = meta['id'],
            uuid = uuid.uuid3(uuid.NAMESPACE_URL, BASE_URL + info['link']['url']),
            url = info['link']['url'],
            authors = [name['name'] for name in ext['authors']],
            abstract_short = info['text'],
            series = ext['overline'],
            language = meta['language'],
            created = datetime.fromtimestamp(meta['creationDate']),
            modified = datetime.fromtimestamp(meta['modificationDate']),
            price = ext['price'],
            availability = {key: key in ext['availability'] for key in ['online', 'pdf']}
        )
        
        log.info(f"\t\t\t\t{BASE_URL + v.url}")
        vpage = BeautifulSoup(requests.get(BASE_URL + v.url, HEADER).content, features='html.parser')
        v.abstract_long = [p.text.strip() for p in vpage.find(text='Inhaltsbeschreibung').parent.parent.parent.find_all('p')]

        tb = vpage.find(text='Produktinformation').parent.parent.parent
        with suppress(AttributeError): v.note = tb.find('th', text=re.compile('Hinweis.:')).parent.find('td').text.strip()
        with suppress(AttributeError): v.place = tb.find('th', text='Erscheinungsort:').parent.find('td').text.strip()
        with suppress(AttributeError): v.vol = tb.find('th', text='Ausgabe:').parent.find('td').text.strip()
        with suppress(AttributeError): v.pages = int(tb.find('th', text='Seiten:').parent.find('td').text.strip())
        with suppress(AttributeError): v.published = datetime.strptime(tb.find('th', text='Erscheinungsdatum:').parent.find('td').text.strip(), '%d.%m.%Y')

        corpus.append(v)

        if not v.availability['online']:
            log.warning(f"skipped {v.title}; not available online")
            continue

        # --- article loop ------------------
        alinks = vpage.find_all('a', class_='content-index__link', href=True)
        if log.level == logging.DEBUG:
            alinks = alinks[:2]
        for link in alinks:
            # collect the article's content
            url = link['href']
            log.info(f"\t\t\tOPEN:\t{url}")
            apage = BeautifulSoup(requests.get(BASE_URL + url, HEADER).content, features='html.parser')
            title = re.sub('\s*\n\s*', ' /// ', apage.find('h2', class_='opening-header__title').text.strip())            

            for empty_elem in apage.find_all([re.compile('^h[1-6]$'), 'div', 'p']):
                if len(empty_elem.get_text(strip=True)) == 0:
                    empty_elem.extract()
            content = apage.find('div', class_='text-content')

            try:
                first_heading = content.find(re.compile('^h[1-6]$'))
                atext = get_content(content.find([re.compile('^h[1-6]$'), 'p'], slot="", recursive=False), int(first_heading.name[-1]) if first_heading else 3, False)
            except Exception as e:
                log.warning(f"No text content could be retieved: {e}")
                atext = []
            
            # collect author information and infer gender
            author = []
            author_info = []
            author_inferred_gender_wd = []
            author_inferred_gender_ppn = []
            author_inferred_gender_prn = []

            try:
                apage.find('span', class_='opening-header__author').text

                try:
                    browser.get(BASE_URL + url)
                    for elem in browser.find_elements_by_class_name('popup--author'):
                        elem.click()
                        author.append(elem.text.strip().split('\n')[0])
                        popup = browser.find_element_by_class_name('popup-dialog__content')
                        info = re.sub('\n+', ' ', popup.text.strip())
                        author_info.append(re.sub('\xad', '', info))
                        wd, ppn, prn = infer_gender(nlp, author[-1], author_info[-1])
                        author_inferred_gender_wd.append(wd)
                        author_inferred_gender_ppn.append(ppn)
                        author_inferred_gender_prn.append(prn)
                        browser.find_element_by_class_name('popup-dialog__close').click()
                        # log.info(f"\t\t\tAUTHORS: {author}")
                    if author == []:
                        raise Exception('[[own]]')
                except Exception as e:
                    try:
                        ats = apage.find('span', class_='opening-header__author').text.split('/')
                        author.extend([n.strip() for n in ats])
                        author_info.extend(['' for _ in ats])
                        empty = ['' for _ in ats]
                        author_inferred_gender_wd.extend(empty)
                        author_inferred_gender_ppn.extend(empty)
                        author_inferred_gender_prn.extend(empty)
                        log.info(f"\t\t\t\tAUTHORS; no info: {author}")
                    except Exception as e:
                        log.warning(f"Author(s) could not be retrieved: {e}")
                        author = None
                        author_info.append('')
                        author_inferred_gender_wd.append('')
                        author_inferred_gender_ppn.append('')
                        author_inferred_gender_prn.append('')
                
            except AttributeError as e:
                #print(e)
                #print(title)
                if title == 'Editorial':
                    try:
                        if len(atext[-1].split(' ')) < 8:
                            author.append(atext[-1])
                            del atext[-1]
                        else:
                            log.info(f"No author given for Editorial.")
                            author = None
                    except AttributeError as e:
                        print(e)
                        if len(atext[-1]['Editorial'][-1].split(' ')) < 8:
                            author.append(atext[-1]['Editorial'][-1])
                            del atext[-1]['Editorial'][-1]
                        else:
                            log.info(f"No author given for Editorial.")
                            author = None
                    author_info.append('<<EDITOR>>')
                else:
                    log.info(f"No author given: {e}")
                    author_info.append('')
                author_inferred_gender_wd.append('')
                author_inferred_gender_ppn.append('')
                author_inferred_gender_prn.append('')
            
            # collect article information
            article = {title: atext}
            article_uuid = uuid.uuid3(uuid.NAMESPACE_URL, BASE_URL + url)
            article_length = sum(len(par) for par in flatten_article(article)) # w/o title! w/ title: + len(title)

            if author:
                author_uuids = []
                for a, i, g_wd, g_ppn, g_prn in zip(author, author_info, author_inferred_gender_wd, author_inferred_gender_ppn, author_inferred_gender_prn):
                    author_uuids.append(str(uuid.uuid3(uuid.NAMESPACE_URL, BASE_URL + v.url + a.replace(' ', '_'))))
                    authors.add((author_uuids[-1], a, i, g_wd, g_ppn, g_prn))
                articles.append([article_uuid, title, article_length, author_uuids, v.uuid, datetime.now(timezone.utc).timestamp()])
            else:
                articles.append([article_uuid, title, article_length, None, v.uuid, datetime.now(timezone.utc).timestamp()])
            
            # save article
            with open(f"{DATA_PATH_ARTICLES}{article_uuid}.json", mode='w', encoding='utf-8', newline='') as file:
                json.dump(article, file, indent=2, ensure_ascii=False)
                log.info(f"\t\t\tSAVE:\t{article_uuid}")
            
            log.debug(f"Article as JSON:\n{json.dumps(article, indent=2)}")
            log.debug(f"Article as flattened list:\n{list(flatten_article(atext))}")

    browser.quit()

    # --- save lists --------------------
    # of volumes, author, and articles
    with open(f"{DATA_PATH}izpb-corpus_authors.csv", mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['uuid', 'author', 'info', 'inferred_gender_wd', 'inferred_gender_ppn', 'inferred_gender_prn'])
        writer.writerows(authors)

    with open(f"{DATA_PATH}izpb-corpus_articles.csv", mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['uuid', 'title', 'article_length', 'author_uuids', 'volume_uuid', 'retrieval_date_unix'])
        writer.writerows(articles)

    with open(f"{DATA_PATH}izpb-corpus_volumes.csv", mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(corpus[0].__dict__.keys())
        writer.writerows([elem.__dict__.values() for elem in corpus])


if __name__ == '__main__':
    run()