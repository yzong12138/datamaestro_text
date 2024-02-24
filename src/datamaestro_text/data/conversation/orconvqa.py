from functools import cached_property
from typing import Iterator, List, Optional, Union
from attr import define
import json
from datamaestro.data import File

from datamaestro_text.data.ir.base import GenericTopic, TopicRecord

from .base import (
    AnswerEntry,
    ConversationEntry,
    ConversationTree,
    RetrievedEntry,
    SimpleDecontextualizedRecord,
    SingleConversationTree,
)
from . import ConversationDataset


@define(kw_only=True)
class OrConvQADatasetAnswer:
    text: staticmethod
    answer_start: 0
    bid: Optional[int] = None


@define(kw_only=True)
class OrConvQADatasetHistoryEntry:
    question: str
    """The question"""

    answer: OrConvQADatasetAnswer


@define(kw_only=True)
class OrConvQADatasetEntry:
    """A query with past history"""

    query_id: int
    """Question number"""

    query: str
    """The last issued query"""

    rewrite: str
    """Manually rewritten query"""

    history: List[OrConvQADatasetHistoryEntry]
    """The list of queries asked by the user"""

    answer: OrConvQADatasetAnswer

    evidences: List[str]
    """Evidence sources for the conversation"""

    retrieval_labels: List[int]
    """Relevance status for evidences"""


@define
class OrConvQATopicRecord(SimpleDecontextualizedRecord, TopicRecord):
    pass


@define
class OrConvQAAnswerEntry(RetrievedEntry, AnswerEntry):
    pass


class OrConvQADataset(ConversationDataset, File):
    def entries(self) -> Iterator[OrConvQADatasetEntry]:
        """Iterates over re-written query with their context"""
        with self.path.open("rt") as fp:
            for line in fp.readlines():
                entry = json.loads(line)
                yield OrConvQADatasetEntry(
                    query_id=entry["qid"],
                    query=entry["question"],
                    evidences=entry["evidences"],
                    retrieval_labels=entry["retrieval_labels"],
                    rewrite=entry["rewrite"],
                    answer=OrConvQADatasetAnswer(**entry["answer"]),
                    history=[
                        OrConvQADatasetHistoryEntry(
                            question=history_entry["question"],
                            answer=OrConvQADatasetAnswer(**history_entry["answer"]),
                        )
                        for history_entry in entry["history"]
                    ],
                )

    def __iter__(self) -> Iterator[ConversationTree]:
        history: List[ConversationEntry] = []
        current_id: Optional[str] = None

        for entry in self.entries():
            # Creates a new conversation if needed
            cid, query_no = entry.query_id.rsplit("#", 1)
            if cid != current_id:
                if current_id is not None:
                    history.reverse()
                    yield SingleConversationTree(current_id, history)

                current_id = cid
                history = []

            # Add to current
            history.append(
                OrConvQATopicRecord(GenericTopic(query_no, entry.query), entry.rewrite)
            )
            history.append(
                OrConvQAAnswerEntry(
                    answer=entry.answer.text,
                    documents=entry.evidences,
                    document_relevances=entry.retrieval_labels,
                )
            )

        # Yields the last one
        history.reverse()
        yield SingleConversationTree(current_id, history)

    @cached_property
    def trees(self):
        return list(self.__iter__())

    def __len__(self):
        return len(self.trees)

    def get(self, key: int):
        return self.trees[key]
