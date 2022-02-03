"""
contains utilities for processing the post after extraction

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from bs4 import BeautifulSoup
from datetime import datetime
from dataclasses import dataclass
from typing import List
from nltk.stem.wordnet import WordNetLemmatizer
from gensim.parsing.preprocessing import STOPWORDS
from gensim.corpora import Dictionary
import os
from langdetect import detect_langs
import re
from itertools import count
from gensim.models.phrases import Phrases, Phraser
import copy

from so_ana_util.data_access import get_txt, get_doc_iterator, IteratorFromGenerator
from sqlalchemy_models.db_deps import prod_db_deps_container, dict_to_es_key
from so_ana_doc_worker.schemas import ExtractResult, PostRawData, ExtractPostFullResult, QuestionInfo, Answer, \
    TokenizationResult, TokenizationData, FullTokenizationResult, FullBoWResult, BoWResult, BoWData

# own exceptions


class MultipleQuestionsFound(ValueError):
    pass


class MultipleAnswersSectionsFound(ValueError):
    pass


def separate_links(bs_instance, cnt):
    link_dict = {}
    for link in bs_instance.find_all('a'):
        key = f'link_id_{next(cnt)}'
        link['id'] = key
        link_dict[key] = (link.get('href', '#none#'), link.string)
        link.clear()
    content = bs_instance.get_text().strip()
    link_template = '<a id="@id@" href="@href@">\n@content@\n</a>'
    links = '\n'.join([link_template.replace('@id@', key).replace('@content@', value[1] or '').replace('@href@',
                                                                                                       value[0] or '')
                       for key, value in link_dict.items()])
    return content, links


@dataclass
class Comments:
    lst_txt: List[str]
    lst_raw: List[str]
    user_url_lst: List[str]
    date_lst: List[datetime]
    comm_links: List[str]


def extract_comment_lists(comments_base, cnt) -> Comments:
    lst_txt = []
    lst_raw = []
    user_url_lst = []
    date_lst = []
    link_lst = []
    for comment_item in comments_base.find_all('li', []):
        if 'comment' in comment_item.get('class', []):
            comment_date = None
            user_url = None
            comment_raw = str(comment_item)
            comm_txt = None
            comm_links = None
            for link in comment_item.find_all('a'):
                if 'comment-user' in link.get('class', []):
                    try:
                        user_url = link['href']
                    except KeyError:
                        user_url = None
                    link.string = ''
            for span in comment_item.find_all('span'):
                if 'relativetime-clean' in span.get('class', []):
                    try:
                        comment_date_str = span['title'].split(',')[0]
                        comment_date = datetime.strptime(comment_date_str.replace('Z', '+00:00'), '%Y-%m-%d %H:%M:%S%z')
                        span.string = ''
                    except:
                        comment_date = None
                elif 'comment-copy' in span.get('class', []):
                    comm_txt, comm_links = separate_links(span, cnt=cnt)

            lst_raw.append(comment_raw)
            lst_txt.append(comm_txt)
            user_url_lst.append(user_url)
            link_lst.append(comm_links)
            date_lst.append(comment_date)
    return Comments(lst_txt=lst_txt,
                    lst_raw=lst_raw,
                    user_url_lst=user_url_lst,
                    date_lst=date_lst,
                    comm_links=link_lst)


def parse_raw_file(raw_data,
                   for_step,
                   for_step_label,
                   post_id,
                   ord_key,
                   ml_tag,
                   modus):

    try:
        soup = BeautifulSoup(raw_data, 'html.parser')

        code_dict = {}
        answer_list = []

        for i, code in enumerate(soup.find_all('code')):
            key = f'code_{i}'
            code['id'] = key
            code_dict[key] = code.string
            code.clear()

        c_qu = 0
        c_ans = 0

        link_cnt = count(start=0, step=1)
        question_comments = None
        question = None
        question_raw = None
        qu_links = []

        for all_divs in soup.find_all('div'):
            if all_divs.get('id', None) == 'question':
                if c_qu > 0:
                    raise MultipleQuestionsFound(f'Multiple questions found in post {post_id}')
                for qu_subdiv in all_divs.find_all('div'):
                    if 'postcell' in qu_subdiv.get('class', []):
                        for j, post_cell_sub_div in enumerate(qu_subdiv.find_all('div')):
                            if 's_prose' in post_cell_sub_div.get('class', []) \
                                    or 'js-post-body' in post_cell_sub_div.get('class', []):
                                question_raw = str(post_cell_sub_div)
                                question, qu_links = separate_links(bs_instance=post_cell_sub_div,
                                                                    cnt=link_cnt)
                    elif 'comments' in qu_subdiv.get('class', []):
                        question_comments = extract_comment_lists(qu_subdiv, cnt=link_cnt)
                c_qu += 1
            elif all_divs.get('id', None) == 'answers':
                if c_ans > 0:
                    raise MultipleAnswersSectionsFound(f'Multiple questions found in post {post_id}')
                for answer_div in all_divs.find_all('div'):
                    if 'answer' in answer_div.get('class', []):
                        is_accepted_answer = 'accepted-answer' in answer_div.get('class', [])
                        answer_raw = None
                        answer_txt = None
                        answer_user_url = None
                        answer_user_name = None
                        answer_date = None
                        answer_votes = None
                        answer_comments = None
                        answer_links = []
                        for answer_sub_div in answer_div.find_all('div'):
                            if 's-prose' in answer_sub_div.get('class', []) \
                                    or 'js-post-body' in answer_sub_div.get('class', []):
                                answer_raw = str(answer_sub_div)
                                answer_txt, answer_links = separate_links(bs_instance=answer_sub_div,
                                                                          cnt=link_cnt)
                            elif 'js-vote-count' in answer_sub_div.get('class', []):
                                answer_votes = int(answer_sub_div['data-value'])
                            elif 'comments' in answer_sub_div.get('class', []):
                                answer_comments = extract_comment_lists(answer_sub_div, cnt=link_cnt)

                            elif 'mt24' in answer_sub_div.get('class', []):
                                for meta_sub_div in answer_sub_div.find_all('div'):
                                    if 'user-details' in meta_sub_div.get('class', []):
                                        for link in meta_sub_div.find_all('a'):
                                            try:
                                                answer_user_url = link['href']
                                                if answer_user_url.startswith(r'/users'):
                                                    answer_user_name = link.get_text()
                                                    break
                                                else:
                                                    answer_user_url = None
                                            except KeyError:
                                                answer_user_url = None
                                    elif 'user-action-time' in meta_sub_div.get('class', []):
                                        for span in meta_sub_div.find_all('span'):
                                            try:
                                                answer_date_str = span['title']
                                                answer_date = datetime.strptime(answer_date_str.replace('Z', '+00:00'),
                                                                                '%Y-%m-%d %H:%M:%S%z')
                                            except:
                                                answer_date = None
                        answer_list.append(Answer(answer_raw=answer_raw,
                                                  answer_txt=answer_txt,
                                                  answer_links=answer_links,
                                                  user_url=answer_user_url,
                                                  user_name=answer_user_name,
                                                  answer_date=answer_date,
                                                  answer_vote=answer_votes,
                                                  is_accepted_answer=is_accepted_answer,
                                                  comment_lst_raw=getattr(answer_comments, 'lst_raw', []),
                                                  comment_lst=getattr(answer_comments, 'lst_txt', []),
                                                  comment_user_url_lst=getattr(answer_comments, 'user_url_lst', []),
                                                  comment_date_lst=getattr(answer_comments, 'date_lst', []),
                                                  comment_link_lst=getattr(answer_comments, 'comm_links', []),
                                                  modus=modus
                                                  )
                                           )
                c_ans += 1

        code_template = '<code id=@id@>\n@content@\n</code>'
        code_pieces = '\n'.join([code_template.replace('@id@', key).replace('@content@', value or '')
                                 for key, value in code_dict.items()]
                                )

        comment_count = len(getattr(question_comments, 'lst_raw', []))
        comment_count_total = comment_count + sum([len(getattr(item, 'comment_lst', [])) for item in answer_list])

        # language detection
        full_base_txt = ' '.join([question,
                                  *getattr(question_comments, 'lst_txt', []),
                                  *[answer.answer_txt for answer in answer_list],
                                  *[' '.join(answer.comment_lst) for answer in answer_list]
                                  ]
                                 )
        languages = detect_langs(full_base_txt)
        lang_lst = [item.lang for item in languages]
        lang_prob_lst = [item.prob for item in languages]
        max_lang_idx = lang_prob_lst.index(max(lang_prob_lst))
        lang = lang_lst[max_lang_idx]
        lang_prob = lang_prob_lst[max_lang_idx]

        parsing_result = QuestionInfo(step=for_step,
                                      step_label=for_step_label,
                                      post_id=post_id,
                                      ord_key=ord_key,
                                      question_raw=question_raw,
                                      question_txt=question,
                                      question_links=qu_links,
                                      code_pieces=code_pieces,
                                      comment_lst_raw=getattr(question_comments, 'lst_raw', []),
                                      comment_lst=getattr(question_comments, 'lst_txt', []),
                                      comment_user_url_lst=getattr(question_comments, 'user_url_lst', []),
                                      comment_date_lst=getattr(question_comments, 'date_lst', []),
                                      comment_link_lst=getattr(question_comments, 'comm_links', []),
                                      answers=answer_list,
                                      answer_count=len(answer_list),
                                      comment_count=comment_count,
                                      total_comment_count=comment_count_total,
                                      modus=modus,
                                      lang=lang,
                                      lang_prob=lang_prob,
                                      lang_lst=lang_lst,
                                      lang_prob_lst=lang_prob_lst,
                                      ml_tag=ml_tag
                                      )

        extr_res = ExtractResult(step=for_step,
                                 step_label=for_step_label,
                                 ord_key=ord_key,
                                 post_id=post_id,
                                 exit_code=0,
                                 exit_message='',
                                 ml_tag=ml_tag
                                 )
    except Exception as exc:
        extr_res = ExtractResult(step=for_step,
                                 step_label=for_step_label,
                                 ord_key=ord_key,
                                 post_id=post_id,
                                 exit_code=1,
                                 exit_message=f'{exc}',
                                 ml_tag=ml_tag
                                 )

        parsing_result = None

    return ExtractPostFullResult(extract_result=extr_res,
                                 extract_data=parsing_result)


def tokenize(document: QuestionInfo,
             for_step: str,
             for_step_label: str,
             post_id: int,
             ord_key: int,
             ml_tag: int,
             base_content='all',
             to_lower_case=True,
             use_lemmatizer='wordnet',
             filter_gensim_stopwords=True,
             own_stopword_lst=None,
             modus='test'):
    own_stopword_lst = own_stopword_lst or []
    txt = get_txt(base_content, document)
    if to_lower_case:
        txt = txt.lower()

    try:
        text_tokenized = [item for item in re.split(r'[^a-z]', txt) if len(item) > 1]
        if use_lemmatizer.lower() == 'wordnet':
            lemmatizer = WordNetLemmatizer()
            text_tokenized = [lemmatizer.lemmatize(token) for token in text_tokenized]
        elif use_lemmatizer.lower() == 'none':
            pass
        else:
            raise NotImplementedError('t.b.d.')

        if filter_gensim_stopwords is True:
            text_tokenized = [item for item in text_tokenized if item not in STOPWORDS]
        text_tokenized = [item for item in text_tokenized if item not in own_stopword_lst]

        data = TokenizationData(step=for_step,
                                step_label=for_step_label,
                                post_id=post_id,
                                ord_key=ord_key,
                                modus=modus,
                                tokenized_content=text_tokenized,
                                ml_tag=ml_tag
                                )
        res = TokenizationResult(step=for_step,
                                 step_label=for_step_label,
                                 exit_code=0,
                                 exit_message='',
                                 ord_key=ord_key,
                                 post_id=post_id,
                                 ml_tag=ml_tag)
    except Exception as exc:
        data = None
        res = TokenizationResult(step=for_step,
                                 step_label=for_step_label,
                                 exit_code=1,
                                 exit_message=f'{exc}',
                                 ord_key=ord_key,
                                 post_id=post_id,
                                 ml_tag=ml_tag)

    return FullTokenizationResult(tok_result=res,
                                  tok_data=data)


def build_phrases(txt_iter,
                  min_count: int = 20,
                  threshold: float = 0.05,
                  scoring: str = 'npmi',
                  max_vocab_size: int = 1000000
                  ):

    phrases = Phrases(sentences=txt_iter,
                      min_count=min_count,
                      threshold=threshold,
                      scoring=scoring,
                      max_vocab_size=max_vocab_size
                      )

    return Phraser(phrases)


def ext_tokens_with_phrases(tokens, *args):
    res = tokens
    for i, phrases in enumerate(args):
        res += [item for item in phrases[tokens] if item.count('_') == i+1]
    return res

def get_extended_generator(connection,
                           d2es_obj,
                           step_label,
                           ml_tags,
                           phrases_lst):
    def pp_cb(x):
        return ext_tokens_with_phrases(x.tokenized_content,
                                       *phrases_lst)

    ext_doc_generator = get_doc_iterator(connection=connection,
                                         d2es_obj=d2es_obj,
                                         step_label=step_label,
                                         format='unprocessed_tokens',
                                         ml_tags=ml_tags)
    ext_doc_generator.postprocess_callback = pp_cb
    return ext_doc_generator

def generate_dictionary(storage_path,
                        doc_iterator,
                        ext_doc_generator_factory,
                        step,
                        step_label,
                        step_label_4,
                        deps,
                        nr_grams: int =1,
                        filter_no_below=1,
                        filter_no_above=0.95,
                        ):

    phrases_lst = []

    for i in range(nr_grams-1):
        phrases = build_phrases(txt_iter=doc_iterator)
        phrases_lst.append(phrases)
        cb_old = doc_iterator.postprocess_callback
        def new_cb(x):
            return phrases[cb_old(x)]
        doc_iterator.postprocess_callback = new_cb
    ext_doc_generator = ext_doc_generator_factory(connection=deps.conn,
                                                  d2es_obj=deps.d2es,
                                                  step_label=step_label_4,
                                                  ml_tags=[0],
                                                  phrases_lst=phrases_lst
                                                  )

    dictionary = Dictionary(ext_doc_generator)
    dictionary.filter_extremes(no_below=filter_no_below, no_above=filter_no_above)
    timest = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
    dictionary_key = f'dictdata_{timest}_{step}_{step_label}.txt'
    storage_file_path = os.path.join(storage_path, dictionary_key)
    dictionary.save_as_text(storage_file_path)
    ret_lst = []
    for i, phrase in enumerate(phrases_lst):
        phrases_key = f'phrases_{i+2}_{timest}_{step}_{step_label}.pkl'
        full_phr_path = os.path.join(storage_path, phrases_key)
        phrase.save(full_phr_path)
        ret_lst.append(phrases_key)
    return dictionary_key, ret_lst


def load_phrase(base_path, phrase_lst):
    res = [Phraser.load(os.path.join(base_path, item)) for item in phrase_lst]
    return res



def doc_to_bow(for_step: str,
               for_step_label: str,
               post_id: int,
               ord_key: int,
               storage_path: str,
               file_key: str,
               document: List[str],
               ml_tag: int,
               modus: str):
    try:
        bow_data = BoWData.from_dict_key_and_document(step=for_step,
                                                      step_label=for_step_label,
                                                      post_id=post_id,
                                                      ord_key=ord_key,
                                                      base_path=storage_path,
                                                      file_key=file_key,
                                                      document=document,
                                                      ml_tag=ml_tag,
                                                      modus=modus)

        bow_res = BoWResult(step=for_step,
                            step_label=for_step_label,
                            ord_key=ord_key,
                            exit_code=0,
                            exit_message='',
                            post_id=post_id,
                            ml_tag=ml_tag)

    except Exception as exc:
        bow_res = BoWResult(step=for_step,
                            step_label=for_step_label,
                            ord_key=ord_key,
                            exit_code=1,
                            exit_message=f'{exc}',
                            post_id=post_id,
                            ml_tag=ml_tag)
        bow_data = None

    return FullBoWResult(bow_result=bow_res,
                         bow_data=bow_data)


if __name__ == '__main__':
    batch_id = 0
    deps = prod_db_deps_container()

    qu = 'select * from so_ana_management.post_results where step=\'#2\' ' \
         'and result_class_name=\'DownloadPostResult\' ' \
         'and exit_code=0 ' \
         'LIMIT 5'

    lst = []

    result_cursor = deps.conn.execute(qu)

    modus = 'test'

    """
    doc_iterator = get_doc_iterator(connection=deps.conn,
                                    d2es_obj=deps.d2es,
                                    step_label=step_label,
                                    format='unprocessed_tokens',
                                    ml_tags=[0])
                                    
    ext_doc_generator = get_extended_generator(connection=deps.conn,
                                               d2es_obj=deps.d2es,
                                               step_label=step_label,
                                               ml_tags=[0],
                                               phrases_lst=phrases_lst)
    """

    for row in result_cursor:
        post_id = row['post_id']
        ord_key = row['ord_key']
        ml_tag = row['ml_tag']
        step = row['step']
        step_label = row['step_label']
        deps.script_logger.info(f'Start extracting information from post ord_key={ord_key} (post_id={post_id})')
        key = dict_to_es_key({'step': step,
                              'step_label': step_label,
                              'ord_key': ord_key
                              }
                             )

        raw_data = deps.d2es.get(PostRawData, key).content_raw
        transformed_data = parse_raw_file(raw_data=raw_data,
                                          for_step='#3',
                                          for_step_label='dummy',
                                          post_id=post_id,
                                          ord_key=ord_key,
                                          ml_tag=ml_tag,
                                          modus=modus
                                          )

        key = dict_to_es_key({'step': '#3',
                              'step_label': 'dummy',
                              'ord_key': ord_key
                              })
        deps.d2es(id=key, data=transformed_data.extract_data)

        deps.script_logger.info(transformed_data.extract_result)
        tokenized_data = tokenize(document=transformed_data.extract_data,
                                  for_step='#4',
                                  for_step_label='dummy',
                                  post_id=post_id,
                                  ord_key=ord_key,
                                  base_content='all',
                                  to_lower_case=True,
                                  use_lemmatizer='wordnet',
                                  filter_gensim_stopwords=True,
                                  own_stopword_lst=[],
                                  ml_tag=ml_tag,
                                  modus=modus
                                  )

        key = dict_to_es_key({'step': '4',
                              'step_label': 'dummy',
                              'ord_key': ord_key
                              })

        deps.script_logger.info(tokenized_data)
        lst.append(tokenized_data.tok_data)
    ext_lst = [copy.deepcopy(item) for item in lst]

    def dummy_ext_fact(phrases_lst, **kwargs):
        global ext_lst
        for item in ext_lst:
            item.tokenized_content = ext_tokens_with_phrases(item.tokenized_content, *phrases_lst)

        def ext_dummy_generator():
            _lst = [doc.tokenized_content for doc in ext_lst]
            for item in _lst:
                yield item

        return IteratorFromGenerator(generator=ext_dummy_generator)

    def dummy_generator():
        data = [doc.tokenized_content for doc in lst]
        for item in data:
            yield item

    dummy_doc_iterator = IteratorFromGenerator(generator=dummy_generator)


    storage_path = r'C:\Users\d91109\Documents\git\MBA\python\data\dictionaries\dummy'
    rel_dictionary_key, phrases_lst = generate_dictionary(storage_path=storage_path,
                                                          step='#5',
                                                          step_label='something',
                                                          step_label_4='something_step_4',
                                                          deps=deps,
                                                          doc_iterator=dummy_doc_iterator,
                                                          ext_doc_generator_factory=dummy_ext_fact,
                                                          nr_grams=2,
                                                          filter_no_below=1,
                                                          filter_no_above=1.0
                                                          )

    for doc in ext_lst:
        bow = doc_to_bow(for_step='#6',
                         for_step_label='dummy',
                         post_id=doc.post_id,
                         ord_key=doc.ord_key,
                         storage_path=storage_path,
                         file_key=rel_dictionary_key,
                         document=doc.tokenized_content,
                         ml_tag=doc.ml_tag,
                         modus=modus
                         )

        key = dict_to_es_key({'step': '#6',
                              'step_label': 'dummy',
                              'ord_key': doc.ord_key
                              })
        deps.d2es(id=key, data=bow.bow_data)

        print(bow)
        print(bow.bow_data.BoW)
