#!/usr/bin/env python3
"""
Minimal GUI (preview) for running CSV-based TTS generation.
Stage 1: only prints selected CSV path and output dir when "実行" is clicked.

Next step (after confirming GUI works): wire this to minimax_from_csv.py.
"""

import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox


class TTSGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MiniMax TTS GUI (Preview)")
        self.geometry("520x220")

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
        tk.Button(self, text="実行 (ドライラン)", command=self.run_preview, bg="#4CAF50", fg="white").pack(
            padx=10, pady=16
        )

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

    def run_preview(self) -> None:
        if not self.csv_path:
            messagebox.showwarning("CSV未選択", "先にCSVファイルを選んでください。")
            return
        if not self.out_dir:
            messagebox.showwarning("出力フォルダ未選択", "先に出力フォルダを選んでください。")
            return
        # Stage 1: just print the values (no TTS execution).
        print(f"csv={self.csv_path}")
        print(f"out_dir={self.out_dir}")
        messagebox.showinfo("ドライラン完了", "ターミナル出力を確認してください。")


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
