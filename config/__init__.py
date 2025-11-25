import os

from config.config import DEEPSEEK_KEY, LANGSMITH_API_KEY

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Text2SQL_Agent_Demo"
os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
os.environ["DEEPSEEK_API_KEY"] = DEEPSEEK_KEY
