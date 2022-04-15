"""
contains dependencies for extraction of posts

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from dependency_injector import containers, providers

# import so_ana_util
from so_ana.infrastructure.download_utils import WebContentDownloader


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

