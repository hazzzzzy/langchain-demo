import time

from sqlalchemy import text, create_engine

from config.config import DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE

engine = create_engine(f'mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}')


def query_mysql(query: str):
    """
    执行SQL查询并返回结果。
    输入: SQL语句
    输出: 查询结果（JSON字符串）
    """
    try:
        query_header = ['SELECT', 'select']
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


if __name__ == '__main__':
    print(query_mysql('SELECT * FROM tb_admin_log LIMIT 5;'))
