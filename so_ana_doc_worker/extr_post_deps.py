"""
contains dependencies for extraction of posts

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""


import os
import requests
import logging
import time
from dependency_injector import containers, providers
import robots
from dataclasses import dataclass
from circuitbreaker import circuit, CircuitBreakerMonitor
from datetime import datetime, timedelta

import so_ana_util
from so_ana_util.common_types import get_tst_logger, get_null_logger, get_prod_logger, TstHandler


class AbstractContentDownloader:
    """
    This class represents an abstract base class for a content downloader.

    Concrete representations will be implemented by the real  downloader and by
    a mock downloader that reads in data from hard disk.
    """

    def metadata_by_topic_and_page(self, topic: str, page_nr: int) -> str:
        """
        Requests a meta data page by topic and page number

        :param topic: topic label
        :param page_nr: the page number

        :return: the requested page as string
        """
        raise NotImplementedError('To be implemented in subclass')

    def post_by_id(self, post_id: int) -> str:
        """
        requests a post by id

        :param post_id: id of the post
        :return: the content of the post as string
        """
        raise NotImplementedError('To be implemented in subclass')

@dataclass
class RequResult:
    """
    Represents the result of a request
    """
    code: int
    content: str
    err_msg: str
    circuit_closed: bool = True


class RobotsPolicyException(ValueError):
    pass


class HTTPError(RuntimeError):
    pass


def get_requ_data(page_url,
                  params,
                  rp,
                  base_url ,
                  user_agent,
                  from_email):
    rp.set_url(base_url + r'/robots.txt')
    rp.read()
    if not rp.can_fetch(user_agent, page_url):
        msg = f'Url "{page_url}" not allowed by policy of "{base_url}".'
        raise RobotsPolicyException(msg)
    else:
        headers = {'User-Agent': user_agent, 'From': from_email}
        r = requests.get(url=page_url, params=params, headers = headers)
        if r.status_code == 200:
            cont = r.text
            return (0, cont)
        else:
            raise HTTPError(f'request "{page_url}" exited with code {r.status_code}.')


class WebContentDownloader(AbstractContentDownloader):

    def __init__(self,
                 stack_exchange_ws: str,
                 user_agent: str,
                 from_email: str,
                 logger: logging.Logger = None,
                 requ_delay=2.0,
                 recovery_timeout=400):

        self.logger = logger or get_null_logger()
        self.user_agent = user_agent
        self.from_email = from_email
        self.stack_exchange_ws = stack_exchange_ws
        self.rp = robots.RobotFileParser()
        self.requ_delay = requ_delay
        self.get_requ_data = circuit(failure_threshold=3, recovery_timeout=recovery_timeout)(get_requ_data)

        main_config = so_ana_util.get_main_config()

        for (key, value) in main_config['so_urls'].items():
            if stack_exchange_ws==key:
                self.base_url = value['base_url']
                self.post_template = value['post_template']
                self.meta_template = value['meta_template']
                break
        else:
            NotImplementedError(f'Stack exchange site {stack_exchange_ws} not implemented yet.')

        self._next_request_time = datetime.now()

    def _get_site(self, page_url, params=dict()):
        self.logger.info('requesting: ' + page_url)
        try:
            delay = (self._next_request_time-datetime.now()).total_seconds()
            if delay > 0:
                time.sleep(delay)
            res = self.get_requ_data(   page_url=page_url,
                                        params=params,
                                        rp=self.rp,
                                        base_url=self.base_url,
                                        user_agent=self.user_agent,
                                        from_email = self.from_email
                                )
            self._next_request_time = datetime.now() + timedelta(seconds=self.requ_delay)
            code = res[0]
            cont = res[1]
            msg = ''
        except Exception as exc:
            msg = f'Exception "{exc}" occured when executing http request "{page_url}".'
            self.logger.error(msg)
            code = 1
            cont = ''
            msg = str(exc)

        return RequResult(code=code,
                          content=cont,
                          err_msg=msg,
                          circuit_closed=CircuitBreakerMonitor.get('get_requ_data').closed)

    def metadata_by_topic_and_page(self, topic: str, page_nr: int)->str:
        return self._get_site(self.meta_template.replace('@tag@', str(topic)),
                              {'tab': 'newest', 'page': page_nr, 'pagesize': 50})

    def post_by_id(self, post_id: int)->str:
        return self._get_site(self.post_template.replace('@post_id@', str(post_id)))


class Prod_container(containers.DeclarativeContainer):

    config = providers.Configuration()

    page_downloader = providers.Factory(WebContentDownloader,
                                        stack_exchange_ws = config.stack_exchange_ws,
                                        user_agent = config.user_agent,
                                        from_email = config.from_email,
                                        logger = config.logger,
                                        requ_delay=config.requ_delay,
                                        recovery_timeout=config.recovery_timeout
                                        )

