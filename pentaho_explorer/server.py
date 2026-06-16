from flask import Flask, render_template, request, jsonify, abort
import os
import re
import ast
import xml.etree.ElementTree as ET
import time
import paramiko

app = Flask(__name__)

PENTAHO_PATH = r"C:\Users\willian.arce\Desktop\pentaho viejo\exe\proceso restante"

ETL_SERVER="10.1.1.3"
ETL_USER="sysadmin"
ETL_PASSWORD="a.123456"

ETL_LOG_PATH="/var/pentaho/logs/REGISTRO_CARGA.log"

ALLOWED_EXTENSIONS = (".ktr", ".kjb", ".xml", ".py")
IGNORE_DIRS = {"logs", "backup", ".git", "__pycache__", ".venv", "venv"}

MAX_RESULTS = 200
READ_CHUNK_SIZE = 8192
PREVIEW_MAX_CHARS = 250000


def get_etl_log():

    try:

        ssh=paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(
            ETL_SERVER,
            username=ETL_USER,
            password=ETL_PASSWORD,
            timeout=5
        )

        command=f"tail -n 200 {ETL_LOG_PATH}"

        stdin,stdout,stderr=ssh.exec_command(command)

        output=stdout.read().decode()

        ssh.close()

        return output

    except Exception as e:

        return str(e)


def is_safe_path(path: str) -> bool:
    try:
        base = os.path.abspath(PENTAHO_PATH)
        target = os.path.abspath(path)
        return target.startswith(base)
    except Exception:
        return False


def safe_read_preview(path, max_chars=PREVIEW_MAX_CHARS):
    try:
        with open(path, "r", encoding="utf8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception:
        return ""


def list_tree(base):
    def build(path):
        name = os.path.basename(path)

        if os.path.isdir(path):
            children = []

            try:
                items = sorted(
                    os.listdir(path),
                    key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower())
                )

                for item in items:
                    full = os.path.join(path, item)

                    if os.path.isdir(full):
                        if item.lower() not in IGNORE_DIRS:
                            children.append(build(full))
                    elif item.lower().endswith(ALLOWED_EXTENSIONS):
                        children.append(build(full))
            except Exception:
                pass

            return {
                "name": name,
                "type": "folder",
                "path": path,
                "children": children
            }

        return {
            "name": name,
            "type": "file",
            "path": path
        }

    return build(base)


def file_contains(path, text):
    text = text.lower()

    try:
        with open(path, "r", encoding="utf8", errors="ignore") as f:
            tail = ""

            while True:
                chunk = f.read(READ_CHUNK_SIZE)
                if not chunk:
                    break

                block = (tail + chunk).lower()

                if text in block:
                    return True

                tail = block[-len(text):] if len(text) < len(block) else block

    except Exception:
        pass

    return False


def search_files(text, selected_types=None):
    text = (text or "").strip().lower()
    if not text:
        return []

    selected_types = selected_types or []
    selected_types = [t.lower().strip(".") for t in selected_types if t]

    results = []

    for root, dirs, files in os.walk(PENTAHO_PATH):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_DIRS]

        for file in files:
            file_lower = file.lower()

            if not file_lower.endswith(ALLOWED_EXTENSIONS):
                continue

            ext = file_lower.split(".")[-1]

            if selected_types and ext not in selected_types:
                continue

            full = os.path.join(root, file)

            try:
                if text in file_lower or file_contains(full, text):
                    results.append({
                        "archivo": file,
                        "ruta": root.replace(PENTAHO_PATH, "").lstrip("\\/") or ".",
                        "path": full,
                        "tipo": ext
                    })

                    if len(results) >= MAX_RESULTS:
                        return results
            except Exception:
                pass

    return results


# -------------------------------------------------
# DETECCION SQL MEJORADA
# -------------------------------------------------

def detect_tables(sql):

    tables = set()

    if not sql:
        return []

    sql = sql.replace("\n", " ")

    patterns = [
        r'\bfrom\s+([a-zA-Z0-9_\."-]+)',
        r'\bjoin\s+([a-zA-Z0-9_\."-]+)',
        r'\binto\s+([a-zA-Z0-9_\."-]+)',
        r'\bupdate\s+([a-zA-Z0-9_\."-]+)',
        r'\btruncate\s+table\s+([a-zA-Z0-9_\."-]+)',
        r'\bdelete\s+from\s+([a-zA-Z0-9_\."-]+)',
        r'\bmerge\s+into\s+([a-zA-Z0-9_\."-]+)'
    ]

    for pattern in patterns:

        matches = re.findall(pattern, sql, re.IGNORECASE)

        for table in matches:

            table = table.replace('"', '').strip()
            table = table.split()[0]

            if table in ["", "-", "1"]:
                continue

            if not re.search("[a-zA-Z]", table):
                continue

            tables.add(table)

    return sorted(tables)


