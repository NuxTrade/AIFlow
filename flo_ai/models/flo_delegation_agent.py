from typing import Optional
from langchain_core.runnables import Runnable
from flo_ai.yaml.config import AgentConfig
from flo_ai.state.flo_session import FloSession
from flo_ai.models.flo_executable import ExecutableFlo
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from flo_ai.models.flo_executable import ExecutableType
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.language_models import BaseLanguageModel


class FloDelegatorAgent(ExecutableFlo):
    def __init__(
        self, executor: Runnable, config: AgentConfig, model_name: str
    ) -> None:
        super().__init__(config.name, executor, ExecutableType.delegator)
        self.executor: Runnable = executor
        self.config: AgentConfig = config
        self.model_name = model_name

    class Builder:
        def __init__(
            self,
            session: FloSession,
            agentConfig: AgentConfig,
            llm: Optional[BaseLanguageModel] = None,
            model_name: str = None,
        ) -> None:
            self.config = agentConfig
            delegator_base_system_message = (
                'You are a delegator tasked with routing a conversation between the'
                ' following {member_type}: {members}. Given the following rules,'
                ' respond with the worker to act next '
            )
            self.model_name = model_name
            self.llm = session.llm if llm is None else llm
            self.options = [x.name for x in agentConfig.to]
            self.llm_router_prompt = ChatPromptTemplate.from_messages(
                [
                    ('system', delegator_base_system_message),
                    MessagesPlaceholder(variable_name='messages'),
                    ('system', 'Rules: {delegator_rules}'),
                    (
                        'system',
                        'Given the conversation above, who should act next?'
                        'Select one of: {options}',
                    ),
                ]
            ).partial(
                options=str(self.options),
                members=', '.join(self.options),
                member_type='agents',
                delegator_rules=agentConfig.job,
            )

        def build(self):
            function_def = {
                'name': 'route',
                'description': 'Select the next role.',
                'parameters': {
                    'title': 'routeSchema',
                    'type': 'object',
                    'properties': {
                        'next': {
                            'title': 'Next',
                            'anyOf': [
                                {'enum': self.options},
                            ],
                        }
                    },
                    'required': ['next'],
                },
            }

            chain = (
                self.llm_router_prompt
                | self.llm.bind_functions(
                    functions=[function_def], function_call='route'
                )
                | JsonOutputFunctionsParser()
            )

            return FloDelegatorAgent(
                executor=chain, config=self.config, model_name=self.model_name
            )
