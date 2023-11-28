####  IMPORTS ################################
import csv
import pandas as pd


#### CONSTANTS & GLOABAL VARIABLES ###########
GLEAN_NV_PATH = 'data/meta/Norm_values_GLEAN.csv'

glean_norm_values = {}


#### READ IN GLEAN VALUES ####################
with open(GLEAN_NV_PATH, mode='r', encoding='utf-8') as file:
    reader = csv.reader(file, delimiter=';')
    next(reader, None)
    for row in reader:
        glean_norm_values[row[0]] = [
            float(row[1]),     # arousal
            float(row[2]),     # valence
            float(row[3]),     # imageability
            float(row[4])      # concreteness
        ]


#### EXPLORE GLEAN VALUES ####################
if __name__ == '__main__':
    glean_df = pd.DataFrame.from_dict(glean_norm_values,
                                      orient='index',
                                      columns=['arousal','valence','imageability','concreteness'])
    
    print('=== STATISTICS =======================================')
    print(glean_df.describe(), '\n')
    print(glean_df.agg(['idxmin','min', 'idxmax', 'max']), '\n')
    print(glean_df.sort_values(by='arousal').head(3), '\n')

    print('\n=== SOME EXAMPLES ====================================')
    for word in ['schön', 'paradox', 'windig', 'der', 'Wort', 'alksdjfhalskjfh']:
        try:
            print(f"{word:.<30}{[round(v, 2) for v in glean_norm_values[word]]}")
        except KeyError:
            print(f"{word:.<30}[no entry]")

    print('\n\n=== GLEAN VALUE LOOKUP ===============================')
    while token := input('\nPlease enter a word: '):
        try:
            print(glean_df.loc[token])
        except KeyError:
            print('no entry found')
