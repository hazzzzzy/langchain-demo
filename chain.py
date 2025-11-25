import datetime
from typing import TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek
from langgraph.constants import END
from langgraph.graph import StateGraph

from config.prompt import TEXT2SQL_GEN_SYSTEM_PROMPT, TEXT2SQL_GEN_USER_PROMPT, TEXT2SQL_SUMMARY_SYSTEM_PROMPT, \
    TEXT2SQL_SUMMARY_USER_PROMPT
from utils.create_visual_graph_pic import create_visual_graph_pic
from utils.init_chroma import search_vector, load_vectorstore
from utils.tools import query_mysql

# 初始化
llm = ChatDeepSeek(
    model="deepseek-chat",  # 或 "deepseek-reasoner"（依据你使用的版本）
    temperature=0.6,
    max_retries=2,
)
nowdate = datetime.datetime.now()
hotel_id = 100795
user_id = 1384


class AgentState(TypedDict):
    question: str  # 用户的问题
    schema_context: str  # 从 Chroma 检索出来的表结构
    qa_result: list  # 查询预先设定好的问答sql结果
    sql_query: str  # AI 生成的 SQL
    sql_result: str  # 数据库查询结果
    error: str  # 如果报错，存储错误信息
    retry_times: int  # 记录重试次数，防止死循环
    error_prompt: str
    answer: str

# --- 节点 1: 检索上下文 (复用你现有的 Chroma 逻辑) ---
def retrieve_schema_node(state: AgentState):
    print("--- 正在检索表结构 ---")
    question = state["question"]
    qa_result = state.get("qa_result", [])

    vs_qa = load_vectorstore('qa_sql')
    vs_table = load_vectorstore('table_structure')
    qa_search_result = search_vector(vs_qa, question, min_score=0.5)
    schema_search_result = search_vector(vs_table, question, k=8)

    if len(qa_search_result) > 0:
        for doc in qa_search_result:
            qa_result.append({
                'description': doc.page_content,
                'answer': doc.metadata['a'],
            })

    schema_context = ''
    for doc in schema_search_result:
        print(doc.metadata['table_name'])
        schema_context += f"表名：{doc.metadata['table_name']}\n表描述：{doc.page_content}\n表结构：{doc.metadata['table_structure']}\n\n"
    return {"schema_context": schema_context, 'qa_result': qa_result}


# --- 节点 2: 生成 SQL ---
def generate_sql_node(state: AgentState):
    print("--- 正在生成 SQL ---")
    question = state["question"]
    schema = state["schema_context"]
    retry_times = state.get("retry_times", 0)
    error = state.get("error", "")
    qa_result = state.get("qa_result", [])
    error_prompt = state.get("error_prompt", '')

    if len(qa_result) > 0:
        qa_result = "可参考的 问题-sql 模板，将大括号（{xxx}）中的内容替换为相应数据即可使用：\n" + '\n'.join(
            [f'- 问题：{qa['description']}，sql示例：{qa['answer']}' for qa in qa_result])
    else:
        qa_result = ''
    # 如果有错误，加入错误修正指令（LangGraph 的强大之处）
    if error:
        retry_times += 1
        error_prompt += f"第{retry_times}次生成的 SQL 执行报错了: \n报错内容：{error} \n"

    prompt = ChatPromptTemplate.from_messages([
        ("system", TEXT2SQL_GEN_SYSTEM_PROMPT),
        ("user", TEXT2SQL_GEN_USER_PROMPT)
    ])

    chain = prompt | llm | StrOutputParser()

    sql = chain.invoke({
        "nowdate": nowdate,
        "hotel_id": hotel_id,
        "user_id": user_id,
        "schema": schema,
        "question": question,
        "error_prompt": error_prompt,
        "qa_result": qa_result
    })
    return {"sql_query": sql, "retry_times": retry_times, 'error_prompt': error_prompt}


# --- 节点 3: 执行 SQL ---
def execute_sql_node(state: AgentState):
    print("--- 正在执行 SQL ---")
    sql = state["sql_query"]

    try:
        code, result = query_mysql(sql)
        if code != 0:
            return {"error": result}
        return {"sql_result": result}
    except Exception as e:
        return {"error": str(e)}


# --- 节点 4: 生成最终回答 ---
def generate_answer_node(state: AgentState):
    print("--- 正在整理最终答案 ---")
    question = state["question"]
    result = state["sql_result"]
    schema = state.get('schema_context')
    sql_query = state.get('sql_query')
    retry_times = state.get('retry_times', 0)

    system_prompt = TEXT2SQL_SUMMARY_SYSTEM_PROMPT
    if result and result != [] and retry_times < 3:
        system_prompt += '\n查询使用的sql：{sql_query}\n数据库表结构：\n{schema}'
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", TEXT2SQL_SUMMARY_USER_PROMPT)
    ])

    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({"question": question, "result": result, 'sql_query': sql_query, 'schema': schema})
    return {"answer": answer}  # 这里可以单独开一个字段，或者复用


# 1. 定义判断逻辑：执行完 SQL 后，是去生成答案，还是回去重写 SQL？
def decide_next_step(state: AgentState):
    error = state.get('error')
    if error:
        if error == '执行失败: 不允许篡改数据':
            return 'give_up'
        # 如果有错误，且重试次数没超过 3 次
        if state["retry_times"] < 3:
            print("!!! 检测到 SQL 错误，尝试自动修复 !!!")
            return "retry"
        else:
            return "give_up"
    return "success"


def build_graph():
    # 2. 初始化图
    workflow = StateGraph(AgentState)

    # 3. 添加节点
    workflow.add_node("retrieve", retrieve_schema_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("answer", generate_answer_node)

    # 4. 添加边 (流程线)
    workflow.set_entry_point("retrieve")  # 入口
    workflow.add_edge("retrieve", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")

    # 5. 添加条件边 (Conditional Edges)
    # 当 execute_sql 跑完后，根据 decide_next_step 的返回值决定去哪
    workflow.add_conditional_edges(
        "execute_sql",
        decide_next_step,
        {
            "retry": "generate_sql",  # 报错 -> 回去重写
            "success": "answer",  # 成功 -> 整理答案
            "give_up": "answer"  # 重试太多次 -> 结束
        }
    )

    workflow.add_edge("answer", END)  # 答案生成完 -> 结束

    # 6. 编译图
    app = workflow.compile()
    return app


if __name__ == '__main__':
    app = build_graph()
    # create_visual_graph_pic(app)

    inputs = {"question": "八月十八号酒店收入多少"}

    # stream 可以看到每一步的输出
    for output in app.stream(inputs):
        for key, value in output.items():
            # 打印当前节点完成后的状态更新
            print(key, value)

            # 或者直接获取最终结果
    # final_state = app.invoke(inputs)
    # print("\n=== 最终结果 ===")
    # print(final_state["sql_result"])  # 这里的 result 在 generate_answer 被覆盖为自然语言回答
