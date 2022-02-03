"""
contains utilities for extraction of posts

.. deprecated::

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import so_ana_management.management_utils as so_ana_mu
import os

flow_registry = {}
flow_part = 'new_reporting_2021_12_28_v005'
DATA_ROOT_PATH = r'C:\Users\d91109\Documents\work\git\MBA\python\data'


flow_registry['ddd_std']=\
    so_ana_mu.FlowOptions(description='Flows for domain-driven-design on stack-overflow',
                          stack_exchange_type='stackoverflow',
                          topic='domain-driven-design',
                          download_opts=so_ana_mu.DownloadOptions(opts_label=f'dwnl_ddd_{flow_part}',
                                                                  opts_description='download of data at 2021-12-28',
                                                                  download_rate_delay=2.0,
                                                                  error_retry_delay=400.0,
                                                                  batch_count=1,
                                                                  user_agent='Software Engineering Research@University of St.Gallen',
                                                                  from_email='Holger.Bernigau@gmx.de'
                                                                 ),
                          pre_proc_opts=so_ana_mu.TokenizationOptions(opts_label=f'tok_ddd_{flow_part}',
                                                                      opts_description='standard implementation of stemming',
                                                                      base_content='all',
                                                                      to_lower_case=True,
                                                                      use_lemmatizer='wordnet',
                                                                      filter_gensim_stopwords=True,
                                                                      own_stopword_lst=[]
                                                                     ),
                          vect_opts=so_ana_mu.VectorizationOptions(opts_label=f'vect_ddd_{flow_part}',
                                                                   opts_description='standard vectorization',
                                                                   storage_path=os.path.join(DATA_ROOT_PATH,
                                                                                             r'prod\dict'),
                                                                   filter_no_below=1,
                                                                   filter_no_above=1.0,
                                                                   nr_grams=3
                                                                   ),
                          ml_opts=so_ana_mu.MLOptions(opts_label=f'ml_opts_ddd_{flow_part}',
                                                      opts_description='standard implementation of ml model integration',
                                                      test_fraction=0.15,
                                                      val_fraction=0.15,
                                                      storage_path=os.path.join(DATA_ROOT_PATH,
                                                                                  r'prod\ML'),
                                                      num_topics=10,
                                                      nr_passes=50),
                          rep_opts=so_ana_mu.ReportingOptions(opts_label=f'rep_ddd_{flow_part}',
                                                              opts_description='LDA vis and word cloud',
                                                              wc_base_path=os.path.join(DATA_ROOT_PATH,
                                                                                        r'prod\reports'),
                                                              LDAvis_base_path=os.path.join(DATA_ROOT_PATH,
                                                                                            r'prod\reports')
                                                             ),
                          preproc_batch_count=10,
                          use_step=so_ana_mu.StepDescr(step='#6',
                                                       label='ml_opts_ddd_new_reporting_2021_12_28')
                         )

flow_registry['adm_first']=\
    so_ana_mu.FlowOptions(  description='Flows for anemic domain models (for testing and demos (only about 68 entries)',
                            stack_exchange_type='stackoverflow',
                            topic='anemic-domain-model',
                            download_opts=so_ana_mu.DownloadOptions(opts_label=f'dwnl_adm_{flow_part}',
                                                                    opts_description='download of data at 2021-12-28 (for testing)',
                                                                    download_rate_delay=2.0,
                                                                    error_retry_delay=400.0,
                                                                    batch_count=1,
                                                                    user_agent='Software Engineering Research@University of St.Gallen',
                                                                    from_email='Holger.Bernigau@gmx.de'
                                                                    ),
                            pre_proc_opts=so_ana_mu.TokenizationOptions(opts_label=f'tok_adm_{flow_part}',
                                                                        opts_description='standard implementation of stemming',
                                                                        base_content='all',
                                                                        to_lower_case=True,
                                                                        use_lemmatizer='wordnet',
                                                                        filter_gensim_stopwords=True,
                                                                        own_stopword_lst=[]
                                                                        ),
                            vect_opts=so_ana_mu.VectorizationOptions(opts_label=f'vect_adm_{flow_part}',
                                                                     opts_description='dummy implementation of vectorization',
                                                                     storage_path=os.path.join(DATA_ROOT_PATH,
                                                                                               r'prod\dict'),
                                                                     filter_no_below=1,
                                                                     filter_no_above=1.0,
                                                                     nr_grams=3
                                                                    ),
                            ml_opts=so_ana_mu.MLOptions(opts_label=f'ml_opts_adm_{flow_part}',
                                                        opts_description='standard implementation of ml model integration',
                                                        test_fraction=0.15,
                                                        val_fraction=0.15,
                                                        storage_path=os.path.join(DATA_ROOT_PATH,
                                                                                  r'prod\ML'),
                                                        num_topics=5,
                                                        nr_passes=50),
                            rep_opts=so_ana_mu.ReportingOptions(opts_label=f'rep_adm_{flow_part}',
                                                                opts_description='LDA vis and word cloud',
                                                                wc_base_path=os.path.join(DATA_ROOT_PATH,
                                                                                          r'prod\reports'),
                                                                LDAvis_base_path=os.path.join(DATA_ROOT_PATH,
                                                                                              r'prod\reports')
                                                                ),
                            preproc_batch_count=10,
                            use_step=so_ana_mu.StepDescr(step='#6',
                                                         label='ml_opts_adm_new_reporting_2021_12_28')
                        )

flow_registry['microservices_std']=\
    so_ana_mu.FlowOptions(description='Flows for microservices on stack-overflow',
                          stack_exchange_type='stackoverflow',
                          topic='microservices',
                          download_opts=so_ana_mu.DownloadOptions(opts_label=f'dwnl_micro_{flow_part}',
                                                                  opts_description='download of data at 2021-12-28',
                                                                  download_rate_delay=2.0,
                                                                  error_retry_delay=400.0,
                                                                  batch_count=1,
                                                                  user_agent='Software Engineering Research@University of St.Gallen',
                                                                  from_email='Holger.Bernigau@gmx.de'
                                                                 ),
                          pre_proc_opts=so_ana_mu.TokenizationOptions(opts_label=f'tok_micro_{flow_part}',
                                                                      opts_description='standard implementation of stemming',
                                                                      base_content='all',
                                                                      to_lower_case=True,
                                                                      use_lemmatizer='wordnet',
                                                                      filter_gensim_stopwords=True,
                                                                      own_stopword_lst=[]
                                                                     ),
                          vect_opts=so_ana_mu.VectorizationOptions(opts_label=f'vect_micro_{flow_part}',
                                                                   opts_description='standard vectorization',
                                                                   storage_path=os.path.join(DATA_ROOT_PATH,
                                                                                             r'prod\dict'),
                                                                   filter_no_below=1,
                                                                   filter_no_above=1.0,
                                                                   nr_grams=3
                                                                  ),
                          ml_opts=so_ana_mu.MLOptions(opts_label=f'ml_opts_micro_{flow_part}',
                                                      opts_description='standard implementation of ml model integration.',
                                                      test_fraction=0.15,
                                                      val_fraction=0.15,
                                                      storage_path=os.path.join(DATA_ROOT_PATH,
                                                                                r'prod\ML'),
                                                      num_topics=10,
                                                      nr_passes=50
                                                     ),
                          rep_opts=so_ana_mu.ReportingOptions(opts_label=f'rep_micro_{flow_part}',
                                                              opts_description='LDA vis and word cloud',
                                                              wc_base_path=os.path.join(DATA_ROOT_PATH,
                                                                                        r'prod\reports'),
                                                              LDAvis_base_path=os.path.join(DATA_ROOT_PATH,
                                                                                            r'prod\reports')
                                                             ),
                          preproc_batch_count=10,
                          use_step=so_ana_mu.StepDescr(step='#6',
                                                       label='ml_opts_micro_new_reporting_2021_12_28_v002')
                         )


if __name__ == '__main__':
    for key, value in flow_registry:
        print(f'key="{key}"')
        print('-------------------------------------------------------------------------------------------')
        print(f'value="{value}"')
        print('-------------------------------------------------------------------------------------------')
        print()
        print()



