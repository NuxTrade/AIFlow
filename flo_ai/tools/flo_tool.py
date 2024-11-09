import asyncio
from langchain.tools import tool
from functools import wraps
from typing import Optional

def flotool(
        name: str, 
        description: Optional[str] = None,
        argument_contract: Optional[type] = None, 
        unsafe: bool = False):
    
    def decorator(func):
        func.__doc__ = func.__doc__ or description

        @tool(name, args_schema=argument_contract)
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                if unsafe:
                    raise e
                return f"An error occurred while executing the tool: {str(e)}, please retry with the corresponding fix"
        return wrapper
    
    return decorator
