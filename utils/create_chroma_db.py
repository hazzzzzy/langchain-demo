import json

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

CHROMA_DB_PATH = '../asset/chroma_db'
SQL_FILE_PATH = '../asset/tables_enriched.json'
QA_FILE_PATH = '../asset/qa_sql.json'
model = HuggingFaceEmbeddings(model_name='../models/bge-base-zh-v1.5')

with open(SQL_FILE_PATH, 'r', encoding='utf-8') as f:
    sql_data = json.load(f)

with open(QA_FILE_PATH, 'r', encoding='utf-8') as f:
    qa_data = json.load(f)

sql_docs, qa_docs = [], []

for table in sql_data:
    # 为每个表创建一个文档
    table_name = table.get('table_name', '未知表')
    table_description = table.get('table_description', '')
    fields = table.get('fields', [])

    # 构建表结构描述
    table_structure = ''

    for field in fields:
        column_name = field.get('column_name', '')
        column_type = field.get('column_type', '')
        column_comment = field.get('column_comment', '')
        table_structure += f"  - {column_name} ({column_type}): {column_comment}\n"

    # content = "\n".join(content_parts)

    # 创建文档对象
    doc = Document(
        page_content=table_description,
        metadata={
            "table_structure": table_structure,
            "table_name": table_name,
            "table_zh_name": table_description.split('，表名为')[0],
            # "type": "table_structure"
        }
    )
    sql_docs.append(doc)

for qa in qa_data:
    q = qa['q']
    a = qa['a']
    doc = Document(
        page_content=q,
        metadata={
            'a': a,
            'remark': qa['remark']
        }
    )
    qa_docs.append(doc)

# 加载JSON格式的表结构数据
collections = {
    "table_structure": sql_docs,
    "qa_sql": qa_docs
}

vectorstores = {}
for collection_name, docs in collections.items():
    vectorstores[collection_name] = Chroma.from_documents(
        documents=docs,
        embedding=model,
        persist_directory=CHROMA_DB_PATH,
        collection_name=collection_name
    )


#
# vs_qa = Chroma(
#     embedding_function=model,
#     persist_directory=CHROMA_DB_PATH,
#     collection_name='qa_sql')
# vs_table = Chroma(
#     embedding_function=model,
#     persist_directory=CHROMA_DB_PATH,
#     collection_name='table_structure')
# search_result = vs_qa.similarity_search_with_score('今日营收', k=1)
# print(search_result)
