####  IMPORTS ################################
import sys
import re
import copy
import logging
import logging.config
from dataclasses import dataclass, field

from bz2 import BZ2File
from wiktionary_de_parser import Parser
from wiktionary_de_parser.helper import find_paragraph

from helper import PRN_LIST_INDICATOR_FEMALE, PRN_LIST_INDICATOR_MALE

import traceback

#### CONSTANTS & GLOABAL VARIABLES ############
BZFILE_PATH = 'data/meta/dewiktionary-20231001-pages-articles-multistream.xml.bz2' # Wiktionary data dump retrieved from: https://dumps.wikimedia.org/dewiktionary/20231001/
bz_file = BZ2File(BZFILE_PATH)

VERSION_EXT = '_v21'
PATH_PRN_LIST = f"analysis/prn_list{VERSION_EXT}.csv"
PATH_PRN_STATS = f"analysis/prn_stats{VERSION_EXT}"


#### CLASS AND FUNC DEFINITIONS ###############
@dataclass
class PRNs():
    """
    Helper class to structure and handle compiled PRNs.
    """
    female:'Female'
    male:'Male'

    @dataclass
    class Female():
        sg:list[str] = field(default_factory=lambda: list())
        pl:list[str] = field(default_factory=lambda: list())
        oe:int = 0
        retrieved_from:dict[str,set] = field(default_factory=lambda: dict())

    @dataclass
    class Male():
        sg:list[str] = field(default_factory=lambda: list())
        pl:list[str] = field(default_factory=lambda: list())
        oe:int = 0
        retrieved_from:dict[str,set] = field(default_factory=lambda: dict())

    def to_list(self, sublists:list[list[str], str]=None) -> list[tuple[str,str]]:
        """
        Combines all sublists (female, male x sg, pl) into a single lists (dublicates are retained).

        Args:
            sublists (list[list[str], str], optional): A list of sublists can be provided if not all sublists should be combined into the single list. Defaults to None.

        Returns:
            list[tuple[str,str]]: Combined lists of (non-unique) PRNs.
        """
        prn_list = []

        for sublist, label, source_dict in sublists if sublists else [(self.female.sg, PRN_LIST_INDICATOR_FEMALE, self.female.retrieved_from), (self.female.pl, PRN_LIST_INDICATOR_FEMALE, self.female.retrieved_from), 
                                                                      (self.male.sg, PRN_LIST_INDICATOR_MALE, self.male.retrieved_from), (self.male.pl, PRN_LIST_INDICATOR_MALE, self.male.retrieved_from)]:
            prn_list.extend([(t.strip(), label, f"{'; '.join([f'https://de.wiktionary.org/w/index.php?title={source_title}' for source_title in source_dict[t]])}") for t in sublist if not t == '' and not re.search('^ *[a-z].*|^-.*', t)])

        return prn_list
    
    def to_unique_list(self) -> set[tuple[str,str]]:
        """
        Combines all sublists (female, male x sg, pl) into a single set (dublicates are removed within gender groups; tokens occuring across gender groups (i.e., for both female and male) are removed completely).

        Returns:
            set[tuple[str,str]]: Combined set of unique PRNs
        """
        female = set(self.female.sg) | set(self.female.pl)
        male = set(self.male.sg) | set(self.male.pl)

        dummy = copy.deepcopy(female)
        female -= male
        male -= dummy

        return set(self.to_list(sublists=[(female, PRN_LIST_INDICATOR_FEMALE, self.female.retrieved_from), (male, PRN_LIST_INDICATOR_MALE, self.male.retrieved_from)]))
    
    def write_to_file(self, unique:bool=True, path:str=PATH_PRN_LIST):
        """
        Writes PRNs to a file @ ``path``.

        Args:
            unique (bool, optional): If true, dublicates within and across group are removed (i.e., ``to_unique_list()`` us used). Defaults to True.
            path (str, optional): File Path to where the PRNs shall be saved. Defaults to PATH_PRN_LIST.
        """
        prns = self.to_unique_list() if unique else self.to_list()
        with open(path, mode='w', encoding='utf-8') as file:
            file.write('\n'.join(f"{t[1]},{t[0]},{t[2]}" for t in prns))
    
    def print_stats(self, save_to_file:str=PATH_PRN_STATS):
        """
        Prints a statistical summary for the PRNs.

        Args:
            save_to_file (str, optional): File path to where the statistics shall be saved; if None statistics are only printed to console. Defaults to PATH_PRN_STATS.
        """
        LOGGING_CONFIG = {
            'version': 1,
            'disable_existing_loggers': True,
            'formatters': { 
                'standard': {
                    'format': '{message}',
                    'style': '{'
                }
            },
            'handlers': {
                'console':  {'class': 'logging.StreamHandler', 
                            'formatter': "standard", 
                            'level': 'DEBUG', 
                            'stream': sys.stdout},
                'file':     {'class': 'logging.FileHandler', 
                            'formatter': "standard", 
                            'level': 'INFO', 
                            'filename': f"{save_to_file}.stats",
                            'mode': 'w',
                            'encoding': 'UTF-8'} 
            },
            'loggers': { 
                __name__:   {'level': 'INFO', 
                            'handlers': ['console', 'file'] if save_to_file else ['console'], 
                            'propagate': False}
            }
        }

        logging.config.dictConfig(LOGGING_CONFIG)
        log = logging.getLogger(__name__)

        female_total = len(self.female.sg) + len(self.female.pl)
        male_total = len(self.male.sg) + len(self.male.pl)

        female_sg_set = set(self.female.sg)
        female_pl_set = set(self.female.pl)
        male_sg_set = set(self.male.sg)
        male_pl_set = set(self.male.pl)

        log.info(f"==== prn list statistics =============")

        log.info(f"OVERALL")
        log.info(f"|  {'total':<25}{female_total + male_total:>6}")
        log.info(f"|  {'->  total unique':<25}{len(female_sg_set | female_pl_set | male_sg_set | male_pl_set):>6}")


        for gender, total, sg_list, sg_set, pl_list, pl_set, other_set in [
            ('female', female_total, self.female.sg, female_sg_set, self.female.pl, female_pl_set, (male_sg_set | male_pl_set)),
            ('male', male_total, self.male.sg, male_sg_set, self.male.pl, male_pl_set, (female_sg_set |female_pl_set))
        ]:
            log.info(f"\n{gender.upper()}")
            log.info(f"|  {'total':<25}{total:>6}")
            log.info(f"|  {f'->  unique within {gender}':<25}{len(sg_set | pl_set):>6}")
            log.info(f"|  {'->  unique across gender':<25}{len((sg_set | pl_set) - other_set):>6}")
            log.info(f"|  {'singular':<25}{len(sg_list):>6}")
            log.info(f"|  {f'->  unique within {gender}':<25}{len(sg_set):>6}")
            log.info(f"|  {'->  unique across gender':<25}{len(sg_set - other_set):>6}")
            log.info(f"|  {'plural':<25}{len(pl_list):>6}")
            log.info(f"|  {f'->  unique within {gender}':<25}{len(pl_set):>6}")
            log.info(f"|  {'->  unique across gender':<25}{len(pl_set - other_set):>6}")


