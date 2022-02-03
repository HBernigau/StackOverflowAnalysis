"""
contains utilities for extraction of posts

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import so_ana_doc_worker.extr_post_deps as extr_post_deps
from datetime import datetime
from bs4 import BeautifulSoup
from so_ana_doc_worker.schemas import PostMetaData, PageRawData, ExtractResult, \
    DownloadPostResult, DownloadPageResult,  PostRawData, WorkerSummaryReport, \
    DownloadPageFullResult, DownloadPostFullResult, ExtractFullResult
from sqlalchemy_models.db_deps import prod_db_deps_container
import uuid
import time
import itertools
from numpy.random import choice

def extract_nr_pages(logger, downloader, topic):
    while True:
        data = downloader.metadata_by_topic_and_page(topic , 1)
        if data.code == 0:
            break
        else:
            logger.error(f'Request-Error: "{data.err_msg}", cirquit-closed: "{data.circuit_closed}" waiting for 2 seconds...')
            time.sleep(2.0)

    soup = BeautifulSoup(data.content, 'html.parser')
    max_nr = -1
    for item in soup.find_all('a'):
        if 's-pagination--item' in item.get('class', []) and 'go to page' in item.get('title', '').lower():
            try:
                new_page_nr = int(item.get_text())
            except:
                new_page_nr = -1
            max_nr = max(max_nr, new_page_nr)
    return max_nr



def download_page(  downloader,
                    topic,
                    logger,
                    step,
                    step_label,
                    ord_key,
                    modus):
    page_number = ord_key + 1
    while True:
        data = downloader.metadata_by_topic_and_page(topic,page_number)
        if data.code == 0:
            break
        else:
            logger.info(f'Request-Error: "{data.err_msg}", cirquit-closed: "{data.circuit_closed}" waiting for 2 seconds...')
            time.sleep(2.0)
    raw_page_content = None
    try:
        raw_page_content = PageRawData(step=step,
                                       step_label=step_label,
                                       ord_key=ord_key,
                                       page_nr = page_number,
                                       request_code = data.code,
                                       circuit_closed=data.circuit_closed,
                                       err_msg=data.err_msg,
                                       content_raw=data.content,
                                       modus=modus)

        # save_to_db(data=raw_page_content, key_lst=['step', 'step_label', 'ord_key'], to_pg = False, to_es = True)

        dwnl_res = DownloadPageResult(step=step,
                                      step_label=step_label,
                                      ord_key= ord_key,
                                      page_nr=page_number,
                                      exit_code=0,
                                      exit_message='')
    except Exception as exc:
        logger.error(f'Error when writing to data bases, "{exc}"')
        dwnl_res = DownloadPageResult(step=step,
                                      step_label=step_label,
                                      page_nr=page_number,
                                      exit_code=1,
                                      exit_message=str(exc))

    return DownloadPageFullResult(  dwnl_page_result=dwnl_res,
                                    raw_page_content=raw_page_content
                                    )

def download_post(  downloader,
                    logger,
                    step,
                    step_label,
                    post_id,
                    ord_key,
                    ml_tag,
                    modus='test'):
    while True:
        data = downloader.post_by_id(post_id)
        if data.code == 0:
            break
        else:
            logger.info(f'Request-Error: "{data.err_msg}", cirquit-closed: "{data.circuit_closed}" waiting for 2 seconds...')
            time.sleep(2.0)

    raw_page_content = None
    try:
        raw_page_content = PostRawData(step=step,
                                       step_label=step_label,
                                       ord_key=ord_key,
                                       post_id = post_id,
                                       request_code = data.code,
                                       circuit_closed=data.circuit_closed,
                                       err_msg=data.err_msg,
                                       content_raw=data.content,
                                       modus=modus,
                                       ml_tag=ml_tag)

        dwnl_res = DownloadPostResult(  step=step,
                                        step_label=step_label,
                                        ord_key=ord_key,
                                        post_id=post_id,
                                        exit_code=0,
                                        exit_message='',
                                        ml_tag=ml_tag)
    except Exception as exc:
        logger.error(f'Error when writing to data bases, "{exc}"')
        dwnl_res = DownloadPostResult(step=step,
                                      step_label=step_label,
                                      ord_key=ord_key,
                                      post_id=post_id,
                                      exit_code=1,
                                      exit_message=str(exc),
                                      ml_tag=ml_tag)
    return DownloadPostFullResult(  dwnl_post_result=dwnl_res,
                                    raw_post_content=raw_page_content
                                    )

def extract_meta(raw_page_content,
                 logger,
                 step,
                 step_label,
                 ord_key_generator,
                 test_fraction = 0.15,
                 val_fraction = 0.15,
                 modus='test'
                 ):
    res_lst = []
    soup = BeautifulSoup(raw_page_content.content_raw, 'html.parser')
    for div_question_summary_cont in soup.find_all('div'):
        ord_key=None
        if 'question-summary' in div_question_summary_cont.get('class', []):
            post_id = -1
            res = None
            ml_tag = int(choice([0, 1, 2], size=None, replace=True,
                                p=[1 - test_fraction - val_fraction, val_fraction, test_fraction]))
            try:
                post_id = int(div_question_summary_cont['id'][17:])
                logger.info(f'processing post-id: {post_id}')
                for li in div_question_summary_cont.find_all('a'):
                    if 'question-hyperlink' in li.get('class', []):
                        post_url = li['href']
                        heading = li.get_text()

                for span_item in div_question_summary_cont.find_all('span'):
                    if 'vote-count-post' in span_item.get('class', []):
                        votes = span_item.strong.get_text()

                for div_item in div_question_summary_cont.find_all('div'):
                    if 'views' in div_item.get('class', []):
                        views = div_item['title'][:-6].replace(',', '')
                    elif 'status' in div_item.get('class', []):
                        answers = div_item.strong.get_text()
                        answer_status_lst = [item for item in div_item['class'] if not item == 'status']
                        answer_status = answer_status_lst[0]

                    elif 'excerpt' in div_item.get('class', []):
                        excerpt = div_item.get_text(strip=True)
                    elif 'user-action-time' in div_item.get('class', []):
                        asked_date = div_item.span['title']
                    elif 'user-details' in div_item.get('class', []):
                        user = div_item.get_text("|", strip=True).split('|')[0]
                        try:
                            user_url = div_item.a['href']
                        except:
                            user_url = None
                    elif 'tags' in div_item.get('class', []):
                        tags = []
                        for li in div_item.find_all('a'):
                            tags.append(li.get_text())
                    else:
                        pass
                try:
                    asked_date = datetime.strptime(asked_date.replace('Z', '+00:00'), '%Y-%m-%d %H:%M:%S%z')
                except:
                    asked_date = None

                ord_key = next(ord_key_generator)
                res_data = PostMetaData(step=step,
                                        step_label=step_label,
                                        ord_key=ord_key,
                                        post_id=post_id,
                                        post_meta_extracted_date=datetime.now(),
                                        post_url=post_url,
                                        heading=heading,
                                        excerpt=excerpt,
                                        asked_date=asked_date,
                                        votes=int(votes),
                                        answers=int(answers),
                                        answer_status=answer_status,
                                        views=int(views),
                                        tags=tags,
                                        user=user,
                                        user_url=user_url,
                                        modus=modus,
                                        ml_tag=ml_tag
                                       )


                res = ExtractResult(step=step,
                                    step_label = step_label,
                                    ord_key=ord_key,
                                    post_id=post_id,
                                    exit_code=0,
                                    exit_message='',
                                    ml_tag=ml_tag
                                    )
                res_lst.append( ExtractFullResult(extract_result=res,
                                                  extract_data=res_data
                                                  )
                                )
            except Exception as exc:
                logger.error(f'Error when extracting post-id={post_id}: "{exc}"')
                res =  ExtractResult(   step=step,
                                        step_label=step_label,
                                        ord_key=ord_key,
                                        post_id=post_id,
                                        exit_code=1,
                                        exit_message=str(exc),
                                        ml_tag=ml_tag
                                        )
                res_lst.append(ExtractFullResult(   extract_result=res,
                                                    extract_data=None
                                                )
                               )



    return res_lst

def get_summary(res_lst, sub_field_name):
    res_dict = {}
    res_dict['total'] = len(res_lst)
    res_dict['successfull'] =len([item for item in res_lst if getattr(item, sub_field_name, None).exit_code==0])
    return res_dict
