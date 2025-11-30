import datetime
import os
from typing import Annotated, TypedDict
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from config.logger_config import setup_logging
from config.prompt.step_by_step_prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT
from utils.agent_tools import agent_search_vector, query_mysql

os.environ["LANGCHAIN_PROJECT"] = "Text2SQL_Agent"
logger = setup_logging()


class AgentState(TypedDict):
    # add_messages 是 LangGraph 的黑魔法：
    # 当节点返回新的 message 时，它不是覆盖，而是 append（追加）到列表里
    messages: Annotated[list[BaseMessage], add_messages]


# 1. 初始化 LLM 并绑定工具
# bind_tools 让 DeepSeek 知道它有了“查数据库”的能力
llm = ChatDeepSeek(model="deepseek-chat", temperature=0.6)
tools = [query_mysql, agent_search_vector]
llm_with_tools = llm.bind_tools(tools)


# 2. 定义【思考节点】 (Brain)
def agent_node(state: AgentState):
    # print("[AI 思考中]...")
    messages = state["messages"]
    # LLM 会看之前的对话历史，决定是直接回答，还是调用工具
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# def summary_node(state: AgentState):
#     messages = state["messages"]
#     # print(messages)
#
#     question = messages[1].content
#     answer = messages[-1].content
#     # logger.info(question,)
#     # logger.info(answer)
#
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", SUMMARY_AGENT_SYSTEM_PROMPT),
#         ("user", SUMMARY_AGENT_USER_PROMPT)
#     ])
#
#     chain = prompt | llm | StrOutputParser()
#     summary_context = chain.invoke({
#         'question': question,
#         'answer': answer,
#     })
#     logger.info(summary_context)
#     return {"messages": [AIMessage(content=summary_context)]}


# 3. 定义【工具节点】 (Action)
# ToolNode 是 LangGraph 自带的，它会自动识别 LLM 返回的 tool_calls 并执行


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    messages = state["messages"]
    last_message = messages[-1]

    # 如果 LLM 的回复里包含 tool_calls，说明它想查库 -> 转去工具节点
    if last_message.tool_calls:
        return "tools"
    # print(messages)
    # 否则说明它觉得信息够了，已经生成了最终文本 -> 结束
    return "__end__"


def build_graph():
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("ReAct", agent_node)

    tool_node = ToolNode(tools)
    workflow.add_node("tools", tool_node)
    # workflow.add_node("summary", summary_node)

    # 设置入口
    workflow.set_entry_point("ReAct")

    # 添加条件边：AI 思考完后，决定是去查库(tools)还是结束(END)
    workflow.add_conditional_edges(
        "ReAct",
        should_continue,
    )

    # 添加普通边：工具查完后，必须把结果扔回给 AI，让它继续思考
    workflow.add_edge("tools", "ReAct")
    # workflow.add_edge("summary", END)  # 答案生成完 -> 结束

    app = workflow.compile()
    return app


if __name__ == '__main__':
    nowdate = datetime.datetime.now().strftime('%Y-%m-%d')
    hotel_id = 100785
    user_id = 1384

    app = build_graph()
    # create_visual_graph_pic(app, 'step_by_step_2')

    # question = '根据现在的预订进度，建议一下明天复式大床房的价格应该定多少？'
    question = '当前的房态情况如何'
    inputs = {
        "messages": [
            SystemMessage(content=AGENT_SYSTEM_PROMPT.format(hotel_id)),
            HumanMessage(content=AGENT_USER_PROMPT.format(nowdate, hotel_id, user_id, question))
        ]
    }

    logger.info("====== 开始运行 Agent ======")

    # stream_mode="values" 会返回每次状态更新后的完整 State
    # 但这里我们用默认模式，只获取增量更新，这样更方便看每一步做了什么
    for event in app.stream(inputs, config={"recursion_limit": 50}):
        # 1. 捕获 Agent 的思考与行动
        if "ReAct" in event:
            # print(event)
            message = event["ReAct"]["messages"][0]
            content = message.content
            tool_calls = message.tool_calls

            # 打印 AI 的思考文本 (如果有)
            if content:
                logger.info(f"[AI 回答]: {content}")

            # 打印 AI 决定调用的工具
            if tool_calls:
                for tc in tool_calls:
                    logger.info(f"[调用工具] {tc['name']}: {tc['args']}")

        # 2. 捕获工具的返回结果
        elif "tools" in event:
            # print('工具调用')
            # ToolNode 返回的是 ToolMessage
            message = event["tools"]["messages"][0]
            logger.info(f"[工具返回]: {message.content[:200]}...")  # 只打印前200字防止刷屏

    logger.info("====== 运行结束 ======")

    # # 1. 运行并获取最终状态
    # final_state = app.invoke(inputs)
    #
    # print("\n====== 推理全过程复盘 ======\n")
    #
    # # 2. 遍历历史消息
    # for msg in final_state["messages"]:
    #
    #     if isinstance(msg, HumanMessage):
    #         print(f"👤 [用户]: {msg.content}")
    #
    #     elif isinstance(msg, AIMessage):
    #         # 检查是否有工具调用
    #         if msg.tool_calls:
    #             print(f"🤖 [AI 思考]: {msg.content}")  # DeepSeek 有时会把思考写在 content 里
    #             for tc in msg.tool_calls:
    #                 print(f"🛠️ [AI 决定调用工具]: {tc['name']} -> 参数: {tc['args']}")
    #         else:
    #             print(f"🤖 [AI 最终回答]: {msg.content}")
    #
    #     elif isinstance(msg, ToolMessage):
    #         print(f"📊 [数据库/工具 反馈]: {msg.content}")
    #
    #     print("-" * 50)
