from typing import Union
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from flo_ai.state.flo_session import FloSession
from flo_ai.constants.prompt_constants import FLO_FINISH
from flo_ai.router.flo_router import FloRouter
from flo_ai.models.flo_team import FloTeam
from flo_ai.models.flo_routed_team import FloRoutedTeam
from langgraph.graph import StateGraph
from flo_ai.state.flo_state import TeamFloAgentState
from flo_ai.yaml.config import TeamConfig
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

class NextAgent(BaseModel):
    next: str = Field(description="Name of the next member to be called")

class StateUpdateComponent:
    def __init__(self, name: str, session: FloSession) -> None:
        self.name = name
        self.inner_session = session

    def __call__(self, input):
        self.inner_session.append(self.name)
        return input

class FloLLMRouter(FloRouter):
    
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
    
    def build_graph(self):
        flo_agent_nodes = [self.build_node(flo_agent) for flo_agent in self.members]
        workflow = StateGraph(TeamFloAgentState)
        for flo_agent_node in flo_agent_nodes:
            workflow.add_node(flo_agent_node.name, flo_agent_node.func)
        workflow.add_node(self.router_name, self.build_node(self).func)
        for member in self.member_names:
            workflow.add_edge(member, self.router_name)
        workflow.add_conditional_edges(self.router_name, self.router_fn)
        workflow.set_entry_point(self.router_name)
        workflow_graph = workflow.compile()
        return FloRoutedTeam(self.flo_team.name, workflow_graph, self.flo_team.config)
    
    class Builder:
        def __init__(self,
                    session: FloSession,
                    team_config: TeamConfig,
                    flo_team: FloTeam,
                    router_prompt: ChatPromptTemplate = None,
                    llm: Union[BaseLanguageModel, None] = None) -> None:
    
            self.name = team_config.router.name
            self.session = session
            self.llm = llm if llm is not None else session.llm
            self.flo_team = flo_team
            self.agents = flo_team.members
            self.members = [agent.name for agent in flo_team.members]
            self.options = self.members + [FLO_FINISH]
            member_type = "workers" if flo_team.members[0].type == "agent" else "team members"

            router_base_system_message = (
                "You are a supervisor tasked with managing a conversation between the"
                " following {member_type}: {members}. Given the following rules,"
                " respond with the worker to act next "
            )

            self.parser = JsonOutputParser(pydantic_object=NextAgent)
            self.llm_router_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", router_base_system_message),
                    MessagesPlaceholder(variable_name="messages"),
                    ("system", "Rules: {router_prompt}"),
                    (
                        "system",
                        "Given the conversation above, who should act next?"
                        " Or should we FINISH if the task is already answered ? Select one of: {options} \n {format_instructions}",
                    ),
                ]
            ).partial(
                options=str(self.options), 
                members=", ".join(self.members), 
                member_type=member_type, 
                router_prompt=router_prompt,
                format_instructions=self.parser.get_format_instructions()
            )
        
        def build(self):                
            chain = (
                self.llm_router_prompt
                | self.llm
                | self.parser
            )

            return FloLLMRouter(executor=chain, 
                                flo_team=self.flo_team, 
                                name=self.name, 
                                session=self.session)