def classify_step(step_type):

    t = (step_type or "").lower()

    if "input" in t:
        return "SOURCE"

    if "output" in t or "insert" in t or "update" in t or "tableoutput" in t:
        return "TARGET"

    if "join" in t or "merge" in t:
        return "JOIN"

    if "sort" in t or "selectvalues" in t or "replace" in t:
        return "TRANSFORM"

    return "PROCESS"


def parse_ktr(path):

    data = {
        "steps": [],
        "sources": set(),
        "targets": set(),
        "joins": 0,
        "dependencies": [],
        "sql_blocks": [],
        "summary": {
            "total_steps": 0,
            "sources": 0,
            "targets": 0,
            "joins": 0,
            "complexity": "LOW"
        }
    }

    try:

        tree = ET.parse(path)
        root = tree.getroot()

        for i, step in enumerate(root.iter("step"), 1):

            name = step.findtext("name", "-")
            step_type = step.findtext("type", "-")

            sql = (
                step.findtext("sql")
                or step.findtext("lookup/sql")
                or step.findtext("statement")
                or ""
            ).strip()

            tables = detect_tables(sql)

            category = classify_step(step_type)

            destination = (
                step.findtext("table")
                or step.findtext("tablename")
                or step.findtext("lookup/table")
                or "-"
            )

            for t in tables:
                data["sources"].add(t)

            if step_type.lower() in [
                "insertupdate",
                "tableoutput",
                "delete",
                "update",
                "synchronizeaftermerge"
            ]:
                if destination and destination != "-":
                    data["targets"].add(destination)

            if category == "JOIN":
                data["joins"] += 1

            if sql:

                data["sql_blocks"].append({
                    "step": name,
                    "sql": sql
                })

            data["steps"].append({
                "nro": i,
                "step": name,
                "tipo": step_type,
                "origen": ", ".join(tables) if tables else "-",
                "destino": destination if destination else "-",
                "categoria": category,
                "sql": sql
            })

        total_steps = len(data["steps"])

        complexity = "LOW"

        if total_steps > 5:
            complexity = "MEDIUM"

        if total_steps > 12:
            complexity = "HIGH"

        data["summary"] = {
            "total_steps": total_steps,
            "sources": len(data["sources"]),
            "targets": len(data["targets"]),
            "joins": data["joins"],
            "complexity": complexity
        }

        data["sources"] = sorted(data["sources"])
        data["targets"] = sorted(data["targets"])

    except Exception as e:

        print(f"Error parse_ktr: {e}")

    return data

def parse_ktr(path):

    data = {
        "steps": [],
        "sources": set(),
        "targets": set(),
        "flows": set(),
        "joins": 0,
        "dependencies": [],
        "sql_blocks": [],
        "summary": {
            "total_steps": 0,
            "sources": 0,
            "targets": 0,
            "joins": 0,
            "complexity": "LOW"
        }
    }

    try:

        tree = ET.parse(path)
        root = tree.getroot()

        last_sources = []

        for i, step in enumerate(root.iter("step"), 1):

            name = step.findtext("name", "-")
            step_type = step.findtext("type", "-")

            sql = (
                step.findtext("sql")
                or step.findtext("lookup/sql")
                or step.findtext("statement")
                or ""
            ).strip()

            tables = detect_tables(sql)

            category = classify_step(step_type)

            destination = (
                step.findtext("table")
                or step.findtext("tablename")
                or step.findtext("lookup/table")
                or "-"
            )

            # SOURCE detectado
            if tables:
                for t in tables:
                    data["sources"].add(t)

                last_sources = tables

            # TARGET detectado
            if step_type.lower() in [
                "insertupdate",
                "tableoutput",
                "delete",
                "update",
                "synchronizeaftermerge"
            ]:

                if destination and destination != "-":

                    data["targets"].add(destination)

                    for src in last_sources:
                        data["flows"].add((src, destination))

            if category == "JOIN":
                data["joins"] += 1

            if sql:

                data["sql_blocks"].append({
                    "step": name,
                    "sql": sql
                })

            data["steps"].append({
                "nro": i,
                "step": name,
                "tipo": step_type,
                "origen": ", ".join(tables) if tables else "-",
                "destino": destination if destination else "-",
                "categoria": category,
                "sql": sql
            })

        total_steps = len(data["steps"])

        complexity = "LOW"

        if total_steps > 5:
            complexity = "MEDIUM"

        if total_steps > 12:
            complexity = "HIGH"

        data["summary"] = {
            "total_steps": total_steps,
            "sources": len(data["sources"]),
            "targets": len(data["targets"]),
            "joins": data["joins"],
            "complexity": complexity
        }

        data["sources"] = sorted(data["sources"])
        data["targets"] = sorted(data["targets"])
        data["flows"] = sorted(list(data["flows"]))

    except Exception as e:

        print(f"Error parse_ktr: {e}")

    return data
