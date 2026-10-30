import sqlite3
conn = sqlite3.connect("aura_hafiza.db")
conn.execute("UPDATE hafiza SET aktif=0 WHERE konu LIKE '%Elysia%'")
conn.commit()
conn.close()
