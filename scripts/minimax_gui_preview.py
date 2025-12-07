#!/usr/bin/env python3
"""
Minimal GUI for running CSV-based TTS generation.
Current behavior: choose CSV and output dir, then run minimax_from_csv.py.
Logs are shown in the GUI text area.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


def get_base_dir() -> str:
    # PyInstaller --onefile extracts to _MEIPASS; fallback to repo relative.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


BASE_DIR = get_base_dir()
DEFAULT_CONFIG = os.path.join(BASE_DIR, "configs", "tts.json")
MINIMAX_FROM_CSV = os.path.join(BASE_DIR, "scripts", "minimax_from_csv.py")


class TTSGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MiniMax TTS GUI (Preview)")
        self.geometry("620x420")

        self.csv_path: str = ""
        self.out_dir: str = ""

        # CSV selection
        self.csv_label = tk.Label(self, text="CSV: (未選択)", anchor="w", justify="left")
        self.csv_label.pack(fill="x", padx=10, pady=(10, 2))
        tk.Button(self, text="CSVを選択", command=self.select_csv).pack(padx=10, pady=4)

        # Output directory selection
        self.out_dir_label = tk.Label(self, text="出力フォルダ: (未選択)", anchor="w", justify="left")
        self.out_dir_label.pack(fill="x", padx=10, pady=(12, 2))
        tk.Button(self, text="出力フォルダを選択", command=self.select_out_dir).pack(padx=10, pady=4)

        # Run button
        tk.Button(self, text="実行", command=self.run_batch, bg="#4CAF50", fg="white").pack(padx=10, pady=12)

        # Log area
        self.log_box = scrolledtext.ScrolledText(self, height=10, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=6)

    def select_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="CSVファイルを選択",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.csv_path = path
            self.csv_label.config(text=f"CSV: {path}")

    def select_out_dir(self) -> None:
        path = filedialog.askdirectory(title="出力フォルダを選択")
        if path:
            self.out_dir = path
            self.out_dir_label.config(text=f"出力フォルダ: {path}")

    def append_log(self, message: str) -> None:
        self.log_box.config(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def run_batch(self) -> None:
        if not self.csv_path:
            messagebox.showwarning("CSV未選択", "先にCSVファイルを選んでください。")
            return
        if not self.out_dir:
            messagebox.showwarning("出力フォルダ未選択", "先に出力フォルダを選んでください。")
            return
        if not os.path.exists(DEFAULT_CONFIG):
            messagebox.showerror("configが見つかりません", f"{DEFAULT_CONFIG} を確認してください。")
            return
        if not os.path.exists(MINIMAX_FROM_CSV):
            messagebox.showerror("スクリプトが見つかりません", f"{MINIMAX_FROM_CSV} がありません。")
            return
        if not os.getenv("MINIMAX_API_KEY"):
            messagebox.showwarning("MINIMAX_API_KEY 未設定", "先に .env を読み込むか環境変数をセットしてください。")
            return

        self.append_log(f"開始: csv={self.csv_path}, out_dir={self.out_dir}")
        thread = threading.Thread(target=self._run_subprocess, daemon=True)
        thread.start()

    def _run_subprocess(self) -> None:
        cmd = [
            sys.executable,
            MINIMAX_FROM_CSV,
            self.csv_path,
            "--config",
            DEFAULT_CONFIG,
            "--out-dir",
            self.out_dir,
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self.after(0, lambda: messagebox.showerror("実行エラー", f"プロセス起動に失敗しました: {exc}"))
            return

        if proc.stdout:
            for line in proc.stdout:
                self.after(0, lambda l=line.rstrip(): self.append_log(l))

        proc.wait()
        if proc.returncode == 0:
            self.after(0, lambda: messagebox.showinfo("完了", "バッチ処理が完了しました。"))
        else:
            self.after(
                0,
                lambda: messagebox.showerror("失敗", f"バッチ処理に失敗しました (returncode={proc.returncode})"),
            )


def main() -> None:
    # On WSL/GUI-less environments, this may fail; catch and warn.
    try:
        app = TTSGui()
        app.mainloop()
    except tk.TclError as exc:
        print("GUI起動に失敗しました。ディスプレイ環境を確認してください。")
        print(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
