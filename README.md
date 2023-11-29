# A Computer-Based Analysis of Gender Depictions in Politico-Educational Publications

This GitHub repository contains the Python scripts, Rmd-notebooks, and additional files created and developed as part of the bachelor's thesis

> Language Performativity, Social Representation, and Distant Reading:
> A Computer-Based Analysis of Gender Depictions in Politico-Educational Publications

by Yannik Heß, handed in on November 30, 2023, at the Institute of Cognitive Science of the University of Osnabrück.

## Abstract (bachelor's thesis)

This bachelor’s thesis looks into how natural language processing (NLP) and the principle of distant reading can be used to examine performed discrimination against people of non-male and non-heteronormative gender in politico-educational publications. Theories of performativity by Austin ([1962](#1)), Butler ([1988](#2), [2009](#3)), and Ochs ([1990](#6)) serve as the theoretical background. The proposed methods are being showcased using the German Federal Agency for Civic Education’s (bpb) magazine Informationen zur politischen Bildung. 

Lucy et al.’s ([2020](#3)) work on the illustration of different gender and and ethnic groups in U.S. history textbooks is the methodological starting point and used to develop similar techniques for the German language (gender only). The representation and depictions of various gender groups are analyzed through the existence or non-existence of particular regular expressions, named well-known people, and people-related nouns. 

Similar to other research on gender biases in educational material, a male bias – especially in form of masculine generics – can be found in the magazine’s articles. Women are underrepresented and stereotypical tendencies can be found in their depictions. There are only very rare references to people of non-heteronormative gender identities. Developments in the last years, however, are rather towards an inclusive representation of women and all gender identities. 

Besides showing first methodological successes, this thesis also discusses the main shortcomings the proposed techniques are still facing. It tries to encourage the development of tools combining the strengths of distant and close reading as well as to advocate for further, interdisciplinary research on performativity, real world effects, and how they can be analyzed on a large scale.

## How to use this project

_Clone the repository_
```
git clone https://github.com/he-y01/CBA-GD-PEP.git
```

_Install requirements_
```
pip install -r requirements.txt
```

### Web scraping

_Run the web scraping (as a module!)_
```
python -m webscraper.scraper
```

### Analysis

_Execute the analysis (as a module!)_
```
python -m analysis.main
```

#### Recompile PRN list

To recompile the PRN list, download a German Wiktionary dump (e.g., [dewiktionary-20231001-pages-articles-multistream.xml.bz2](https://dumps.wikimedia.org/dewiktionary/20231001/dewiktionary-20231001-pages-articles-multistream.xml.bz2)) from [Index of /dewiktionary/ (wikimedia.org)](https://dumps.wikimedia.org/dewiktionary/) and place it into the `data/meta` folder.

_Compile PRN list_
```
python analysis/compile.py
```


### Evaluation

The evaluation conducted for the affiliated bachelor's thesis, can be inspected in the knitted Rmd-notebooks under [evaluation/](evaluation/).

To rerun or adapt the evaluation procedure, download the embedded source code from the HTML-file via the "Code" button in the upper right corner.


## Abbreviations

The affiliated bachelor's thesis clearly differentiates between theoretical concepts (well-known people, people-related nouns, gender identity) and the practically implementable versions of them (e.g., people that spaCy's NER recognizes as PER and that have a Wikidata entry with gender/sex information).

As the contents of this repository are the implementation (which can never be an exact representation of the theoretical concepts), the scripts do not make such distinction. The most common abbreviations are:
- prn (people-realted nounds)
- per (well-known people)
- aig (authors' inferred gender)
- f (female /  women)
- m (male / men)
- ud (undetermined)
- amb (ambiguous)

## Data sources

### GLEAN

This project uses Lüdtke & Hugentobler's ([2022](#5)) "German list of extrapolated affective norms" (stored in [Norm_values_GLEAN.csv](data/meta/Norm_values_GLEAN.csv)) as German connotation lexicon to examine whether women are described differently compared to men.
It is made available by the authors under the [Creative Commons Attribution 4.0 International License (CC BY-SA 4.0)](https://creativecommons.org/licenses/by/4.0/) and can be downloaded [here](https://osf.io/a6w53/).

### dewiktionary

The German Wiktionary project is used to compile a list of German nouns that reference either a female or male person or group of people. The textual contents of Wiktionary are licensed under the Creative Commons AttributionShareAlike 4.0 International License ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)).

The script [compile_prn_list.py](analysis/compile_prn_list.py) states how the PRN list is being obtained from the data. A PRN list compiled from the [dewiktionary-20231001-pages-articles-multistream.xml.bz2](https://dumps.wikimedia.org/dewiktionary/20231001/dewiktionary-20231001-pages-articles-multistream.xml.bz2) dump is saved in [prn_list_v21.csv](analysis/prn_list_v21.csv), while [prn_list_v21_adjusted.csv](analysis/prn_list_v21_adjusted.csv) contains additional manual adjustments.

In compliance with Wiktionary's license and terms of use, both PRN lists are made available under the same [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license. Furthermore, the PRN lists contains contain a column for URLs to the source pages on Wiktionary where the respective contributors are listed.

### Wikidata

This project only uses information from Wikidata that is part of either the main (entries with IDs starting with Q) or the property (entries with IDs starting with P) namespace.

Structured data in these namespaces is licensed under Creative Commons Universal 1.0 License ([CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)) making them part of the public domain and thereby free to use. Still, the invaluable work of the Wikimedia Foundation and all contributing authors shall be emphasized here.

### IzpB magazine

The bpb's magazine "Informationen zur politischen Bildung" ("Information for Political Education") is used to showcase the developed methods. 
The volumes are made available to the public free of charge and can be obtained from the bpb's website: [https://www.bpb.de/shop/zeitschriften/izpb/](https://www.bpb.de/shop/zeitschriften/izpb/).
The file [izpb-corpus_article-list.csv](logs-bachelorthesis/izpb-corpus_article-list.csv) lists all articles that were analyzed and evaluated as part of the affiliated bachelor's thesis.


## Licensing

The source code of this project (Python scripts, and Rmd-notebooks) is made available under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).

The compiled PRN lists ([prn_list_v21.csv](analysis/prn_list_v21.csv) and [prn_list_v21_adjusted.csv](analysis/prn_list_v21_adjusted.csv)) are licensed under the Creative Commons AttributionShareAlike 4.0 International License ([CC BY-SA 4.0)](https://creativecommons.org/licenses/by/4.0/).

## References

<a id="1">[1]</a>
Austin, J. L. (1962). How to do things with words: The William James Lectures delivered at Harvard University in 1955 (J. O. Urmson, Ed.). Oxford University Press.

<a id="2">[2]</a>
Butler, J. (1988). Performative acts and gender constitution: An essay in phenomenology and feminist theory. Theatre Journal, 40 (4), 519–531. https://doi.org/10.2307/3207893

<a id="3">[3]</a>
Butler, J. (2009). Performativity, precarity and sexual politics. Revista de Antropología Iberoamericana, 4 (3). https://recyt.fecyt.es/index.php/AIBR/article/view/32682

<a id="4">[4]</a>
Lucy, L., Demszky, D., Bromley, P., & Jurafsky, D. (2020). Content analysis of textbooks via natural language processing: Findings on gender, race, and ethnicity in Texas U.S. history textbooks. AERA Open, 6 (3), 1–27. https://doi.org/10.1177/2332858420940312

<a id="5">[5]</a>
Lüdtke, J., & Hugentobler, K. G. (2022, August 19). Using emotional word ratings to extrapolated norms for valence, arousal, imageability and concreteness: The German list of extrapolated affective norms (G-LEAN). In E. Ferstl, L. Konieczny, R. von Stülpnagel, J. Beck, & L. Zacharski (Eds.), Proceedings of the 15th biannual conference of the german society for cognitive science. OSF. Retrieved May 30, 2023, from https://osf.io/a6w53/

<a id="6">[6]</a>
Ochs, E. (1990). Indexicality and socialization. In J. W. Stigler, R. A. Shweder, & G. H. Herdt (Eds.), Cultural psychology: Essays on comparative human development (pp. 287–308). Cambridge Univ. Press
