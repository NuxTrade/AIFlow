import asyncio
import warnings
import logging
from typing import Optional
from flo_ai.yaml.config import to_supervised_team
from flo_ai.builders.yaml_builder import build_supervised_team, FloRoutedTeamConfig
from typing import Any, Iterator, Union
from flo_ai.state.flo_session import FloSession
from flo_ai.models.flo_executable import ExecutableFlo
from flo_ai.error.flo_exception import FloException
from flo_ai.constants.common_constants import DOCUMENTATION_WEBSITE
from flo_ai.common.flo_logger import (
    get_logger,
    set_log_level_internal,
    set_log_config_internal,
    set_logger_internal,
    FloLogConfig,
)
from langchain.tools import StructuredTool


class Flo:
    def __init__(self, session: FloSession, config: FloRoutedTeamConfig) -> None:
        self.session = session
        self.config = config
        session.config = config
        self.runnable: ExecutableFlo = build_supervised_team(session)

        self.langchain_logger = session.langchain_logger
        get_logger().info('Flo instance created ...', session)

    def stream(self, query, config=None) -> Iterator[Union[dict[str, Any], Any]]:
        self.validate_invoke(self.session)
        get_logger().info(f"streaming query requested: '{query}'", self.session)
        return self.runnable.stream(query, config)

    def async_stream(self, query, config=None) -> Iterator[Union[dict[str, Any], Any]]:
        get_logger().info(f"Streaming async query requested: '{query}'", self.session)
        return self.runnable.astream(query, config)

    def invoke(self, query, config=None) -> Iterator[Union[dict[str, Any], Any]]:
        config = {'callbacks': [self.session.langchain_logger]}
        self.validate_invoke(self.session)
        get_logger().info(f"Invoking query: '{query}'", self.session)
        return self.runnable.invoke(query, config)

    def async_invoke(self, query, config=None) -> Iterator[Union[dict[str, Any], Any]]:
        config = {'callbacks': [self.session.langchain_logger]}
        get_logger().info(f"Invoking async query: '{query}'", self.session)
        return self.runnable.ainvoke(query, config)

    @staticmethod
    def build(session: FloSession, yaml: str, log_level: Optional[str] = None):
        if log_level:
            warnings.warn(
                '`log_level` is deprecated and will be removed in a future version. '
                'Please use `Flo.set_log_level()` instead.',
                DeprecationWarning,
                stacklevel=2,
            )
            Flo.set_log_level(log_level)
        get_logger().info('Building Flo instance from YAML ...', session)
        return Flo(session, to_supervised_team(yaml))

    @staticmethod
    def set_log_level(log_level: str):
        set_log_level_internal(log_level)

    @staticmethod
    def set_log_config(logging_config: FloLogConfig):
        set_log_config_internal(logging_config)

    @staticmethod
    def set_logger(logging_config: logging.Logger):
        set_logger_internal(logging_config)

    def draw(self, xray=True):
        from IPython.display import Image, display

        return display(Image(self.runnable.draw(xray)))

    def draw_to_file(self, filename: str, xray=True):
        from PIL import Image as PILImage
        import io

        byte_image = self.runnable.draw(xray)
        with io.BytesIO(byte_image) as image_io:
            image = PILImage.open(image_io)
            image.save(filename)

    def validate_invoke(self, session: FloSession):
        async_coroutines = filter(
            lambda x: (
                isinstance(x, StructuredTool)
                and hasattr(x, 'coroutine')
                and asyncio.iscoroutinefunction(x.coroutine)
            ),
            session.tools.values(),
        )
        async_tools = list(async_coroutines)
        if len(async_tools) > 0:
            raise FloException(
                f"""You seem to have atleast one async tool registered in this session. Please use flo.async_invoke or flo.async_stream. Checkout {DOCUMENTATION_WEBSITE}"""
            )
