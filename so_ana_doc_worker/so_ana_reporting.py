"""
contains utilities for reporting of LDA results

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import sys
import os
from typing import List, Tuple

sys.stderr = open(os.devnull, "w") # hide DeprecationWarnings from moduls import
import pyLDAvis
import pyLDAvis.gensim
from gensim.models.ldamodel import LdaModel
sys.stderr = sys.__stderr__
from sqlalchemy import text
from wordcloud import WordCloud
from collections import Counter
from dataclasses import dataclass
import pandas as pd
import matplotlib.pyplot as plt
import json
import numpy as np
from gensim.corpora import Dictionary
from collections import defaultdict

import so_ana_management.management_utils as so_ana_mu
from so_ana_util.data_access import get_doc_iterator
from sqlalchemy_models.db_deps import prod_db_deps_container, dict_to_es_key
import so_ana_doc_worker.schemas as so_ana_worker_schemas

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

desired_width = 620
pd.set_option('display.width', desired_width)
np.set_printoptions(linewidth=desired_width)
pd.set_option('display.max_columns', 10)


def get_deps(**kwargs):
    return prod_db_deps_container(**kwargs)


@dataclass
class ReportingDataAccess:
    flow_run_id: str

    def load_job_data(self, sqla_session=None):
        job_data = sqla_session.get(so_ana_mu.JobOverview, {'flow_run_id': self.flow_run_id})
        return job_data

    def _get_rel_steps(self, connection):
        qu = 'select step, step_label, prev_step_lbls ' \
             'from so_ana_management.steps_overview ' \
             'where flow_run_id = %(flow_run_id)s ' \
             'and step=\'#8\''
        qu_res = connection.execute(qu, {'flow_run_id': self.flow_run_id}).fetchone()
        step_set = set()
        step_set.add((qu_res['step'], qu_res['step_label']))
        for i, prev_label in enumerate(qu_res['prev_step_lbls']):
            step_set.add((f'#{i+1}', prev_label))
        return step_set

    def load_job_step_data(self, sqla_session):
        conn = sqla_session.connection()
        step_set = self._get_rel_steps(conn)

        res = {}
        for item in step_set:
            data = sqla_session.get(so_ana_mu.JobStepOverview, {'step': item[0], 'step_label': item[1]})
            res[data.step] = data
        return res

    def load_artefacts(self, sqla_session):
        conn = sqla_session.connection()
        step_set = self._get_rel_steps(conn)
        rec_lst = []
        for item in step_set:
            qu = 'select step, step_label, artefact_key, artefact_value ' \
                 'from so_ana_management.artefacts ' \
                 'where step=%(step)s and step_label=%(step_label)s'
            cursor = conn.execute(qu, {'step': item[0], 'step_label': item[1]})
            for row in cursor:
                rec_lst.append({item[0]: item[1] for item in row._mapping.items()})
        serializer = so_ana_mu.get_proj_serializer()
        for item in rec_lst:
            item['artefact_value'] = serializer.deserialize(json.dumps(item['artefact_value']), as_bytes=False)
        return rec_lst

    @classmethod
    def load_all_job_data(cls, connection):
        return pd.read_sql('select * from so_ana_management.job_overview', con=connection)

    def load_all_step_data_for_flow_run_id(connection, flow_run_id):
        qu= 'select * from so_ana_management.steps_overview ' \
            'where flow_run_id=%(flow_run_id)s and step=%(step)s'

        res = []
        res_8 = {key: value
                 for key, value in connection.execute(qu, {'flow_run_id': flow_run_id, 'step': '#8'}).fetchone().items()}
        res.append(res_8)

        qu= 'select * from so_ana_management.steps_overview ' \
            'where step=%(step)s and step_label=%(step_label)s'

        for i, step_label in enumerate(res_8['prev_step_lbls']):
            res_new = {key: value
                       for key, value in connection.execute(qu, {'step': f'#{i+1}', 'step_label': step_label}).fetchone().items()}
            res.append(res_new)
        final = pd.DataFrame.from_records(res)
        final.set_index('step', inplace=True)
        return final

    def show_raw_post(self,
                      connection,
                      d2es,
                      post_ord_key):
        raise NotImplementedError()

    def show_raw_page(self,
                      connection,
                      d2es,
                      post_ord_key):
        raise NotImplementedError()


class WCReports:

    def __init__(self, deps_obj, step, step_label, base_content='all'):
        self.deps = deps_obj
        self.step = step
        self.step_label = step_label
        self.base_content = base_content

    @classmethod
    def _get_wc(cls):
        return WordCloud(background_color="white", width=1920, height=1080)

    @classmethod
    def _save_if_not_null(cls, file_name, wc):
        if file_name is not None:
            wc.to_file(file_name)

    def wc_for_doc(self, ord_key, file_name=None):
        wc = WCReports._get_wc()
        key = dict_to_es_key({'step': self.step, 'step_label': self.step_label, 'ord_key': ord_key})
        doc = self.deps.d2es.get(so_ana_worker_schemas.BoWData, key)
        txt_freq_dict = dict(zip(doc.key_tokens, doc.values))
        wc.generate_from_frequencies(txt_freq_dict)

        WCReports._save_if_not_null(file_name, wc)
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")

        return plt

    def wc_for_corpus(self, file_name=None, ml_tags=None):
        wc = WCReports._get_wc()
        txt_iterator = get_doc_iterator(connection=self.deps.conn,
                                        d2es_obj=self.deps.d2es,
                                        step_label=self.step_label,
                                        ml_tags = ml_tags,
                                        )
        counts_all = Counter()
        for txt_freq_dict in txt_iterator:
            counts_all.update(txt_freq_dict)
        wc.generate_from_frequencies(counts_all)

        WCReports._save_if_not_null(file_name, wc)
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        return plt

    @classmethod
    def wc_for_topics_of_topic_model(cls, lda_model_obj, topic_nr, file_name=None, topn=100):
        wc = cls._get_wc()

        counts_all = {item[0]: item[1] for item in lda_model_obj.show_topic(topicid=topic_nr, topn=topn)}
        wc.generate_from_frequencies(counts_all)

        cls._save_if_not_null(file_name, wc)
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        return plt


def get_LDAvis_obj(deps_obj, step_label, lda_model_obj, gensim_dictionary):
    doc_iterator = get_doc_iterator(connection=deps_obj.conn,
                                    d2es_obj=deps_obj.d2es,
                                    step_label=step_label,
                                    format='keys')
    return pyLDAvis.gensim.prepare(lda_model_obj,
                                   doc_iterator,
                                   gensim_dictionary
                                   )


def LDA_from_artefact(lda_model_artefact_obj):
    lda_model_path = os.path.join(lda_model_artefact_obj['artefact_value']['base_path'],
                                  lda_model_artefact_obj['artefact_value']['lda_key'])
    return LdaModel.load(lda_model_path)


def dictionary_from_artefact(dict_artefact_obj):
    dict_path = os.path.join(dict_artefact_obj['artefact_value']['storage_path'],
                             dict_artefact_obj['artefact_value']['keys_dict']['dict_key'])
    return Dictionary.load_from_text(dict_path)


def generate_lda_vis(dict_artefact_obj,
                     lda_model_artefact_obj,
                     deps_obj,
                     step_label,
                     target_file_html=None,
                     target_file_json=None):

    lda_model = LDA_from_artefact(lda_model_artefact_obj)
    dictionary = dictionary_from_artefact(dict_artefact_obj)
    LDAvis_prepared = get_LDAvis_obj(deps_obj=deps_obj,
                                     step_label=step_label,
                                     lda_model_obj=lda_model,
                                     gensim_dictionary=dictionary)

    if target_file_html is not None:
        pyLDAvis.save_html(LDAvis_prepared, target_file_html)
    if target_file_json is not None:
        pyLDAvis.save_json(LDAvis_prepared, target_file_json)
    return LDAvis_prepared


def set_topic_values(lda_model_artefact_obj,
                     step_5_label: str
                     ):
    lda_model = LDA_from_artefact(lda_model_artefact_obj)


@dataclass
class ExtBowData:
    ord_key: int
    post_id: int
    for_step: str
    for_step_label: str
    bow_data: List[Tuple[int, int]]


@dataclass
class TopicResult:
    ord_key: int
    post_id: int
    for_step: str
    for_step_label: str
    topic_id: int
    topic_weight: float


def pp_callback(x):
    return ExtBowData(for_step=x.step,
                      for_step_label=x.step_label,
                      ord_key =x.ord_key,
                      post_id=x.post_id,
                      bow_data=list(zip(x.keys, x.values))
                      )


def topic_iterator(deps, for_step_label, lda_model_artefact):
    doc_generator = get_doc_iterator(connection=deps.conn,
                                     d2es_obj=deps.d2es,
                                     step_label=for_step_label,
                                     format='keys',
                                     ml_tags=None
                                     )

    doc_generator.postprocess_callback=pp_callback
    lda_model=LDA_from_artefact(lda_model_artefact)
    for doc in doc_generator:
        for top in lda_model.get_document_topics(doc.bow_data, minimum_probability=0.0):
            yield TopicResult(ord_key=doc.ord_key,
                              post_id=doc.post_id,
                              for_step=doc.for_step,
                              for_step_label=doc.for_step_label,
                              topic_id=int(top[0]),
                              topic_weight=float(top[1])
                              )


if __name__ == '__main__':
    deps = get_deps()
    conn = deps.conn
    session = deps.session
    d2es = deps.d2es

    all_jobs = ReportingDataAccess.load_all_job_data(conn)

    flow_run_id = all_jobs.sort_values('started_at_timest', ascending=False).iloc[0, :]['flow_run_id']
    rep_data_access = ReportingDataAccess(flow_run_id)
    step_result_dict = rep_data_access.load_job_step_data(sqla_session=session)
    artefacts = rep_data_access.load_artefacts(session)
    print(artefacts)

    wc_report_obj = WCReports(deps_obj=deps,
                              step='#3',
                              step_label=step_result_dict['#3'].step_label)

    lda_model_artefact = [item for item in artefacts
                          if item['step'] == '#6' and item['artefact_key'] == 'LDA_model_data'][0]
    dict_artefact = [item for item in artefacts
                     if item['step'] == '#5' and item['artefact_key'] == 'dictionary'][0]

    generate_lda_vis(lda_model_artefact_obj=lda_model_artefact,
                     dict_artefact_obj=dict_artefact,
                     deps_obj=deps,
                     step_label=step_result_dict['#5'].step_label,
                     target_file_html='dummy.html',
                     target_file_json='dummy.json')

    lda_model = LDA_from_artefact(lda_model_artefact)
    dictionary = dictionary_from_artefact(dict_artefact)

    print(lda_model.get_topics())
    print(lda_model.print_topic(0), type(lda_model.print_topic(0)))
    print(lda_model.print_topics(num_topics=20, num_words=10))
    print(lda_model.show_topics(num_topics=10, num_words=10, log=False, formatted=False))
    print()
    for topic in range(10):
        print(lda_model.show_topic(topicid=topic, topn=30), type(lda_model.show_topic(topicid=0, topn=10)))

    print()
    print('LDA topics...')
    topic_portion_sum_dict = defaultdict(int)
    doc_iter = get_doc_iterator(connection=deps.conn,
                                d2es_obj=deps.d2es,
                                step_label=step_result_dict['#5'].step_label,
                                format ='keys',
                                ml_tags=None)
    total = len(doc_iter)
    for i, doc in enumerate(doc_iter):
        for topic_id, fraction in lda_model[doc]:
            topic_portion_sum_dict[topic_id] += fraction/total
    print(topic_portion_sum_dict)

    #for topic in range(5):
    #    dummy = WCReports.wc_for_topics_of_topic_model(lda_model_obj=lda_model,
    #                                                   topic_nr=topic,
    #                                                   file_name=f'dummy_topic_{topic}.png',
    #                                                   topn=100)

    # to do: coherence measures: http://svn.aksw.org/papers/2015/WSDM_Topic_Evaluation/public.pdf
    #           and https://rare-technologies.com/what-is-topic-coherence/
    #           https: // radimrehurek.com / gensim / auto_examples / tutorials / run_lda.html
    #        trigrams, filter extremes (compare https://radimrehurek.com/gensim/auto_examples/tutorials/run_lda.html)
    #        https://radimrehurek.com/gensim/models/ldamodel.html
    #        play with hyper parameters: alpha, num_topics, ierations=20
    #        article: https://www.di.ens.fr/~fbach/mdhnips2010.pdf
    #        check if "diff" is usefull (https://radimrehurek.com/gensim/models/ldamodel.html)
    #        EM in LDA

    #        get_document_topics(bow, minimum_probability=None, minimum_phi_value=None, per_word_topics=False)
    #        get_term_topics(word_id, minimum_probability=None)
    #        get_topic_terms(topicid, topn=10)
    #        log_perplexity(chunk, total_docs=None)
