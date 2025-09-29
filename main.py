import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
import psycopg2
import pyodbc   # для InterSystems Caché
import json
import os
import re

CONFIG_FILE = "db_config.json"


class SQLRunnerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SQL Runner")
        self.conn = None
        self.cur = None
        self.db_type = tk.StringVar(value="pg")  # тип базы
        self.configs = {}

        # --- выбор площадки ---
        frame_platform = tk.LabelFrame(root, text="Площадка")
        frame_platform.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_platform, text="Профиль").grid(row=0, column=0, padx=5, pady=2)
        self.profile_selector = ttk.Combobox(frame_platform, state="readonly")
        self.profile_selector.grid(row=0, column=1, padx=5, pady=2)
        self.profile_selector.bind("<<ComboboxSelected>>", self.on_profile_change)

        # --- форма подключения ---
        frame_conn = tk.LabelFrame(root, text="Параметры подключения")
        frame_conn.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_conn, text="Тип БД").grid(row=0, column=0, padx=5, pady=2)
        self.type_selector = ttk.Combobox(frame_conn, state="readonly",
                                          values=["PostgreSQL", "Caché"])
        self.type_selector.grid(row=0, column=1, padx=5, pady=2)
        self.type_selector.current(0)
        self.type_selector.bind("<<ComboboxSelected>>", self.on_type_change)

        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.db_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()

        tk.Label(frame_conn, text="Host").grid(row=1, column=0, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.host_var).grid(row=1, column=1, padx=5, pady=2)

        tk.Label(frame_conn, text="Port").grid(row=1, column=2, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.port_var).grid(row=1, column=3, padx=5, pady=2)

        tk.Label(frame_conn, text="Database/Namespace").grid(row=2, column=0, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.db_var).grid(row=2, column=1, padx=5, pady=2)

        tk.Label(frame_conn, text="User").grid(row=2, column=2, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.user_var).grid(row=2, column=3, padx=5, pady=2)

        tk.Label(frame_conn, text="Password").grid(row=3, column=0, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.password_var, show="*").grid(row=3, column=1, padx=5, pady=2)

        tk.Button(frame_conn, text="Подключиться", command=self.connect_db).grid(row=4, column=0, pady=5)
        tk.Button(frame_conn, text="Отключиться", command=self.disconnect_db).grid(row=4, column=1, pady=5)

        # --- ошибки ---
        self.error_output = tk.Text(root, height=3, fg="red")
        self.error_output.pack(fill="x", padx=10, pady=5)

        # загрузка конфигов
        self.load_configs()

    
    # --------------------
    # тип БД
    # --------------------
    def on_type_change(self, event=None):
        if self.type_selector.get() == "PostgreSQL":
            self.db_type.set("pg")
            if not self.port_var.get():
                self.port_var.set("5432")
        else:
            self.db_type.set("cache")
            if not self.port_var.get():
                self.port_var.set("1972")  # дефолтный порт Caché

    # --------------------
    # Площадки
    # --------------------
    def on_profile_change(self, event=None):
        profile = self.profile_selector.get()
        if profile == "Добавить новую площадку...":
            self.add_new_profile()
            return

        if profile in self.configs:
            cfg = self.configs[profile]
            self.host_var.set(cfg.get("host", ""))
            self.port_var.set(cfg.get("port", "5432"))
            self.db_var.set(cfg.get("db", ""))
            self.user_var.set(cfg.get("user", ""))
            self.password_var.set(cfg.get("password", ""))

    def add_new_profile(self):
        name = simpledialog.askstring("Новый профиль", "Введите название новой площадки:")
        if not name:
            return
        if name in self.configs:
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, f"Профиль '{name}' уже существует")
            return

        # создаем пустой профиль
        self.configs[name] = {
            "host": "",
            "port": "5432",
            "db": "",
            "user": "",
            "password": ""
        }
        self.save_configs()
        self.update_profile_selector()
        self.profile_selector.set(name)

    def update_profile_selector(self):
        values = list(self.configs.keys()) + ["Добавить новую площадку..."]
        self.profile_selector["values"] = values
        if values:
            self.profile_selector.current(0)

    # --------------------
    # Работа с БД
    # --------------------
    def connect_db(self):
        try:
            if self.db_type.get() == "pg":
                self.conn = psycopg2.connect(
                    host=self.host_var.get(),
                    port=self.port_var.get(),
                    dbname=self.db_var.get(),
                    user=self.user_var.get(),
                    password=self.password_var.get()
                )
                self.cur = self.conn.cursor()

            elif self.db_type.get() == "cache":
                conn_str = (
                    f"DRIVER={{InterSystems ODBC}};"
                    f"SERVER={self.host_var.get()};"
                    f"PORT={self.port_var.get()};"
                    f"DATABASE={self.db_var.get()};"
                    f"UID={self.user_var.get()};"
                    f"PWD={self.password_var.get()};"
                )
                self.conn = pyodbc.connect(conn_str)
                self.cur = self.conn.cursor()

            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Подключение успешно")

            # сохранить конфиг
            profile = self.profile_selector.get()
            if profile and profile != "Добавить новую площадку...":
                self.configs[profile] = {
                    "type": self.db_type.get(),
                    "host": self.host_var.get(),
                    "port": self.port_var.get(),
                    "db": self.db_var.get(),
                    "user": self.user_var.get(),
                    "password": self.password_var.get()
                }
                self.save_configs()

        except Exception as e:
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, f"Ошибка подключения: {e}")

    def disconnect_db(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        self.conn, self.cur = None, None
        self.error_output.delete("1.0", tk.END)
        self.error_output.insert(tk.END, "Отключено")

    # --------------------
    # Работа с файлами SQL
    # --------------------
    def load_sql_file(self, file_path=None, keep_state=False):
        old_values = {}
        old_index = self.query_selector.current() if keep_state else -1

        if keep_state:
            for num, (entry, val_type) in self.param_widgets.items():
                old_values[num] = (entry.get(), val_type.get())

        if not file_path:
            file_path = filedialog.askopenfilename(filetypes=[("SQL files", "*.sql")])
            if not file_path:
                return
        self.sql_file_path = file_path
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.queries = [q.strip() for q in content.split("--NEXT_QUERY") if q.strip()]
        self.query_selector["values"] = [f"Запрос {i+1}" for i in range(len(self.queries))]

        if self.queries:
            if 0 <= old_index < len(self.queries):
                self.query_selector.current(old_index)
            else:
                self.query_selector.current(0)
            self.on_query_change(old_values=old_values)

    def reload_sql_file(self):
        if not self.sql_file_path:
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Сначала загрузите SQL файл")
            return
        self.load_sql_file(self.sql_file_path, keep_state=True)

    # --------------------
    # Построение параметров
    # --------------------
    def build_params(self, sql_query, old_values=None):
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        self.param_widgets = {}

        param_nums = sorted(set(int(m) for m in re.findall(r"\{(\d+)\}", sql_query)))
        for i, num in enumerate(param_nums):
            tk.Label(self.params_frame, text=f"Параметр {num}").grid(row=i, column=0, padx=5, pady=2)

            entry = tk.Entry(self.params_frame, name=f"param_{num}")
            entry.grid(row=i, column=1, padx=5, pady=2)

            val_type = tk.StringVar(value="str")
            rb_str = tk.Radiobutton(self.params_frame, text="Строка", variable=val_type, value="str")
            rb_int = tk.Radiobutton(self.params_frame, text="Число", variable=val_type, value="int")
            rb_str.grid(row=i, column=2, padx=5)
            rb_int.grid(row=i, column=3, padx=5)

            if old_values and num in old_values:
                entry.insert(0, old_values[num][0])
                val_type.set(old_values[num][1])

            self.param_widgets[num] = (entry, val_type)

    def on_query_change(self, event=None, old_values=None):
        idx = self.query_selector.current()
        if idx >= 0 and idx < len(self.queries):
            self.build_params(self.queries[idx], old_values)

    # --------------------
    # Запуск запроса
    # --------------------
    def run_query(self):
        if not self.conn or not self.cur:
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Нет подключения к БД")
            return

        if self.sql_file_path:
            self.load_sql_file(self.sql_file_path, keep_state=True)

        idx = self.query_selector.current()
        if idx == -1 or idx >= len(self.queries):
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Не выбран запрос")
            return

        sql_query = self.queries[idx]
        params_order = re.findall(r"\{(\d+)\}", sql_query)
        values = []
        for num in params_order:
            num = int(num)
            if num in self.param_widgets:
                entry, val_type = self.param_widgets[num]
                raw_val = entry.get()
                if raw_val == "":
                    values.append(None)
                elif val_type.get() == "int":
                    try:
                        values.append(int(raw_val))
                    except ValueError:
                        values.append(float(raw_val))
                else:
                    values.append(raw_val)
            else:
                values.append(None)

        sql_exec = re.sub(r"\{\d+\}", "%s", sql_query)

        try:
            self.cur.execute(sql_exec, values)
            if self.cur.description:
                rows = self.cur.fetchall()
                col_names = [desc[0] for desc in self.cur.description]

                self.tree.delete(*self.tree.get_children())
                self.tree["columns"] = col_names

                for col in col_names:
                    self.tree.heading(col, text=col)
                    self.tree.column(col, width=120, stretch=False)

                for row in rows:
                    self.tree.insert("", "end", values=row)
            else:
                self.conn.commit()

            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Запрос выполнен успешно")

        except Exception as e:
            self.conn.rollback()
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, f"Ошибка: {e}")

    # --------------------
    # Конфиги
    # --------------------
    def save_configs(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.configs, f, ensure_ascii=False, indent=2)

    def load_configs(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.configs = json.load(f)
        else:
            self.configs = {}

        self.update_profile_selector()

    def on_close(self):
        self.disconnect_db()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x950")
    app = SQLRunnerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
