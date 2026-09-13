import sqlite3

def authorizer_debug(action_code, param1, param2, db_name, trigger_or_view):
    print(f"Action: {action_code}, param1: {param1}, param2: {param2}, db: {db_name}")
    return 0

conn = sqlite3.connect("file:store.db?mode=ro", uri=True)
conn.set_authorizer(authorizer_debug)
cur = conn.cursor()
cur.execute("PRAGMA table_info('customers');")
print("PRAGMA success:", len(cur.fetchall()))
conn.close()