def compile(save_to_file:bool=True, save_stats:bool=True):
    """
    Compile a list of PRNs (and their gender affiliation) from German Wiktionary dump.

    Args:
        save_to_file (bool, optional): If true, saves compiled list to file. Defaults to True.
        save_stats (bool, optional): If true, saves statistics to file. Defaults to True.
    """
    prn_obj = PRNs(PRNs.Female(), PRNs.Male())

    def filter(_, text, current_record):
        gender = None

        try:
            if 'lang_code' not in current_record or current_record['lang_code'] != 'de':
                return False
        
            if list(current_record['pos'].keys())[0] == 'Substantiv' and not 'Nachname' in current_record['pos']['Substantiv']:
                match_wwf = find_paragraph('Weibliche Wortformen', text)
                match_mwf = find_paragraph('Männliche Wortformen', text)

                if ob := find_paragraph('Oberbegriffe', text):
                    for x in ['tier', 'vogel', 'stute', 'hengst', 'pferd', 'fabelwesen']:
                        if x in ob.lower():
                            return False
                elif ub := find_paragraph('Unterbegriffe', text):
                    for x in ['tier', 'vogel', 'stute', 'hengst', 'pferd', 'fabelwesen']:
                        if x in ub.lower():
                            return False

                if match_wwf and not match_mwf:
                    sg = [re.sub('_m|_f|<.*(<|>)|\*|.*_.*|.*(<|>)|(^|\'\').*\'\'|^:|^ *(der|die|das)|#| ', '', wf) for wf in re.split(',|/|\||;|:', re.sub(':\[.*\] |\[\[|\]\]|<.*/>|\{\{.*\}\}|\(.*\)|\n|#Substantiv', ' ', match_wwf))]
                    prn_obj.female.sg.extend(sg)
                    for elem in sg:
                        new = prn_obj.female.retrieved_from.get(elem,set())
                        new.add(current_record['title'])
                        prn_obj.female.retrieved_from[elem] = new
                    gender = PRN_LIST_INDICATOR_MALE
                    try:
                        pl = [v for k, v in current_record['flexion'].items() if k.startswith('Nominativ Plural')]
                        prn_obj.male.pl.extend(pl)
                        for elem in pl:
                            new = prn_obj.male.retrieved_from.get(elem,set())
                            new.add(current_record['title'])
                            prn_obj.male.retrieved_from[elem] = new
                    except:
                        pass
                
                elif match_mwf and not match_wwf:
                    sg = [re.sub('_m|_f|<.*(<|>)|\*|.*_.*|.*(<|>)|(^|\'\').*\'\'|^:|^ *(der|die|das)|#| ', '', wf) for wf in re.split(',|/|\||;|:', re.sub(':\[.*\] |\[\[|\]\]|<.*/>|\{\{.*\}\}|\(.*\)|\n|#Substantiv', ' ', match_mwf))]
                    prn_obj.male.sg.extend(sg)
                    for elem in sg:
                        new = prn_obj.male.retrieved_from.get(elem, set())
                        new.add(current_record['title'])
                        prn_obj.male.retrieved_from[elem] = new
                    gender = PRN_LIST_INDICATOR_FEMALE
                    try:
                        pl = [v for k, v in current_record['flexion'].items() if k.startswith('Nominativ Plural')]
                        prn_obj.female.pl.extend(pl)
                        for elem in pl:
                            new = prn_obj.female.retrieved_from.get(elem, set())
                            new.add(current_record['title'])
                            prn_obj.female.retrieved_from[elem] = new
                    except:
                        pass
        
        except Exception as e:
            print(e)
            print(current_record)

        return {'gender': gender} if gender else False


    for record in Parser(bz_file, custom_methods=[filter]):
        if 'gender' not in record:
            continue

        if record['gender'] == PRN_LIST_INDICATOR_FEMALE:
            prn_obj.female.sg.append(record['title'])
            new = prn_obj.female.retrieved_from.get(record['title'], set())
            new.add(record['title'])
            prn_obj.female.retrieved_from[record['title']] = new
            prn_obj.female.oe += 1
        elif record['gender'] == PRN_LIST_INDICATOR_MALE:
            prn_obj.male.sg.append(record['title'])
            new = prn_obj.male.retrieved_from.get(record['title'], set())
            new.add(record['title'])
            prn_obj.male.retrieved_from[record['title']] = new
            prn_obj.male.oe += 1

    if save_to_file: prn_obj.write_to_file()
    if save_stats: prn_obj.print_stats()

if __name__ == '__main__':
    compile()