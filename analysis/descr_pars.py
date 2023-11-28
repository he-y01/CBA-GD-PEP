#### IMPORTS #################################
from analysis.glean import glean_norm_values 
from analysis.helper import Statistics
from spacy.tokens import Doc, Token
from logging import Logger


#### CONSTANTS ###############################
SVP_DELIMITER = ''
PER_GENDER_MAPPING = {'PER:M':'PER:männlich', 'PER:F':'PER:weiblich'}
TARGET_POS = {'NOUN', 'PROPN'}


#### FUNC DEFINITIONS ########################
def obtain_gender_occurrences(t:Token, logger:Logger) -> dict[str,int]:
    """
    Obtains the gender distribution for the targets (nouns, proper nouns) starting with ``t``.

    Args:
        t (Token): First target.
        logger (Logger): Instance of used ``Logger``

    Returns:
        dict[str,int]: Dictionary of the number of occurences for female, male, and undetermined targets.
    """
    female_occurrences = 0
    male_occurrences = 0
    undetermined = 0

    if not t:
        return {'f':female_occurrences, 'm':male_occurrences, 'ud':undetermined}

    # gender for starting target ``t``
    if g := t._.gender:
        logger.debug(f"\tDESCR_PRN: {t} --- {t._.gender}")
        if g == 'PRN:F':
            female_occurrences += 1
        elif g == 'PRN:M':
            male_occurrences += 1                            
    elif t.ent_type_.startswith('PER:'):
        logger.debug(f"\tDESCR_PER: {t} --- {t.ent_type_}")
        g = t.ent_type_
        if g == PER_GENDER_MAPPING['PER:F']:
            female_occurrences += 1
        elif g == PER_GENDER_MAPPING['PER:M']:
            male_occurrences += 1
        elif g == 'PER:NA' or g == 'PER:AMB':
            undetermined += 1

    # iterate over a possible conjunctions that ``t`` is a part of
    new_children = True
    tk = t
    while new_children:
        new_children = False
        for child in tk.children:
            if child.dep_ == 'cj' and child.pos_ in TARGET_POS and is_nom(child, logger):
                new_children = True
                tk = child
                if g := child._.gender: 
                    logger.debug(f"\tDESCR_PRN_c: {tk} --- {tk._.gender}")
                    if g == 'PRN:F':
                        female_occurrences += 1
                    elif g == 'PRN:M':
                        male_occurrences += 1 
                    else:
                        new_children = False                           
                elif child.ent_type_.startswith('PER:'):
                    logger.debug(f"\tDESCR_PER_c: {tk} --- {tk.ent_type_}")
                    g = child.ent_type_
                    if g == PER_GENDER_MAPPING['PER:F']:
                        female_occurrences += 1
                    elif g == PER_GENDER_MAPPING['PER:M']:
                        male_occurrences += 1
                    elif g == 'PER:NA' or g == 'PER:AMB':
                        undetermined += 1
                    else:
                        new_children = False
                break
            elif child.dep_ == 'cd' and child.pos_ == 'CCONJ':
                new_children = True
                tk = child
                break   
    
    return {'f':female_occurrences, 'm':male_occurrences, 'ud':undetermined}
    