def get_crontab():

    try:

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(
            ETL_SERVER,
            username=ETL_USER,
            password=ETL_PASSWORD,
            timeout=5
        )

        command = "cat /etc/crontab_migra"

        stdin, stdout, stderr = ssh.exec_command(command)

        output = stdout.read().decode()

        ssh.close()

        return output

    except Exception as e:

        return str(e)
        
def cron_to_text(schedule):

    parts = schedule.split()

    if len(parts) != 5:
        return schedule

    minute, hour, day, month, weekday = parts

    dias = {
        "0": "Domingo",
        "1": "Lunes",
        "2": "Martes",
        "3": "Miércoles",
        "4": "Jueves",
        "5": "Viernes",
        "6": "Sábado",
        "7": "Domingo"
    }

    if schedule == "* * * * *":
        return "Cada minuto"

    if minute.startswith("*/"):
        return f"Cada {minute[2:]} minutos"

    if hour.startswith("*/"):
        return f"Cada {hour[2:]} horas"

    if weekday == "*":
        if minute.isdigit() and hour.isdigit():
            return f"Todos los días a las {hour.zfill(2)}:{minute.zfill(2)} horas"

    if "-" in weekday:

        start, end = weekday.split("-")

        d1 = dias.get(start, start)
        d2 = dias.get(end, end)

        return f"De {d1} a {d2} a las {hour.zfill(2)}:{minute.zfill(2)} horas"

    if weekday.isdigit():

        d = dias.get(weekday, weekday)

        return f"{d} a las {hour.zfill(2)}:{minute.zfill(2)} horas"

    return schedule

@app.route("/crontab")
def crontab_view():

    data = get_crontab()

    lines = []

    for l in data.splitlines():

        if not l.strip():
            continue

        if l.strip().startswith("#"):
            continue

        parts = l.split()

        if len(parts) < 6:
            continue

        schedule = " ".join(parts[0:5])
        schedule_text = cron_to_text(schedule)
        user = parts[5]
        command = " ".join(parts[6:])

        lines.append({
            "schedule": schedule,
            "schedule_text": schedule_text,
            "user": user,
            "command": command
                        })
    return render_template(
        "crontab.html",
        rows=lines
    )
        
def parse_python(path):
    data = {
        "functions": [],
        "classes": [],
        "imports": [],
        "rows": [],
        "summary": {
            "total_steps": 0,
            "sources": 0,
            "targets": 0,
            "joins": 0,
            "complexity": "LOW"
        }
    }

    try:
        with open(path, "r", encoding="utf8", errors="ignore") as f:
            content = f.read()

        tree = ast.parse(content)

        imports = []
        functions = []
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.append(n.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(module)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)

        imports = sorted(set([i for i in imports if i]))
        functions = sorted(set(functions))
        classes = sorted(set(classes))

        rows = []
        idx = 1

        for cls in classes:
            rows.append({
                "nro": idx,
                "step": cls,
                "tipo": "Class",
                "origen": "-",
                "destino": "-",
                "categoria": "PROCESS",
                "sql": ""
            })
            idx += 1

        for fn in functions:
            rows.append({
                "nro": idx,
                "step": fn,
                "tipo": "Function",
                "origen": "-",
                "destino": "-",
                "categoria": "PROCESS",
                "sql": ""
            })
            idx += 1

        total_items = len(rows)
        complexity = "LOW"
        if total_items > 8:
            complexity = "MEDIUM"
        if total_items > 20:
            complexity = "HIGH"

        data["functions"] = functions
        data["classes"] = classes
        data["imports"] = imports
        data["rows"] = rows
        data["summary"] = {
            "total_steps": total_items,
            "sources": len(imports),
            "targets": len(functions),
            "joins": len(classes),
            "complexity": complexity
        }

    except Exception as e:
        print(f"Error parse_python: {e}")

    return data


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/tree")
def api_tree():
    return jsonify(list_tree(PENTAHO_PATH))


