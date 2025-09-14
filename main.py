
import tkinter as tk
from tkinter import ttk, filedialog
import psycopg2
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
        self.sql_file_path = None
        self.queries = []
        self.param_widgets = {}

        # --- Форма подключения ---
        frame_conn = tk.LabelFrame(root, text="Параметры подключения")
        frame_conn.pack(fill="x", padx=10, pady=5)

        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.db_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()

        tk.Label(frame_conn, text="Host").grid(row=0, column=0, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.host_var).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(frame_conn, text="Port").grid(row=0, column=2, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.port_var).grid(row=0, column=3, padx=5, pady=2)

        tk.Label(frame_conn, text="Database").grid(row=1, column=0, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.db_var).grid(row=1, column=1, padx=5, pady=2)

        tk.Label(frame_conn, text="User").grid(row=1, column=2, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.user_var).grid(row=1, column=3, padx=5, pady=2)

        tk.Label(frame_conn, text="Password").grid(row=2, column=0, padx=5, pady=2)
        tk.Entry(frame_conn, textvariable=self.password_var, show="*").grid(row=2, column=1, padx=5, pady=2)

        tk.Button(frame_conn, text="Подключиться", command=self.connect_db).grid(row=3, column=0, pady=5)
        tk.Button(frame_conn, text="Отключиться", command=self.disconnect_db).grid(row=3, column=1, pady=5)

        # --- Кнопки загрузки SQL ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(btn_frame, text="Загрузить SQL", command=self.load_sql_file).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Обновить файл", command=self.reload_sql_file).pack(side="left", padx=5)

        # --- Выбор запроса ---
        self.query_selector = ttk.Combobox(root, state="readonly")
        self.query_selector.pack(fill="x", padx=10, pady=5)
        self.query_selector.bind("<<ComboboxSelected>>", self.on_query_change)

        # --- Параметры с прокруткой ---
        params_container = tk.LabelFrame(root, text="Параметры запроса")
        params_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.params_canvas = tk.Canvas(params_container, height=200)
        self.params_scrollbar = ttk.Scrollbar(params_container, orient="vertical", command=self.params_canvas.yview)
        self.params_scrollbar.pack(side="right", fill="y")

        self.params_canvas.configure(yscrollcommand=self.params_scrollbar.set)
        self.params_canvas.pack(side="left", fill="both", expand=True)

        self.params_frame = tk.Frame(self.params_canvas)
        self.params_canvas.create_window((0, 0), window=self.params_frame, anchor="nw")
        self.params_frame.bind(
            "<Configure>", lambda e: self.params_canvas.configure(scrollregion=self.params_canvas.bbox("all"))
        )

        # --- Кнопка запуска ---
        tk.Button(root, text="Запустить запрос", command=self.run_query).pack(pady=5)

        # --- Таблица для результата (в Scrollable Frame) ---
        self.table_frame = tk.Frame(root)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(self.table_frame, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        self.vsb = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.hsb.grid(row=1, column=0, sticky="ew")

        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.table_frame.rowconfigure(0, weight=1)
        self.table_frame.columnconfigure(0, weight=1)

        # --- Поле ошибок ---
        self.error_output = tk.Text(root, height=3, fg="red")
        self.error_output.pack(fill="x", padx=10, pady=5)

        # --- Загрузка конфига ---
        self.load_config()

    # --------------------
    # Работа с БД
    # --------------------
    def connect_db(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host_var.get(),
                port=self.port_var.get(),
                dbname=self.db_var.get(),
                user=self.user_var.get(),
                password=self.password_var.get()
            )
            self.cur = self.conn.cursor()
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Подключение успешно")
            self.save_config()
        except Exception as e:
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, f"Ошибка подключения: {e}")

    def disconnect_db(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        self.conn = None
        self.cur = None
        self.error_output.delete("1.0", tk.END)
        self.error_output.insert(tk.END, "Отключено")

    # --------------------
    # Работа с файлами
    # --------------------
    def load_sql_file(self, file_path=None, keep_state=False):
        old_values = {}
        old_index = self.query_selector.current() if keep_state else -1

        # сохраняем старые параметры
        if keep_state:
            
            for num, (entry, val_type) in self.param_widgets.items():
                old_values[num] = (entry.get(), val_type.get())
        # print(old_values)

        if not file_path:
            file_path = filedialog.askopenfilename(filetypes=[("SQL files", "*.sql")])
            if not file_path:
                return
        self.sql_file_path = file_path
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.queries = [q.strip() for q in content.split("--NEXT_QUERY") if q.strip()]
        self.query_selector["values"] = [f"Запрос {i+1}" for i in range(len(self.queries))]

        # восстанавливаем выбранный запрос
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

            # восстанавливаем старые значения, если они остались
            if old_values and num in old_values:
                # print(old_values)
                entry.insert(0, old_values[num][0])
                val_type.set(old_values[num][1])

            self.param_widgets[num] = (entry, val_type)

        # навигация стрелками (как раньше)
        param_nums = sorted(self.param_widgets.keys())
        for i, pnum in enumerate(param_nums):
            entry, _ = self.param_widgets[pnum]

            def make_nav_handler(index):
                def handler(ev):
                    if ev.keysym in ("Up", "Down"):
                        new_index = index - 1 if ev.keysym == "Up" else index + 1
                        if 0 <= new_index < len(param_nums):
                            next_pnum = param_nums[new_index]
                            next_entry, _ = self.param_widgets[next_pnum]
                            next_entry.focus_set()
                            self.params_canvas.yview_moveto(
                                max(0, next_entry.winfo_y() / max(1, self.params_frame.winfo_height()))
                            )
                        return "break"
                return handler

            entry.bind("<Up>", make_nav_handler(i))
            entry.bind("<Down>", make_nav_handler(i))

    def on_query_change(self, event=None, old_values=None):
        idx = self.query_selector.current()
        if idx >= 0 and idx < len(self.queries):
            self.build_params(self.queries[idx], old_values)

            # Навигация стрелками
            param_nums = sorted(self.param_widgets.keys())
            for i, pnum in enumerate(param_nums):
                entry, _ = self.param_widgets[pnum]

                def make_nav_handler(index):
                    def handler(ev):
                        if ev.keysym in ("Up", "Down"):
                            new_index = index - 1 if ev.keysym == "Up" else index + 1
                            if 0 <= new_index < len(param_nums):
                                next_pnum = param_nums[new_index]
                                next_entry, _ = self.param_widgets[next_pnum]
                                next_entry.focus_set()
                                self.params_canvas.yview_moveto(
                                    max(0, next_entry.winfo_y() / max(1, self.params_frame.winfo_height()))
                                )
                            return "break"
                    return handler

                entry.bind("<Up>", make_nav_handler(i))
                entry.bind("<Down>", make_nav_handler(i))

    # --------------------
    # Запуск запроса
    # --------------------
    def run_query(self):
        if not self.conn or not self.cur:
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Нет подключения к БД")
            return

        # Автообновление SQL файла с сохранением состояния
        if self.sql_file_path:
            self.load_sql_file(self.sql_file_path, keep_state=True)

        idx = self.query_selector.current()

        if idx == -1 or idx >= len(self.queries):
            self.error_output.delete("1.0", tk.END)
            self.error_output.insert(tk.END, "Не выбран запрос")
            return

        sql_query = self.queries[idx]

        # Параметры
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

                # Обновляем таблицу
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
    # Конфиг
    # --------------------
    def save_config(self):
        config = {
            "host": self.host_var.get(),
            "port": self.port_var.get(),
            "db": self.db_var.get(),
            "user": self.user_var.get(),
            "password": self.password_var.get()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.host_var.set(config.get("host", ""))
                self.port_var.set(config.get("port", "5432"))
                self.db_var.set(config.get("db", ""))
                self.user_var.set(config.get("user", ""))
                self.password_var.set(config.get("password", ""))
    
    def on_close(self):
        self.disconnect_db()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x950")  # фиксированный стартовый размер
    app = SQLRunnerApp(root)
    root.mainloop()
