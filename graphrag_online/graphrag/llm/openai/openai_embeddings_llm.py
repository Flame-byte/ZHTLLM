# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""The EmbeddingsLLM class."""

from typing_extensions import Unpack

from graphrag.llm.base import BaseLLM
from graphrag.llm.types import (
    EmbeddingInput,
    EmbeddingOutput,
    LLMInput,
)

from .openai_configuration import OpenAIConfiguration
from .types import OpenAIClientTypes
import ollama
from urllib.parse import urlparse

# class OpenAIEmbeddingsLLM(BaseLLM[EmbeddingInput, EmbeddingOutput]):
#     """A text-embedding generator LLM."""

#     _client: OpenAIClientTypes
#     _configuration: OpenAIConfiguration

#     def __init__(self, client: OpenAIClientTypes, configuration: OpenAIConfiguration):
#         self.client = client
#         self.configuration = configuration

#     async def _execute_llm(
#         self, input: EmbeddingInput, **kwargs: Unpack[LLMInput]
#     ) -> EmbeddingOutput | None:
#         embedding_list = []

#         host = "http://localhost:11434"  # default ollama
#         if self.configuration.api_base:
#             parsed_url = urlparse(self.configuration.api_base)
#             host = f"{parsed_url.scheme}://{parsed_url.netloc}"

#         client = ollama.Client(host=host)

#         for inp in input:
#             embedding_result = client.embeddings(
#                 model=self.configuration.model, prompt=inp
#             )
#             embedding_list.append(embedding_result["embedding"])
#         return embedding_list

class OpenAIEmbeddingsLLM(BaseLLM[EmbeddingInput, EmbeddingOutput]):
    client: OpenAIClientTypes
    configuration: OpenAIConfiguration

    def __init__(self, client: OpenAIClientTypes, configuration: OpenAIConfiguration):
        self.client = client
        self.configuration = configuration

    async def _execute_llm(
        self, input: EmbeddingInput, **kwargs: Unpack[LLMInput]
    ) -> EmbeddingOutput | None:
        args = {
            "model": self.configuration.model,
            **(kwargs.get("model_parameters") or {}),
        }

        embedding_list = []
        for inp in input:
            embedding = ollama.embeddings(model=self.configuration.model, prompt=inp)
            embedding_list.append(embedding["embedding"])
        return embedding_list


