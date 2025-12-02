import datetime
import time

from agno.agent import Agent
from agno.db.sqlite import AsyncSqliteDb
from agno.models.deepseek import DeepSeek
from agno.os import AgentOS
from sqlalchemy import text, create_engine

from config.config import DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE
from config.prompt.step_by_step_prompt import AGENT_SYSTEM_PROMPT
from utils.init_chroma import load_vectorstore

engine = create_engine(f'mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}')


def query_mysql(query: str):
    """
    执行SQL查询并返回结果，注意，只允许进行查询且使用此工具查询的表结构没有注释
    Args:
        query: SQL语句

    Returns:
        code: 状态码（0-成功，-1-失败，-2-不允许更改数据）
        result: 状态码为0时，返回查询结果；状态码不为0时，返回查询失败原因
    """
    # logger.info(f"[工具调用] 正在执行 SQL: {query}")
    try:
        query_header = ['SELECT', 'select', 'show', 'SHOW', 'DESCRIBE', 'describe']
        if not any([query.startswith(i) for i in query_header]):
            # if not query.startswith('SELECT') and not query.startswith('select'):
            return -2, f"执行失败: 不允许篡改数据"

        query_start_time = time.time()
        with engine.connect() as conn:
            rows = conn.execute(text(query)).fetchall()
            query_end_time = time.time()
            print(f'查询耗时 {(query_end_time - query_start_time):4f}s')
            data = [dict(row._mapping) for row in rows]
        return 0, str(data)
    except Exception as e:
        return -1, f"执行失败: {e}"


def agent_search_vector(query: str, k: int = 5, schema_min_score: float = 2.0, qa_min_score: float = 0.5):
    """
    这是一个检索工具,基于语义相似度检索表结构与预设问答sql向量数据库中的相关文档。
    当需要理解表结构、字段含义时，则必须使用此工具

    Args:
        query (str): 需要检索的查询文本（如用户的问题或关键词）。
        k (int): 返回的相关表结构与预设问答sql文档数量，默认值5
        schema_min_score (float): 表结构文档的分数阈值，分数越低表示越相关，默认值2.0。
        qa_min_score (float): 预设问答sql文档的分数阈值，分数越低表示越相关，默认值0.5。

    Returns:
        dict: {
                'schema_result': List[Document],   # 表结构文档
                'qa_result': List[Document]       # 预设问答sql文档
                }
    """
    # logger.info(f"[工具调用] 正在检索向量数据库: {query}")
    vs_schema = load_vectorstore('table_structure')
    vs_qa = load_vectorstore('qa_sql')

    # schema_search_result = vs_schema.similarity_search_with_score(query, k=k)
    schema_search_result = vs_schema.max_marginal_relevance_search(query=query, k=k, fetch_k=20, lambda_mult=0.5)
    qa_search_result = vs_qa.similarity_search_with_score(query, k=k)

    # 分数越低越相关
    schema_result, qa_result = '', ''
    for doc in schema_search_result:
        # if score < schema_min_score:
        print(doc.metadata['table_name'])
        doc = f'表名：{doc.metadata['table_name']}\n表中文名：{doc.metadata['table_zh_name']}\n表结构：{doc.metadata['table_structure']}\n'
        schema_result += doc
    for doc, score in qa_search_result:
        if score <= qa_min_score:
            # logger.info(doc.metadata['table_name'])
            doc = f'该句sql的对应场景：{doc.page_content}\n备注：{doc.metadata['remark']}\nsql内容：{doc.metadata['a']}\n'
            qa_result += doc
    return {'qa_result': qa_result, 'schema_result': schema_result}


nowdate = datetime.datetime.now().strftime('%Y-%m-%d')
hotel_id = 100785
user_id = 1384
# question = '5301房间是否有人在住，有的话报出他的登记信息'
question = '查一下当前酒店信息'

# 创建 Agent
pms_agent = Agent(
    model=DeepSeek(id="deepseek-chat"),
    instructions=AGENT_SYSTEM_PROMPT.format(hotel_id),
    db=AsyncSqliteDb(db_file="my_os.db"),
    markdown=True,
    tools=[query_mysql, agent_search_vector],

)

agent_os = AgentOS(
    id="my-first-os",
    description="My first AgentOS",
    agents=[pms_agent],
)

app = agent_os.get_app()

if __name__ == '__main__':
    agent_os.serve(app="demo:app", reload=True)
    # stream = agent.run(AGENT_USER_PROMPT.format(nowdate, hotel_id, user_id, question), stream=True, stream_events=True)
    # for chunk in stream:
    #     for chunk in stream:
    #         # print(chunk)
    #         if chunk.event == RunEvent.run_content:
    #             print(chunk.content, end='')
    #         elif chunk.event == RunEvent.tool_call_started:
    #             print(f"\nTool: {chunk.tool.tool_name} Tool_args:{chunk.tool.tool_args}")
    #         elif chunk.event == RunEvent.tool_call_completed:
    #             print(f"\nResult: {chunk.tool.result[:200]}")