def parse_descriptors(doc:Doc, statistics:Statistics, logger:Logger):
    """
    Parses descriptor relations between descriptor and target words.

    Args:
        doc (Doc): Textual content to parse.
        statistics (Statistics): Data object to directly save counts to.
        logger (Logger): Instance of used ``Logger``.
    """
    for token in doc:
        adv = None
        svp = ''

        # negation
        if token.dep_ == 'ng' and token.head.pos_ in {'VERB', 'AUX', 'ADJ'}:
            statistics.descr.num_neg += 1
            continue
        
        # adjective
        if token.dep_ == 'nk' and token.pos_ == 'ADJ' and token.head.pos_ in TARGET_POS:
            factors = obtain_gender_occurrences(token.head, logger)
            descriptor = token

        # verb or adverb w/ auxilliary verb            
        elif token.dep_ in {'pd', 'oc'} and token.head.pos_ == 'AUX' and token.pos_ in {'ADV', 'VERB'}:
            n = None
            if token.head.dep_ in {'rc', 'oc'} and token.head.head.pos_ in TARGET_POS and is_nom(token.head.head, logger):
                logger.debug(f"FOUND rc: {token} -- {token.head} -- {token.head.head}")
                n = token.head.head
            else: 
                for c in token.head.children:
                    if c.pos_ in TARGET_POS and is_nom(c, logger) and c.dep_ in {'sb', 'oc'}:
                        n = c
                        break
            factors = obtain_gender_occurrences(n, logger)
            descriptor = token

        # verb (w/ or w/o adverb)
        elif token.dep_ == 'sb' and token.head.pos_ == 'VERB' and token.pos_ in TARGET_POS and is_nom(token, logger):
            factors = obtain_gender_occurrences(token, logger)
            if token.head.dep_ == 'oc' and token.head.head.pos_ in {'ADV', 'AUX'}:
                logger.debug(f"FOUND oc: {token} -- {token.head} -- {token.head.head}")
                adv = token.head.head
            for c in token.head.children:
                if c.dep_ == 'svp' and c.head == token.head:
                    svp = c.lemma_.lower() + SVP_DELIMITER
                elif not adv and c.dep_ in {'mo', 'oc'} and c.pos_ in {'ADV', 'AUX'}:
                    logger.debug(f"FOUND adv, {c.dep_}: {token} -- {token.head} -- {c}")
                    adv = c
                    logger.debug(f"ADV FOUND: {adv}")
            descriptor = token.head

        else:
            continue

        if factors['f'] == 0 and factors['m'] == 0 and factors['ud'] == 0:
            continue

        # consider a possible conjunction of descriptors
        nested_descr = []
        for token in (descriptor, adv):
            if not token: continue
            nested_descr = []
            new_children = True
            tk = token
            while new_children:
                new_children = False
                for child in tk.children:
                    if child.dep_ == 'cj' and (child.pos_ == 'ADJ' or child.pos_ == 'ADV' or child.pos_ == 'VERB'):
                        svp_c = None
                        if child.pos_ == 'VERB':
                            for c in child.children:
                                if c.dep_ == 'svp' and c.head == child:
                                    logger.debug(f"FOUND nested svp: {c} -- {c.head}")
                                    svp_c = c.lemma_.lower() + SVP_DELIMITER 
                                elif c.dep_ in {'mo', 'oc'} and c.pos_ in {'ADV', 'AUX'}:
                                    nested_descr.append(c.lemma_.lower())
                        if svp_c: nested_descr.append(svp_c + child.lemma_.lower())
                        else: nested_descr.append(child.lemma_.lower())
                        new_children = True
                        tk = child
                        break
                    elif child.dep_ == 'cd' and child.pos_ == 'CCONJ':
                        new_children = True
                        tk = child
                        break 
        if adv: nested_descr.append(adv.lemma_.lower())
        if not nested_descr == []: logger.debug(f"NESTED DESCR: {descriptor} -- {nested_descr}")

        descriptor = svp + descriptor.lemma_.lower()
        add_descriptor(descriptor, factors, statistics, logger)
        for descr in nested_descr:
            add_descriptor(descr, factors, statistics, logger)

        
def add_descriptor(descriptor:str, factors:dict[str,int], statistics:Statistics, logger:Logger):
    """
    Adds occurrences and counts for a found descriptor-target relation to ``statistics``.

    Args:
        descriptor (str): Found descriptor.
        factors (dict[str,int]): Gender distribution in target words.
        statistics (Statistics): Data object to save occurrences and counts to.
        logger (Logger): Instance of used ``Logger``.
    """
    logger.debug(f"----- {descriptor} -- {factors} -----")
    f_factor = factors['f']
    m_factor = factors['m']
    ud_factor = factors['ud']
    
    statistics.descr.female_descriptors[descriptor] = statistics.descr.female_descriptors.get(descriptor, 0) + f_factor
    statistics.descr.male_descriptors[descriptor] = statistics.descr.male_descriptors.get(descriptor, 0) + m_factor
    statistics.descr.ud_descriptors[descriptor] = statistics.descr.ud_descriptors.get(descriptor, 0) + ud_factor
    
    for key, factor in zip(statistics.descr.num_matches_descr.keys(), (f_factor, m_factor, ud_factor)):
        statistics.descr.num_matches_descr[key] += factor

    try:
        statistics.glean.female_glean = [a + f_factor*b for a,b in zip(statistics.glean.female_glean, glean_norm_values[descriptor])]
        statistics.glean.male_glean = [a + m_factor*b for a,b in zip(statistics.glean.male_glean, glean_norm_values[descriptor],)]
        statistics.glean.ud_glean = [a + ud_factor*b for a,b in zip(statistics.glean.ud_glean, glean_norm_values[descriptor])]

    except KeyError:
        for key, factor in zip(statistics.glean.glean_not_found.keys(), (f_factor, m_factor, ud_factor)):
            statistics.glean.glean_not_found[key] += factor
        if not (f_factor == 0 and m_factor == 0 and ud_factor == 0):
            logger.info(f"\tGLEAN NOT FOUND: {descriptor}")


def is_nom(t:Token, logger:Logger) -> bool:
    """
    Returns true if ``t`` is a nominal object (in the textual context it was extracted from).

    Args:
        t (Token): Token to check if nominal object.
        logger (Logger): Instance of used ``Logger``

    Returns:
        bool: True if ``t`` is a nominal object; False otherwise.
    """
    return 'Nom' in t.morph.get('Case')