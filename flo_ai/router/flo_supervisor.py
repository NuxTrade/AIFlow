from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Union
from langchain_core.runnables import Runnable
from flo_ai.state.flo_session import FloSession
from flo_ai.constants.prompt_constants import FLO_FINISH
from flo_ai.router.flo_llm_router import FloLLMRouter, StateUpdateComponent
from flo_ai.models.flo_team import FloTeam
from flo_ai.yaml.config import TeamConfig
from langchain_core.output_parsers import JsonOutputParser
from flo_ai.router.flo_llm_router import NextAgent

supervisor_system_message = (
    "You are a supervisor tasked with managing a conversation between the"
    " following {member_type}: {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When the users question is answered or the assigned task is finished,"
    " respond with FINISH. "
)

class FloSupervisor(FloLLMRouter):
    
    def __init__(self,
                 session: FloSession,
                 executor: Runnable, 
                 flo_team: FloTeam,
                 name: str) -> None:
        super().__init__(
            session = session, 
            name = name, 
            flo_team = flo_team,
            executor = executor
        )

    class Builder:
        def __init__(self,
                    session: FloSession,
                    team_config: TeamConfig,
                    flo_team: FloTeam,
                    llm: Union[BaseLanguageModel, None] = None) -> None:
            self.name = team_config.router.name
            self.session = session
            self.llm = llm if llm is not None else session.llm
            self.flo_team = flo_team
            self.agents = flo_team.members
            self.members = [agent.name for agent in flo_team.members]
            self.options = self.members + [FLO_FINISH]
            member_type = "workers" if flo_team.members[0].type == "agent" else "team members"
            self.parser = JsonOutputParser(pydantic_object=NextAgent)
            self.supervisor_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", supervisor_system_message),
                    MessagesPlaceholder(variable_name="messages"),
                    (
                        "system",
                        "Given the conversation above, who should act next?"
                        " Or should we FINISH if the task is already answered, Select one of: {options}  \n {format_instructions}",
                    ),
                ]
            ).partial(
                options=str(self.options), 
                members=", ".join(self.members), 
                member_type=member_type,
                format_instructions=self.parser.get_format_instructions()
            )
        
        def build(self):
            chain = (
                self.supervisor_prompt
                | self.llm
                | self.parser
            )

            return FloSupervisor(executor=chain, 
                                flo_team=self.flo_team, 
                                name=self.name, 
                                session=self.session)
