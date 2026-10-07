"""构建期清理知识库数据库：保留知识库登记，清空对话记录。

纯镜像部署时会把仓库里的 info.db 烘进镜像，如果直接烘原文件，会把本机的
测试会话（message/conversation 等）一起带进发布镜像。这里只保留知识库与
文件登记（knowledge_base / knowledge_file / file_doc），其余会话表清空。

用法（构建期）:
    python sanitize_kb_db.py /root/mdt_data/data/knowledge_base/info.db
"""

import sqlite3
import sys

CLEAR_TABLES = ("message", "conversation", "human_message_event", "summary_chunk")


def main() -> int:
    db = sys.argv[1] if len(sys.argv) > 1 else "/root/mdt_data/data/knowledge_base/info.db"
    con = sqlite3.connect(db)
    try:
        tables = {
            r[0]
            for r in con.execute("select name from sqlite_master where type='table'")
        }
        for name in CLEAR_TABLES:
            if name in tables:
                con.execute(f'DELETE FROM "{name}"')
        con.commit()
        for name in sorted(tables):
            count = con.execute(f'select count(*) from "{name}"').fetchone()[0]
            print(f"  {name}: {count}")
    finally:
        con.close()
    print(f"已清理会话记录: {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
