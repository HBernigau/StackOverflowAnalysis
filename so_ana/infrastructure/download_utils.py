import logging
import time
from datetime import datetime, timedelta
import requests
import robots
from circuitbreaker import circuit, CircuitBreakerMonitor
from typing import Dict ,Tuple

import so_ana.infrastructure.null_logger
from so_ana.infrastructure.download_types import RobotsPolicyException, HTTPError, RequResult
import so_ana.infrastructure.null_logger
import so_ana.infrastructure.config_access

def get_requ_data(page_url: str,
                  params: Dict[str, str],
                  rp: robots.RobotFileParser,
                  base_url: str,
                  user_agent: str,
                  from_email: str) -> str:
    """
    executes an HTTP get request ensuring compatibility with robots.txt file

    :param page_url: the target url
    :param params: parameters for the http request
    :param rp: robots file parser
    :param base_url: base url (*base_url*/robots.txt assumed to exist)
    :param user_agent: user agent to be appended to the HTTP request
    :param from_email: from field to be appended to the HTTP request
    :return: page as text
    """
    rp.set_url(base_url + r'/robots.txt')
    rp.read()
    if not rp.can_fetch(user_agent, page_url):
        msg = f'Url "{page_url}" not allowed by policy of "{base_url}".'
        raise RobotsPolicyException(msg)
    else:
        headers = {'User-Agent': user_agent, 'From': from_email}
        r = requests.get(url=page_url, params=params, headers=headers)
        if r.status_code == 200:
            cont = r.text
            return cont
        else:
            raise HTTPError(f'request "{page_url}" exited with code {r.status_code}.',
                            full_response=r)


class WebContentDownloader():

    def __init__(self,
                 stack_exchange_ws: str,
                 user_agent: str,
                 from_email: str,
                 logger: logging.Logger = None,
                 requ_delay=2.0,
                 recovery_timeout=400,
                 config_data=None):
        """
        A web content downloader

        :param stack_exchange_ws: abbreviation for stack exchange type
        :param user_agent: user agent (to be appended to request header)
        :param from_email: from field (to be appended to request header)
        :param logger: logger to be used
        :param requ_delay: minimal delay between successive requests
        :param recovery_timeout: timeout for recovery in case of failure
        :param config_data: configuration data (will be set to main config if not set)
        """

        self.logger = logger or so_ana.infrastructure.null_logger.get_null_logger()
        self.main_config = config_data or so_ana.infrastructure.config_access.get_main_config()
        self.user_agent = user_agent
        self.from_email = from_email
        self.stack_exchange_ws = stack_exchange_ws
        self.rp = robots.RobotFileParser()
        self.requ_delay = requ_delay
        self.get_requ_data = circuit(failure_threshold=3, recovery_timeout=recovery_timeout)(get_requ_data)

        for (key, value) in self.main_config['so_urls'].items():
            if stack_exchange_ws == key:
                self.base_url = value['base_url']
                self.post_template = value['post_template']
                self.meta_template = value['meta_template']
                break
        else:
            raise NotImplementedError(f'Stack exchange site {stack_exchange_ws} not implemented yet.')

        self._next_request_time = datetime.now()

    def _get_site(self, page_url, params=dict()):
        self.logger.info('requesting: ' + page_url)
        try:
            delay = (self._next_request_time-datetime.now()).total_seconds()
            if delay > 0:
                time.sleep(delay)
            cont = self.get_requ_data(page_url=page_url,
                                      params=params,
                                      rp=self.rp,
                                      base_url=self.base_url,
                                      user_agent=self.user_agent,
                                      from_email=self.from_email
                                     )
            self._next_request_time = datetime.now() + timedelta(seconds=self.requ_delay)
            code = 0
            msg = ''
        except Exception as exc:
            msg = f'Exception "{exc}" occurred when executing http request "{page_url}".'
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

