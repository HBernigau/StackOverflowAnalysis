import typing

class DownloaderProtocol(typing.Protocol):

    def metadata_by_topic_and_page(self, topic: str, nr: int)->:
        pass