from chromadb import Settings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config.config import CHROMA_DB_PATH, MODEL_PATH

model = HuggingFaceEmbeddings(model_name=MODEL_PATH)
print('向量模型加载完毕。。。。')


def load_vectorstore(collection_name):
    """为表结构数据创建向量存储"""
    # 加载JSON格式的表结构数据
    vectorstore = Chroma(
        embedding_function=model,
        persist_directory=CHROMA_DB_PATH,
        collection_name=collection_name,
        client_settings=Settings(anonymized_telemetry=False)
    )

    return vectorstore


def search_vector(vs, query, k=5, min_score: float = 2.0):
    search_result = vs.similarity_search_with_score(query, k=k)
    # print(search_result)
    # 分数越低越相关
    result = []
    for doc, score in search_result:
        if score < min_score:
            result.append(doc)
    return result


if __name__ == '__main__':
    question = '昨日总收入多少'
    vs_qa = load_vectorstore('table_structure')
    qa_search_result = search_vector(vs_qa, question)

    r = search_vector(vs_qa, question)
    print(r)
