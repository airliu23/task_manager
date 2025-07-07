import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import json
import os
from datetime import datetime
import difflib
import re
import subprocess
import platform
import uuid

class TaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title("任务记录工具")
        self.root.geometry("900x600")
        self.root.resizable(True, True)

        # 字体设置：固定为14号SimHei
        self.font_size = 14
        self.font = ("SimHei", self.font_size)
        try:
            self.root.tk.call('tk', 'scaling', self.root.winfo_fpixels('1i') / 96.0)
        except:
            pass
        # 全局字体设置
        self.root.option_add("*Font", f"SimHei {self.font_size}")

        self.tasks = []
        self.tasks_file = "tasks.json"
        self.base_dir = os.path.abspath(os.path.join(os.getcwd(), ""))

        self.load_tasks()

        self.selected_tasks = set()
        self.current_task_id = None
        self.filter_status = "全部"

        self.create_widgets()
        self.update_task_list()
        # 注释掉窗口大小变化时的字体缩放，保持14号不变
        # self.root.bind("<Configure>", self.on_window_resize)

    def generate_folder_path(self, project, short_desc, ver):
        """生成合法的文件夹路径（基于project和short_desc）"""
        # 替换非法字符
        safe_project = re.sub(r'[\\/:*?"<>|]', '_', project.strip())
        safe_desc = re.sub(r'[\\/:*?"<>|]', '_', short_desc.strip())
        safe_ver = re.sub(r'[\\/:*?"<>|]', '_', ver.strip())

        # 构建路径：基础目录/项目/简易描述
        folder_path = os.path.join(self.base_dir, safe_project, safe_desc, safe_ver)
        return folder_path

    def create_folder_if_not_exists(self, folder_path):
        """创建文件夹（如果不存在）"""
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                return True
            except Exception as e:
                messagebox.showerror("错误", f"创建文件夹失败: {str(e)}")
                return False
        return True

    def open_task_folder(self, folder):
        """打开任务对应的文件夹（修复路径拼接问题）"""
        folder_path = os.path.join(self.base_dir, folder)
        if not folder_path:
            messagebox.showwarning("提示", "文件夹路径未设置！")
            return
        if not os.path.exists(folder_path):
            messagebox.showwarning("提示", "文件夹不存在！")
            return

        # 根据操作系统调用对应命令
        system = platform.system()
        try:
            if system == "Windows":
                # Windows：使用 explorer 打开
                subprocess.Popen(f'explorer "{folder_path}"')
            elif system == "Darwin":
                # macOS：使用 open 打开
                subprocess.Popen(f'open "{folder_path}"')
            elif system == "Linux":
                # Linux：使用 xdg-open 打开
                subprocess.Popen(f'xdg-open "{folder_path}"')
            else:
                messagebox.showwarning("提示", "暂不支持该操作系统的文件夹打开操作！")
        except Exception as e:
            messagebox.showerror("错误", f"打开文件夹失败：{str(e)}")

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=0)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)
        main_frame.rowconfigure(3, weight=0)

        # 筛选器区域
        filter_frame = ttk.Frame(main_frame)
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(filter_frame, text="筛选状态:", font=self.font).pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(
            filter_frame, 
            textvariable=self.filter_var,
            values=["全部", "未完成", "已完成"],
            state="readonly",
            width=10,
            font=self.font
        )
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind("<<ComboboxSelected>>", self.on_filter_change)

        # 任务列表区域
        list_frame = ttk.LabelFrame(main_frame, text="任务列表", padding="14")
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 14))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("select", "id", "project", "short_desc", "priority", "create_time", "modified_time", "completed")
        self.task_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        self.task_tree.heading("select", text="选择")
        self.task_tree.heading("id", text="ID")
        self.task_tree.heading("project", text="项目")
        self.task_tree.heading("short_desc", text="简易描述")
        self.task_tree.heading("priority", text="优先级")
        self.task_tree.heading("create_time", text="创建时间")
        self.task_tree.heading("modified_time", text="修改时间")
        self.task_tree.heading("completed", text="状态")

        self.task_tree.column("select", width=30, anchor=tk.CENTER)
        self.task_tree.column("id", width=50, anchor=tk.CENTER)
        self.task_tree.column("project", width=120)
        self.task_tree.column("short_desc", width=180)
        self.task_tree.column("priority", width=80, anchor=tk.CENTER)
        self.task_tree.column("create_time", width=150, anchor=tk.CENTER)
        self.task_tree.column("modified_time", width=150, anchor=tk.CENTER)
        self.task_tree.column("completed", width=80, anchor=tk.CENTER)

        self.task_tree.grid(row=0, column=0, sticky="nsew")
        self.task_tree.bind("<Button-1>", self.on_tree_click)
        self.task_tree.bind("<Double-1>", self.on_tree_double_click)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # 操作按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky="ew", pady=5)
        button_frame.columnconfigure(0, weight=1)

        ttk.Button(button_frame, text="全选", command=self.select_all_tasks).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="反选", command=self.invert_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="标记为完成", command=self.mark_tasks_completed).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除选中", command=self.delete_tasks).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空已完成", command=self.clear_completed_tasks).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="刷新列表", command=self.update_task_list).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="添加任务", command=self.open_add_task_window).pack(side=tk.RIGHT, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(value="任务总数: 0, 已完成: 0, 选中: 0")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=3, column=0, sticky="ew", pady=(5, 0))

    # 移除窗口缩放时的字体调整逻辑，保持14号字体不变
    # def on_window_resize(self, event):
    #     if event.width < 600 or event.height < 400:
    #         return
    #     scale_factor = min(event.width/900, event.height/600)
    #     new_font = max(int(self.base_font_size * scale_factor), 8)
    #     self.root.option_add("*Font", f"SimHei {new_font}")

    def on_filter_change(self, event=None):
        """筛选状态变更时更新任务列表"""
        self.filter_status = self.filter_var.get()
        self.update_task_list()

    def load_tasks(self):
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for t in loaded:
                        if "description_history" not in t:
                            t["description_history"] = [{"version": 1, "timestamp": t["create_time"], "action": "创建"}]
                        if "modified_time" not in t:
                            t["modified_time"] = t["create_time"]
                    self.tasks = loaded
            except Exception as e:
                messagebox.showerror("错误", f"加载失败: {str(e)}")
                self.tasks = []

    def save_tasks(self):
        try:
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
            self.update_status()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def update_task_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)

        # 根据筛选条件过滤任务
        filtered_tasks = self.tasks
        if self.filter_status == "未完成":
            filtered_tasks = [t for t in self.tasks if not t["completed"]]
        elif self.filter_status == "已完成":
            filtered_tasks = [t for t in self.tasks if t["completed"]]

        for t in filtered_tasks:
            status = "已完成" if t["completed"] else "未完成"
            self.task_tree.insert("", tk.END, values=(
                "√" if t["id"] in self.selected_tasks else "",
                t["id"], t["project"], t["short_desc"], t["priority"],
                t["create_time"], t["modified_time"], status
            ), tags=("completed" if t["completed"] else ("high_priority" if t["priority"]=="高" else ("medium_priority" if t["priority"]=="中" else "low_priority"))))
        # 确保字体为14号
        self.task_tree.tag_configure("completed", foreground="gray", font=("SimHei", 14, "italic"))
        self.task_tree.tag_configure("high_priority", foreground="red", font=("SimHei", 14))
        self.task_tree.tag_configure("medium_priority", foreground="orange", font=("SimHei", 14))
        self.task_tree.tag_configure("low_priority", foreground="green", font=("SimHei", 14))
        self.update_status()

    def update_status(self):
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t["completed"])
        selected = len(self.selected_tasks)
        self.status_var.set(f"任务总数: {total}, 已完成: {completed}, 选中: {selected}")

    def on_tree_click(self, event):
        if self.task_tree.identify_region(event.x, event.y) == "cell":
            item = self.task_tree.identify_row(event.y)
            col = self.task_tree.identify_column(event.x)
            if col == "#1":
                task_id = int(self.task_tree.item(item, "values")[1])
                if task_id in self.selected_tasks:
                    self.selected_tasks.remove(task_id)
                else:
                    self.selected_tasks.add(task_id)
                self.update_task_list()
                return "break"

    def on_tree_double_click(self, event):
        if self.task_tree.identify_region(event.x, event.y) == "cell":
            item = self.task_tree.identify_row(event.y)
            task_id = int(self.task_tree.item(item, "values")[1])
            self.show_task_detail(task_id)

    def on_history_double_click(self, event, task):
        """双击版本历史行，打印版本信息并打开文件夹"""
        # 1. 获取双击的行ID
        row_id = self.history_tree.identify_row(event.y)
        if not row_id:
            return  # 未点击有效行

        # 2. 提取该行的时间戳
        row_values = self.history_tree.item(row_id, "values")
        timestamp = row_values[0]

        # 3. 查找该版本的详细信息
        target_ver = None
        for ver in task["description_history"]:
            if ver["timestamp"] == timestamp:
                target_ver = ver
                break

        # 5. 打开任务文件夹（复用已有逻辑）
        self.open_task_folder(target_ver["folder_path"])

    def show_task_detail(self, task_id):
        self.current_task_id = task_id
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            messagebox.showwarning("警告", "任务不存在！")
            return

        detail_win = tk.Toplevel(self.root)
        detail_win.title(task["short_desc"])
        detail_win.geometry("900x700")
        detail_win.update_idletasks()
        x = (detail_win.winfo_screenwidth() - detail_win.winfo_width()) // 2
        y = 50
        detail_win.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(detail_win, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 状态信息        
        status_info = ttk.Frame(main_frame)
        status_info.pack(fill=tk.X, pady=5)
        status = "已完成" if task["completed"] else "未完成"
        status_color = "gray" if task["completed"] else "black"
        ttk.Label(status_info, text=f"状态: {status}", foreground=status_color, font=self.font).pack(side=tk.LEFT, padx=20)
        ttk.Label(status_info, text=f"项目: {task['project']}", font=self.font).pack(side=tk.LEFT, padx=20)
        priority_color = {"高":"red", "中":"orange", "低":"green"}
        ttk.Label(status_info, text=f"优先级: {task['priority']}", foreground=priority_color[task['priority']], font=self.font).pack(side=tk.LEFT)

        ttk.Label(main_frame, text=f"创建时间: {task['create_time']}", font=self.font).pack(anchor=tk.W, pady=5)
        ttk.Label(main_frame, text=f"最近修改: {task['modified_time']}", font=self.font).pack(anchor=tk.W, pady=10)

        ttk.Separator(main_frame).pack(fill=tk.X, pady=10)

        # 创建自定义 Treeview 样式（字体大小14）
        tree_style = ttk.Style()
        tree_style.configure("History.Treeview", font=("SimHei", 14), rowheight=40)  # 设置字体和大小

        # 历史版本展示区域
        history_frame = ttk.Frame(main_frame)
        history_frame.pack(fill=tk.BOTH, expand=True)

        # 历史版本Treeview
        history_columns = ("timestamp", "content")
        self.history_tree = ttk.Treeview(history_frame, columns=history_columns, show="headings", height=5, style="History.Treeview")
        self.history_tree.heading("timestamp", text="时间")
        self.history_tree.heading("content", text="详细描述")
        self.history_tree.column("timestamp", width=180, anchor=tk.CENTER, stretch=False)
        self.history_tree.column("content", width=400, stretch=True)

        # 使用 pack 布局 Treeview
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # 滚动条
        history_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscroll=history_scrollbar.set)

        # 修改：使用 pack 布局滚动条
        history_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # 填充版本数据（调试输出）
        versions = sorted(task["description_history"], key=lambda x: -x["version"])
        for ver in versions:
            self.history_tree.insert("", tk.END, values=(
                ver["timestamp"],
                ver["content"]
            ))

        self.history_tree.tag_configure("latest", background="#e6f7ff", font=self.font)
        self.history_tree.tag_configure("", font=self.font)  # 默认
        self.history_tree.bind("<Double-Button-1>", lambda e: self.on_history_double_click(e, task))

        # 描述显示区域
        desc_frame = ttk.Frame(main_frame)
        desc_frame.pack(fill=tk.X, pady=10)

        ttk.Label(desc_frame, text="详细描述（编辑）:", font=("SimHei", 14, "bold")).pack(anchor=tk.W, pady=5)

        # 获取最新版本内容
        latest_version = max(task["description_history"], key=lambda x: x["version"])
        self.desc_text = tk.Text(desc_frame, wrap=tk.WORD, height=15, font=self.font)
        self.desc_text.pack(fill=tk.BOTH, expand=True, pady=10)
        self.desc_text.config(state=tk.NORMAL)  # 默认可编辑
        self.latest_version_content = latest_version["content"]  # 记录最新版本内容（用于对比）

        # 滚动条
        scrollbar = ttk.Scrollbar(self.desc_text, orient=tk.VERTICAL, command=self.desc_text.yview)
        self.desc_text.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        # 定义保存逻辑
        def save_changes():
            new_desc = self.desc_text.get("1.0", tk.END).strip()
            if new_desc == self.latest_version_content:
                messagebox.showinfo("提示", "内容未变更，无需保存！")
                return

            # 生成新版本
            new_version_num = latest_version["version"] + 1

            # 生成文件夹
            folder_path = self.generate_folder_path(task["project"], task["short_desc"], str(new_version_num))
            if not self.create_folder_if_not_exists(folder_path):
                return

            self.open_task_folder(folder_path)

            new_version = {
                "version": new_version_num,
                "content": new_desc,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "修改",
                "folder_path" : folder_path
            }
            task["description_history"].append(new_version)
            task["modified_time"] = new_version["timestamp"]

            # 保存并更新任务列表
            self.save_tasks()
            self.update_task_list()

            # 刷新当前窗口（关闭后重新打开）
            detail_win.destroy()
            self.show_task_detail(task_id)

        # 仅保留“修改”和“关闭”按钮
        ttk.Button(button_frame, text="修改", command=save_changes).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="关闭", command=detail_win.destroy).pack(side=tk.RIGHT)

    def show_version_content(self, event, task):
        selection = self.history_tree.selection()
        if not selection:
            return
        item = self.history_tree.item(selection[0])
        version_num = int(item["values"][0].replace("v", ""))
        version = next((v for v in task["description_history"] if v["version"] == version_num), None)
        if version:
            # 判断是否是最新版本
            latest_version = max(task["description_history"], key=lambda x: x["version"])
            if version["version"] == latest_version["version"]:
                # 最新版本：允许编辑
                self.desc_text.config(state=tk.NORMAL)
                self.desc_text.delete("1.0", tk.END)
                self.desc_text.insert(tk.END, version["content"])
                self.desc_text.config(state=tk.DISABLED)
                self.version_info.set(f"当前显示: v{version['version']} ({version['timestamp']})")
                self.edit_btn.config(state=tk.NORMAL)
                self.save_btn.config(state=tk.DISABLED)
                self.cancel_btn.config(state=tk.DISABLED)
            else:
                # 历史版本：只读
                self.desc_text.config(state=tk.NORMAL)
                self.desc_text.delete("1.0", tk.END)
                self.desc_text.insert(tk.END, version["content"])
                self.desc_text.config(state=tk.DISABLED)
                self.version_info.set(f"当前显示: v{version['version']} ({version['timestamp']})")
                self.edit_btn.config(state=tk.DISABLED)
                self.save_btn.config(state=tk.DISABLED)
                self.cancel_btn.config(state=tk.DISABLED)

    def toggle_edit_mode(self):
        task = next((t for t in self.tasks if t["id"] == self.current_task_id), None)
        if not task:
            return
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择版本！")
            return
        item = self.history_tree.item(selection[0])
        current_version_num = int(item["values"][0].replace("v", ""))
        latest_version = max(task["description_history"], key=lambda x: x["version"])

        if current_version_num != latest_version["version"]:
            messagebox.showinfo("提示", "仅最新版本可编辑，请选择最新版本！")
            return

        self.is_editing = not self.is_editing
        if self.is_editing:
            self.desc_text.config(state=tk.NORMAL)
            self.edit_btn.config(text="取消编辑")
            self.save_btn.config(state=tk.NORMAL)
            self.cancel_btn.config(state=tk.NORMAL)
        else:
            self.desc_text.config(state=tk.DISABLED)
            self.edit_btn.config(text="修改描述")
            self.save_btn.config(state=tk.DISABLED)
            self.cancel_btn.config(state=tk.DISABLED)
            # 恢复最新版本内容
            self.show_version_content(None, task)

    def save_edited_desc(self):
        task = next((t for t in self.tasks if t["id"] == self.current_task_id), None)
        if not task:
            messagebox.showwarning("警告", "任务已删除！")
            return

        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择最新版本！")
            return
        item = self.history_tree.item(selection[0])
        current_version_num = int(item["values"][0].replace("v", ""))
        latest_version = max(task["description_history"], key=lambda x: x["version"])

        if current_version_num != latest_version["version"]:
            messagebox.showwarning("警告", "仅最新版本可编辑！")
            return

        new_desc = self.desc_text.get("1.0", tk.END).strip()
        if new_desc == latest_version["content"]:
            messagebox.showinfo("提示", "内容未变更！")
            self.toggle_edit_mode()
            return

        # 生成新版本
        new_version_num = latest_version["version"] + 1
        new_version = {
            "version": new_version_num,
            "content": new_desc,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "修改"
        }
        task["description_history"].append(new_version)
        task["modified_time"] = new_version["timestamp"]

        # 保存并更新UI
        self.save_tasks()
        self.update_task_list()

        # 更新历史版本Treeview
        self.history_tree.delete(*self.history_tree.get_children())
        versions = sorted(task["description_history"], key=lambda x: -x["version"])
        for ver in versions:
            self.history_tree.insert("", tk.END, values=(
                f"v{ver['version']}",
                ver["timestamp"],
                ver["action"]
            ))
        # 自动选中最新版本
        self.history_tree.selection_set(self.history_tree.get_children()[0])
        # 刷新描述显示
        self.show_version_content(None, task)
        self.toggle_edit_mode()

        messagebox.showinfo("成功", f"描述已更新为 v{new_version_num}")

    def cancel_edit(self):
        self.show_version_content(None, next((t for t in self.tasks if t["id"] == self.current_task_id), None))
        self.toggle_edit_mode()

    def show_version_comparison(self, task, version_num):
        if version_num == 1:
            messagebox.showinfo("提示", "无更早版本可对比！")
            return

        current_version = next((v for v in task["description_history"] if v["version"] == version_num), None)
        prev_version = next((v for v in task["description_history"] if v["version"] == version_num - 1), None)

        if not current_version or not prev_version:
            messagebox.showwarning("警告", "版本信息丢失！")
            return

        # 对比窗口
        compare_win = tk.Toplevel(self.root)
        compare_win.title(f"版本对比 v{prev_version['version']} → v{current_version['version']}")
        compare_win.geometry("900x500")
        compare_win.resizable(True, True)

        compare_win.update_idletasks()
        x = (compare_win.winfo_screenwidth() - compare_win.winfo_width()) // 2
        y = 100
        compare_win.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(compare_win, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 旧版本显示
        ttk.Label(main_frame, text=f"v{prev_version['version']} ({prev_version['timestamp']})", font=("SimHei", 14, "bold")).pack(anchor=tk.W)
        prev_text = tk.Text(main_frame, wrap=tk.WORD, height=14, font=("SimHei", 14))
        prev_text.pack(fill=tk.BOTH, expand=True, pady=5)
        prev_text.insert(tk.END, prev_version["content"])
        prev_text.config(state=tk.DISABLED)

        # 新版本显示
        ttk.Label(main_frame, text=f"v{current_version['version']} ({current_version['timestamp']})", font=("SimHei", 14, "bold")).pack(anchor=tk.W)
        curr_text = tk.Text(main_frame, wrap=tk.WORD, height=14, font=("SimHei", 14))
        curr_text.pack(fill=tk.BOTH, expand=True, pady=5)
        curr_text.insert(tk.END, current_version["content"])
        curr_text.config(state=tk.DISABLED)

        # 差异显示
        diff_text = tk.Text(main_frame, wrap=tk.WORD, height=5, font=("SimHei", 14), bg="#f0f0f0")
        diff_text.pack(fill=tk.BOTH, expand=True, pady=5)

        prev_lines = prev_version["content"].splitlines()
        curr_lines = current_version["content"].splitlines()
        diff = difflib.unified_diff(prev_lines, curr_lines, lineterm='')

        diff_summary = []
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                diff_summary.append(f"新增: {line[1:]}")
            elif line.startswith('-') and not line.startswith('---'):
                diff_summary.append(f"删除: {line[1:]}")

        if not diff_summary:
            diff_text.insert(tk.END, "无变更")
        else:
            diff_text.insert(tk.END, "\n".join(diff_summary))

        diff_text.config(state=tk.DISABLED)
        ttk.Button(main_frame, text="关闭", command=compare_win.destroy).pack(anchor=tk.E, pady=10)

    def open_add_task_window(self):
        """打开添加任务的子界面"""
        add_window = tk.Toplevel(self.root)
        add_window.title("添加新任务")
        add_window.geometry("500x350")
        add_window.resizable(True, True)

        # 设置窗口位置在屏幕上方居中
        add_window.update_idletasks()
        screen_width = add_window.winfo_screenwidth()
        screen_height = add_window.winfo_screenheight()
        x = (screen_width - add_window.winfo_width()) // 2
        y = 100
        add_window.geometry(f"+{x}+{y}")

        # 设置窗口始终在最上层
        # add_window.wm_attributes("-topmost", True)

        # 创建添加任务界面
        frame = ttk.Frame(add_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # 配置框架的行列权重
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=0)  # 标题行
        frame.rowconfigure(1, weight=0)  # 项目名称行
        frame.rowconfigure(2, weight=0)  # 简易描述行
        frame.rowconfigure(3, weight=0)  # 优先级行
        frame.rowconfigure(4, weight=1)  # 详细描述行
        frame.rowconfigure(5, weight=0)  # 按钮行

        # 标题
        title_label = ttk.Label(frame, text="添加新任务", font=("SimHei", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky="nsew")

        # 项目名称
        ttk.Label(frame, text="项目名称:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        project_var = tk.StringVar()
        project_entry = ttk.Entry(frame, textvariable=project_var, width=30)
        project_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # 简易描述
        ttk.Label(frame, text="简易描述:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        short_var = tk.StringVar()
        short_entry = ttk.Entry(frame, textvariable=short_var, width=30)
        short_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # 优先级
        ttk.Label(frame, text="优先级:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        priority_var = tk.StringVar(value="中")
        priority_combo = ttk.Combobox(frame, textvariable=priority_var, 
                                     values=["高", "中", "低"], state="readonly", width=10)
        priority_combo.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)

        # 详细描述
        ttk.Label(frame, text="详细描述:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.NW)
        long_text = tk.Text(frame, wrap=tk.WORD, height=6, width=30)
        long_text.grid(row=4, column=1, padx=5, pady=5, sticky="nsew")

        # 添加滚动条
        scrollbar = ttk.Scrollbar(long_text, orient=tk.VERTICAL, command=long_text.yview)
        long_text.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ttk.Label(frame, text="文件夹路径:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        # folder_var = tk.StringVar()
        # folder_entry = ttk.Entry(frame, textvariable=folder_var, width=30)
        # folder_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")

        # def browse_folder():
        #     folder_selected = filedialog.askdirectory()
        #     if folder_selected:
        #         folder_var.set(folder_selected)

        # ttk.Button(frame, text="浏览...", command=browse_folder).grid(row=5, column=2, padx=5, pady=5)

        # 按钮区域
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=15, sticky="nsew")

        # 添加按钮
        def add_task():
            project = project_var.get().strip() or "未分类"
            short = short_var.get().strip()
            if not short:
                messagebox.showwarning("警告", "简易描述不能为空！")
                return
            long = long_text.get("1.0", tk.END).strip()
            priority = priority_var.get()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            folder_path = self.generate_folder_path(project, short, "1")
            if not self.create_folder_if_not_exists(folder_path):
                return

            new_task = {
                "id": len(self.tasks)+1,
                "project": project,
                "short_desc": short,
                "priority": priority,
                "create_time": now,
                "modified_time": now,
                "completed": False,
                "description_history": [{"version": 1, "content": long, "timestamp": now, "action": "创建", "folder_path" : folder_path}]
            }

            self.tasks.append(new_task)
            self.save_tasks()

            self.open_task_folder(folder_path)
            self.update_task_list()

            # 关闭窗口
            add_window.destroy()

            # 显示成功消息
            messagebox.showinfo("成功", "任务已添加！")

        ttk.Button(button_frame, text="添加", command=add_task).pack(side=tk.LEFT, padx=(0, 10))

        # 取消按钮
        ttk.Button(button_frame, text="取消", command=add_window.destroy).pack(side=tk.RIGHT)

    def get_selected_task_ids(self):
        if not self.selected_tasks:
            messagebox.showwarning("警告", "请先选择任务！")
            return []
        return list(self.selected_tasks)

    def select_all_tasks(self):
        self.selected_tasks = {t["id"] for t in self.tasks}
        self.update_task_list()

    def invert_selection(self):
        all_ids = {t["id"] for t in self.tasks}
        self.selected_tasks = all_ids - self.selected_tasks
        self.update_task_list()

    def mark_tasks_completed(self):
        task_ids = self.get_selected_task_ids()
        if not task_ids:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for tid in task_ids:
            for t in self.tasks:
                if t["id"] == tid:
                    t["completed"] = not t["completed"]
                    t["modified_time"] = now
                    break
        self.save_tasks()
        self.update_task_list()

    def delete_tasks(self):
        task_ids = self.get_selected_task_ids()
        if not task_ids:
            return
        descs = [next((t["short_desc"] for t in self.tasks if t["id"]==tid), "未知任务") for tid in task_ids]
        desc_text = f"{descs[0]}等{len(descs)}个任务" if len(descs)>3 else "、".join(descs)
        if messagebox.askyesno("确认", f"确定删除以下任务？\n{desc_text}"):
            self.tasks = [t for t in self.tasks if t["id"] not in task_ids]
            self.selected_tasks = {tid for tid in self.selected_tasks if tid in {t["id"] for t in self.tasks}}
            for i, t in enumerate(self.tasks, 1):
                t["id"] = i
            self.save_tasks()
            self.update_task_list()

    def clear_completed_tasks(self):
        if not any(t["completed"] for t in self.tasks):
            messagebox.showinfo("提示", "无已完成任务！")
            return
        if messagebox.askyesno("确认", "确定清除所有已完成任务？"):
            self.tasks = [t for t in self.tasks if not t["completed"]]
            self.selected_tasks = {tid for tid in self.selected_tasks if tid in {t["id"] for t in self.tasks}}
            for i, t in enumerate(self.tasks, 1):
                t["id"] = i
            self.save_tasks()
            self.update_task_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = TaskManager(root)
    root.mainloop()
