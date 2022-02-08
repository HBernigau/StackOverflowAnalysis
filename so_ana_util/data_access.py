"""
contains several utilities for accessing data (elastic search and Postgresql)

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from so_ana_doc_worker import schemas as so_ana_worker_schemas
from so_ana_sqlalchemy_models.db_deps import dict_to_es_key

class IteratorFromGenerator:

    def __init__(self,
                 generator,
                 filter_callback = None,
                 postprocess_callback=None,
                 len_func=None,
                 *args,
                 **kwargs):
        """
        Generates an iterator from a generator

        :param generator: an arbitrary generator
        :param filter_callback: output of the generator is generated if filter_callback(output = True) /
                                defaults to x->True
        :param postprocess_callback: output of the generator is modified to postprocess_callback(output) /
                                     defaults to x->x
        :param args: args passed to generator
        :param kwargs: Kwargs passed to generator
        """
        self.generator=generator
        self.filter_callback = filter_callback or (lambda x: True)
        self.postprocess_callback = postprocess_callback or (lambda x: x)
        self.args=args or []
        self.kwargs=kwargs or {}
        self._cust_gen=None
        if len_func is None:
            def fb_len_func():
                cnt = 0
                for item in self:
                    cnt +=1
                return cnt
            len_func = fb_len_func
        self.len_func = len_func


    def __iter__(self):
        def _cust_iter(*args, **kwargs):
            for item in self.generator(*args, **kwargs):
                if self.filter_callback(item):
                    yield self.postprocess_callback(item)
        self._cust_gen = _cust_iter(*self.args, **self.kwargs)
        return self._cust_gen

    def __next__(self):
        return next(self._cust_gen)

    def __len__(self):
        return self.len_func()


def get_txt(base_content, document):
    if base_content == 'all':
        txt = ' '.join([document.question_txt,
                        *document.comment_lst,
                        *[answer.answer_txt for answer in document.answers],
                        *[' '.join(answer.comment_lst) for answer in document.answers]])
    else:
        raise NotImplementedError('t.b.d.')
    return txt


def pg_res_driven_es_iterator(connection,
                              d2es_obj,
                              base_class,
                              step,
                              step_label,
                              ml_tags = None
                              ):
    ml_tags = ml_tags or [0, 1, 2]
    ml_tuple = tuple(ml_tags)
    qu = 'select ord_key from so_ana_management.post_results ' \
         'where step=%(step)s and step_label=%(step_label)s and ml_tag in %(ml_tuple)s'
    cur = connection.execute(qu, {'step': step, 'step_label': step_label, 'ml_tuple': ml_tuple})
    for item in cur:
        key = dict_to_es_key({'step': step, 'step_label': step_label, 'ord_key': item['ord_key']})
        doc = d2es_obj.get(base_class, key)
        yield doc

def get_pg_res_driven_es_iterator_len_func(connection,
                                           step,
                                           step_label,
                                           ml_tags = None):
    ml_tags = ml_tags or [0, 1, 2]
    ml_tuple = tuple(ml_tags)
    def _len_func():
        qu = 'select count(*) as nr from so_ana_management.post_results ' \
             'where step=%(step)s and step_label=%(step_label)s and ml_tag in %(ml_tuple)s'
        res = connection.execute(qu, {'step': step,
                                      'step_label': step_label,
                                      'ml_tuple': ml_tuple
                                      }).fetchone()
        return res['nr']
    return _len_func

def get_doc_iterator(connection,
                     d2es_obj,
                     step_label,
                     format = 'tokens',
                     ml_tags=None
):
    def to_freq_dict(x: so_ana_worker_schemas.BoWData):
        return dict(zip(x.key_tokens, x.values))

    def to_bow_freq_dict(x: so_ana_worker_schemas.BoWData):
        return list(zip(x.keys, x.values))

    def to_token_lst(x: so_ana_worker_schemas.TokenizationData):
        return x.tokenized_content

    transl_dict = {'#1': so_ana_worker_schemas.PostMetaData,
                   '#2': so_ana_worker_schemas.PostRawData,
                   '#3': so_ana_worker_schemas.QuestionInfo,
                   '#4': so_ana_worker_schemas.TokenizationData,
                   '#5': so_ana_worker_schemas.BoWData}

    if format.lower() == 'tokens':
        post_proc_cb = to_freq_dict
        step = '#5'
        base_class = transl_dict[step]
    elif format.lower() == 'keys':
        post_proc_cb = to_bow_freq_dict
        step = '#5'
        base_class = transl_dict[step]
    elif format.lower() == 'unprocessed_tokens':
        post_proc_cb = to_token_lst
        step = '#4'
        base_class = transl_dict[step]
    elif format.lower().startswith('all_'):
        step = format.lower().split('_')[1]
        base_class = transl_dict[step]
        post_proc_cb = None
    else:
        raise NotImplementedError(f'unknown format {format.lower()} - chose "tokens", "keys" or "unprocessed_tokens"!')

    txt_iterator = IteratorFromGenerator(generator = pg_res_driven_es_iterator,
                                         filter_callback = None,
                                         postprocess_callback=post_proc_cb,
                                         len_func=get_pg_res_driven_es_iterator_len_func(   connection=connection,
                                                                                            step=step,
                                                                                            step_label=step_label,
                                                                                            ml_tags=ml_tags),
                                         connection=connection,
                                         d2es_obj=d2es_obj,
                                         base_class=base_class,
                                         step = step,
                                         step_label=step_label,
                                         ml_tags=ml_tags
                                         )
    return txt_iterator


if __name__ == '__main__':

    def sample_generator(start=0, end=10):

        for i in range(start, end):
            yield i

    my_sample_iterator = IteratorFromGenerator( sample_generator,
                                                filter_callback = lambda x: x % 2 == 0,
                                                postprocess_callback=lambda x: 7*x,
                                                start=0,
                                                end=20
                                              )

    for i in my_sample_iterator:
        print(i)
    print()
    print(len(my_sample_iterator))
