"""Azure OpenAI client isolated behind a small classifier interface."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings
from .models import LLMClassificationOutput
from .prompts import SYSTEM_PROMPT


class AzureClassifierClient:
    def __init__(self, settings: Settings) -> None:
        settings.require_azure_credentials()
        llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_deployment_name,
            temperature=settings.classifier_temperature,
            max_tokens=settings.classifier_max_tokens,
            timeout=settings.classifier_timeout_seconds,
            max_retries=0,
        )
        self._structured_llm = llm.with_structured_output(
            LLMClassificationOutput, method="json_schema"
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def classify(self, message: str) -> LLMClassificationOutput:
        return self._structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=message)]
        )
