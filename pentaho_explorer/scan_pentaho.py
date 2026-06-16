import os
import sqlite3

PENTAHO_PATH = r"C:\Users\willian.arce\Desktop\pentaho_explorer\PENTAHO_PROJECTS"   
DB_PATH = "database/pentaho_catalog.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo TEXT,
    ruta TEXT,
    tipo TEXT,
    contenido TEXT
)
""")

cursor.execute("DELETE FROM catalog")

for root, dirs, files in os.walk(PENTAHO_PATH):

    for file in files:

        if file.endswith((".ktr",".kjb",".xml")):

            path = os.path.join(root,file)

            try:
                with open(path,"r",encoding="utf8",errors="ignore") as f:

                    content = f.read()

                    cursor.execute("""
                    INSERT INTO catalog
                    (archivo,ruta,tipo,contenido)
                    VALUES (?,?,?,?)
                    """,(
                        file,
                        root,
                        file.split(".")[-1],
                        content.lower()
                    ))

            except:
                pass

conn.commit()
conn.close()

print("INDEXADO COMPLETADO")
