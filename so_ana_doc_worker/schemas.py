"""
contains general schemas for data as used in the current module

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""


from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Any
import os
from gensim.corpora import Dictionary


@dataclass
class PostMetaData:
    """Meta information on post"""
    step: str
    step_label: str
    ord_key: int
    post_id: int
    post_meta_extracted_date: date
    post_url: str
    heading: str
    excerpt: str
    asked_date: date
    votes: int
    answers: int
    answer_status: str
    views: int
    tags: List[str]
    user: str
    user_url: str
    modus: str
    ml_tag: int


@dataclass
class BaseResult:
    """Base class for results on step level"""
    step: str
    step_label: str
    ord_key: int
    exit_code: int
    exit_message: str


@dataclass
class ExtractResult(BaseResult):
    """Result of information extraction step"""
    post_id: int
    ml_tag: int = field(default=None)


@dataclass
class DownloadPostResult(BaseResult):
    """Result of a download step for posts"""
    post_id: int
    ml_tag: int


@dataclass
class DownloadPageResult(BaseResult):
    """Result of a download step for pages (containing a list of posts)"""
    page_nr: int


@dataclass
class WorkerSummaryReport:
    """Summary report for multiple results"""
    total: int
    success: int
    failure: int = field(init=False)

    def __post_init__(self):
        self.failure = self.total - self.success

    @classmethod
    def from_result_list(cls, res_lst: List[Any], attr_name: str):
        """
        creates summary report from list of data with one field that represents an object with some exit code

        :param res_lst: list of results with a valid exit_code (0 is interpreted as absence of errors)
        :param attr_name: attribute that contains the exit code
        :return:

        """
        total = len(res_lst)
        success = len([item for item in res_lst if getattr(item, attr_name).exit_code == 0])
        return cls(total=total, success=success)


@dataclass
class PageRawData:
    """Raw page content"""
    step: str
    step_label: str
    ord_key: int
    page_nr: int
    request_code: int
    circuit_closed: bool
    err_msg: str
    content_raw: str
    modus: str


@dataclass
class DownloadPageFullResult:
    """Full download result for pages containing both data and execution information"""
    dwnl_page_result: DownloadPageResult
    raw_page_content: PageRawData


@dataclass
class PostRawData:
    """Raw post content"""
    step: str
    step_label: str
    ord_key: int
    ml_tag: int
    post_id: int
    request_code: int
    circuit_closed: bool
    err_msg: str
    content_raw: str
    modus: str


@dataclass
class DownloadPostFullResult:
    """Full download result for posts containing both data and execution information"""
    dwnl_post_result: DownloadPostResult
    raw_post_content: PostRawData


@dataclass
class ExtractFullResult:
    """Full extraction result containing both data and execution information"""
    extract_result: ExtractResult
    extract_data: PostMetaData


@dataclass
class Answer:
    """Wrapper for answer on post"""
    answer_raw: str
    answer_txt: str
    answer_links: str
    user_url: str
    user_name: str
    answer_date: date
    answer_vote: int
    is_accepted_answer: bool
    comment_lst_raw: List[str]
    comment_lst: List[str]
    comment_user_url_lst: List[str]
    comment_date_lst: List[date]
    comment_link_lst: List[str]
    modus: str


@dataclass
class QuestionInfo:
    """Wrapper for meta data on a question"""
    step: str
    step_label: str
    post_id: int
    ml_tag: int
    ord_key: int
    question_raw: str
    question_links: str
    question_txt: str
    code_pieces: str
    comment_lst_raw: List[str]
    comment_lst: List[str]
    comment_user_url_lst: List[str]
    comment_date_lst: List[datetime]
    comment_link_lst: List[str]
    answers: List[Answer]
    answer_count: int
    comment_count: int
    total_comment_count: int
    modus: str
    lang: str
    lang_prob: float
    lang_lst: List[str]
    lang_prob_lst: List[float]


@dataclass
class ExtractPostFullResult:
    """Full extract post result containing both data and execution information"""
    extract_result: ExtractResult
    extract_data: QuestionInfo


@dataclass
class TokenizationResult(BaseResult):
    """Result of tokenization step"""
    post_id: int
    ml_tag: int


@dataclass
class BoWResult(BaseResult):
    """Result of back-of-words transformation step"""
    post_id: int
    ml_tag: int


@dataclass
class TokenizationDataBase:
    """Data of tokenization step (base for BoW and Tokenized data)"""
    step: str
    step_label: str
    post_id: int
    ord_key: int
    modus: str
    ml_tag: int


@dataclass
class TokenizationData(TokenizationDataBase):
    """Data for tokenized documents"""
    tokenized_content: List[str]


@dataclass
class BoWData(TokenizationDataBase):
    """data for back-of-words representation of document"""
    file_key: str
    keys: List[int]
    values: List[int]
    key_tokens: List[str]

    def dictionary(self, base_path):
        """loads gensim dictionary from file path"""
        storage_file_path = os.path.join(base_path, self.file_key)
        return Dictionary.load_from_text(storage_file_path)

    @classmethod
    def from_dict_key_and_document(cls,
                                   step: str,
                                   step_label: str,
                                   post_id: int,
                                   ord_key: int,
                                   base_path: str,
                                   file_key: str,
                                   document: List[str],
                                   ml_tag: int,
                                   modus: str):
        """Creates a document from dictionary and document (tokenized form)"""
        res = cls(step=step,
                  step_label=step_label,
                  post_id=post_id,
                  ord_key=ord_key,
                  file_key=file_key,
                  keys=[],
                  values=[],
                  modus=modus,
                  ml_tag=ml_tag,
                  key_tokens=[]
                  )

        dictionary = res.dictionary(base_path)
        bow = dictionary.doc2bow(document)
        res.keys = [item[0] for item in bow]
        res.values = [item[1] for item in bow]
        res.key_tokens = [dictionary.get(code) for code in res.keys]
        return res

    @property
    def BoW(self):
        """Back of word representation in gensim compatible format"""
        if len(self.keys) != len(self.values):
            raise RuntimeError(f'inconsistency between "keys" and "values"')
        return list(zip(self.keys, self.values))


@dataclass
class FullTokenizationResult:
    """Full result of tokenization step containing both data and execution information"""
    tok_result: TokenizationResult
    tok_data: TokenizationData


@dataclass
class FullBoWResult:
    """Full back-of-words transformation step result containing both data and execution information"""
    bow_result: BoWResult
    bow_data: BoWData
