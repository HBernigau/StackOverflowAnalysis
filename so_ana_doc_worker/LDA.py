"""
contains helper functions related to creation of LDA model

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import os
import sys
sys.stderr = open(os.devnull, "w") # hide DeprecationWarnings from moduls import
from gensim.models.ldamodel import LdaModel
sys.stderr = sys.__stderr__
from datetime import datetime
from gensim.corpora import Dictionary

def create_LDA_model(step,
                     step_label,
                     base_path,
                     base_path_lda,
                     dictionary_key,
                     corpus,
                     **kwargs
                     ):
    dictionary_path = os.path.join(base_path, dictionary_key)
    dictionary = Dictionary.load_from_text(dictionary_path)
    timest = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
    lda_key = f'LDA_model_{timest}_{step}_{step_label}.model'
    lda_model = LdaModel(corpus, id2word=dictionary, **kwargs)
    full_file_path = os.path.join(base_path_lda, lda_key)
    lda_model.save(full_file_path)
    return lda_key

