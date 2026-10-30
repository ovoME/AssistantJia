from importlib.metadata import version

from langchain.agents import create_agent
from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


class InlineLoader(BaseLoader):
    def lazy_load(self):
        yield Document(page_content='dependency smoke test', metadata={'source': 'ci'})


assert HumanMessage(content='smoke').content == 'smoke'
assert next(InlineLoader().lazy_load()).page_content == 'dependency smoke test'
assert callable(create_agent)
assert ChatOpenAI is not None

for package in ('langchain', 'langchain-community', 'langchain-core', 'langchain-openai'):
    print(f'{package}=={version(package)}')