@app.route("/search")
def search():
    q = request.args.get("q", "").lower().strip()
    types_raw = request.args.get("types", "").strip()
    selected_types = [t for t in types_raw.split(",") if t]

    start = time.time()
    results = search_files(q, selected_types=selected_types)
    elapsed = round((time.time() - start) * 1000, 2)

    return jsonify({
        "results": results,
        "count": len(results),
        "elapsed_ms": elapsed,
        "limited": len(results) >= MAX_RESULTS
    })


@app.route("/open")
def open_file():
    path = request.args.get("path", "")
    q = request.args.get("q", "")

    if not path or not os.path.exists(path) or not is_safe_path(path):
        abort(404)

    ext = os.path.splitext(path)[1].lower()
    content = safe_read_preview(path)

    parsed = {
        "summary": {
            "total_steps": 0,
            "sources": 0,
            "targets": 0,
            "joins": 0,
            "complexity": "LOW"
        },
        "sources": [],
        "targets": [],
        "dependencies": [],
        "sql_blocks": []
    }
    rows = []
    functions = []
    classes = []
    imports = []

    if ext == ".ktr":
        parsed = parse_ktr(path)
        rows = parsed["steps"]
    elif ext == ".kjb":
        parsed = parse_kjb(path)
        rows = parsed["entries"]
    elif ext == ".py":
        py_data = parse_python(path)
        rows = py_data["rows"]
        parsed["summary"] = py_data["summary"]
        functions = py_data["functions"]
        classes = py_data["classes"]
        imports = py_data["imports"]

    return render_template(
        "viewer.html",
        file=path,
        filename=os.path.basename(path),
        ext=ext,
        content=content,
        rows=rows,
        summary=parsed.get("summary", {}),
        sources=parsed.get("sources", []),
        targets=parsed.get("targets", []),
        dependencies=parsed.get("dependencies", []),
        sql_blocks=parsed.get("sql_blocks", []),
        functions=functions,
        classes=classes,
        imports=imports,
        search=q
    )
@app.route("/etl/log")
def etl_log():

    log=get_etl_log()

    return jsonify({
        "log":log
    })
@app.route("/etl")
def etl_dashboard():

    log = get_etl_log()

    lines = log.splitlines()

    today = time.strftime("%Y-%m-%d")

    procesos = {}
    procesos_error = set()

    rows = []

    for l in reversed(lines):

        if today not in l:
            continue

        parts = l.split()

        if len(parts) < 3:
            continue

        proceso = parts[2]

        procesos[proceso] = True

        if "ERROR" in l.upper():
            procesos_error.add(proceso)

        estado = "OK"

        if "ERROR" in l.upper():
            estado = "ERROR"

        rows.append({
            "line": l,
            "estado": estado,
            "proceso": proceso
        })

    total_procesos = len(procesos)

    total_error = len(procesos_error)

    total_ok = total_procesos - total_error

    return render_template(
        "etl_dashboard.html",
        rows=rows,
        total=total_procesos,
        ok=total_ok,
        error=total_error,
        today=today
    )


@app.route("/catalog")
def catalog():
    path = request.args.get("path", "")

    if not path or not os.path.exists(path) or not is_safe_path(path):
        abort(404)

    ext = os.path.splitext(path)[1].lower()

    parsed = {
        "summary": {
            "total_steps": 0,
            "sources": 0,
            "targets": 0,
            "joins": 0,
            "complexity": "LOW"
        },
        "sources": [],
        "targets": [],
        "dependencies": [],
        "sql_blocks": []
    }
    functions = []
    classes = []
    imports = []

    if ext == ".ktr":
        parsed = parse_ktr(path)
    elif ext == ".kjb":
        parsed = parse_kjb(path)
    elif ext == ".py":
        py_data = parse_python(path)
        parsed["summary"] = py_data["summary"]
        functions = py_data["functions"]
        classes = py_data["classes"]
        imports = py_data["imports"]

    return render_template(
        "catalog.html",
        file=os.path.basename(path),
        ext=ext,
        summary=parsed.get("summary", {}),
        sources=parsed.get("sources", []),
        targets=parsed.get("targets", []),
        dependencies=parsed.get("dependencies", []),
        sql_blocks=parsed.get("sql_blocks", []),
        functions=functions,
        classes=classes,
        imports=imports
    )


if __name__ == "__main__":
    app.run(port=5000, debug=True)
