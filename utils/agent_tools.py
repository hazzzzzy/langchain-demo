import time

from langchain_core.tools import tool
from sqlalchemy import text, create_engine

from config.config import DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE
from config.logger_config import setup_logging
from utils.init_chroma import load_vectorstore

logger = setup_logging()

engine = create_engine(f'mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}')


@tool
def query_mysql(query: str):
    """
    执行SQL查询并返回结果，注意，只允许进行查询且使用此工具查询的表结构没有注释
    Args:
        query: SQL语句

    Returns:
        code: 状态码（0-成功，-1-失败，-2-不允许更改数据）
        result: 状态码为0时，返回查询结果；状态码不为0时，返回查询失败原因
    """
    # print(f"🔍 [工具执行] 正在执行 SQL: {query}")
    try:
        query_header = ['SELECT', 'select', 'show', 'SHOW', 'DESCRIBE', 'describe']
        if not any([query.startswith(i) for i in query_header]):
            # if not query.startswith('SELECT') and not query.startswith('select'):
            return -2, f"执行失败: 不允许篡改数据"

        query_start_time = time.time()
        with engine.connect() as conn:
            rows = conn.execute(text(query)).fetchall()
            query_end_time = time.time()
            logger.info(f'查询耗时 {(query_end_time - query_start_time):4f}s')
            data = [dict(row._mapping) for row in rows]
        return 0, str(data)
    except Exception as e:
        return -1, f"执行失败: {e}"


@tool
def agent_search_vector(query, k=5, min_score: float = 2.0):
    """
    这是一个检索工具,基于语义相似度检索向量数据库中的相关文档。
    当需要理解表结构、字段含义时，则必须使用此工具

    Args:
        query (str): 需要检索的查询文本（如用户的问题或关键词）。
        k(int): 返回的相关表结构文档数量，默认值5

    Returns:
        dict: {
                'table_result': List[Document],   # 表结构文档
                'qa_result': List[Document]       # 推荐的sql问答文档
                }
    """
    # print(f"🔍 [工具执行] 正在检索向量数据库: {query}")
    vs_table = load_vectorstore('table_structure')
    vs_qa = load_vectorstore('qa_sql')
    table_search_result = vs_table.similarity_search_with_score(query, k=k)
    qa_search_result = vs_qa.similarity_search_with_score(query, k=k)
    # print(search_result)
    # 分数越低越相关
    table_result, qa_result = [], []
    for doc, score in table_search_result:
        if score < min_score:
            logger.info(doc.metadata['table_name'])
            table_result.append(doc)
    for doc, score in qa_search_result:
        if score <= 0.5:
            # logger.info(doc.metadata['table_name'])
            qa_result.append(doc)
    return {'qa_result': qa_result, 'table_result': table_result}


if __name__ == '__main__':
    # print(query_mysql('SELECT * FROM tb_admin_log LIMIT 5;'))
    query = '列出昨日各酒店收入情况'
    vs_qa = load_vectorstore('qa_sql')
    qa_search_result = vs_qa.similarity_search_with_score(query, k=5)
    print(qa_search_result)