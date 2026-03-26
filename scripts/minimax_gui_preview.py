#!/usr/bin/env python3
"""
Minimal GUI for running CSV-based TTS generation.

The GUI shells out to the CSV batch runner in a separate process so the user
can cancel a run without killing the GUI itself.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import ctypes
import ctypes.wintypes

import minimax_from_csv


def get_base_dir() -> str:
    # PyInstaller --onefile extracts to _MEIPASS; fallback to repo relative.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


BASE_DIR = get_base_dir()
DEFAULT_CONFIG = os.path.join(BASE_DIR, "configs", "tts.json")
API_KEY_ENV = "MINIMAX_API_KEY"
APP_STATE_DIR = os.path.join(os.path.expanduser("~"), ".minimax_gui_preview")
API_KEY_FILE = os.path.join(APP_STATE_DIR, "minimax_api_key.bin")


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _is_windows() -> bool:
    return os.name == "nt"


def _protect_data(plain_text: str) -> bytes:
    if not _is_windows():
        raise RuntimeError("DPAPI is available only on Windows.")
    if not plain_text:
        raise ValueError("API key is empty.")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data = plain_text.encode("utf-8")
    in_buffer = ctypes.create_string_buffer(data)
    in_blob = _DATA_BLOB(len(data), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()

    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "MiniMax API Key",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise RuntimeError("CryptProtectData failed.")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def _unprotect_data(cipher_text: bytes) -> str:
    if not _is_windows():
        raise RuntimeError("DPAPI is available only on Windows.")
    if not cipher_text:
        raise ValueError("Encrypted API key is empty.")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buffer = ctypes.create_string_buffer(cipher_text, len(cipher_text))
    in_blob = _DATA_BLOB(len(cipher_text), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()

    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise RuntimeError("CryptUnprotectData failed.")

    try:
        plain_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)

    return plain_bytes.decode("utf-8")


def load_saved_api_key() -> str:
    if not os.path.exists(API_KEY_FILE):
        return ""
    try:
        with open(API_KEY_FILE, "rb") as f:
            encrypted = f.read()
        return _unprotect_data(encrypted).strip()
    except Exception:
        return ""


def save_api_key(api_key: str) -> None:
    os.makedirs(APP_STATE_DIR, exist_ok=True)
    encrypted = _protect_data(api_key)
    with open(API_KEY_FILE, "wb") as f:
        f.write(encrypted)


def delete_saved_api_key() -> None:
    if os.path.exists(API_KEY_FILE):
        os.remove(API_KEY_FILE)


class ApiKeyDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, initial_key: str = "", allow_delete: bool = False) -> None:
        super().__init__(parent)
        self.title("APIキー設定")
        self.resizable(False, False)
        self.result_key = ""
        self.result_save = False
        self.result_delete = False

        self.transient(parent)
        self.grab_set()

        frame = tk.Frame(self, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="MINIMAX_API_KEY を入力してください:").pack(anchor="w")
        self.entry = tk.Entry(frame, width=56, show="*")
        self.entry.pack(fill="x", pady=(6, 10))
        if initial_key:
            self.entry.insert(0, initial_key)
        self.entry.focus_set()

        self.save_var = tk.BooleanVar(value=True)
        if _is_windows():
            save_text = "このPCに保存する (Windows DPAPIで暗号化)"
        else:
            save_text = "このPCに保存する"
        tk.Checkbutton(frame, text=save_text, variable=self.save_var).pack(anchor="w")

        button_frame = tk.Frame(frame)
        button_frame.pack(fill="x", pady=(12, 0))

        tk.Button(button_frame, text="キャンセル", command=self._on_cancel).pack(side="right", padx=(8, 0))
        tk.Button(button_frame, text="保存", command=self._on_ok).pack(side="right")
        if allow_delete:
            tk.Button(button_frame, text="削除", command=self._on_delete).pack(side="left")

        self.bind("<Return>", lambda _: self._on_ok())
        self.bind("<Escape>", lambda _: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _on_ok(self) -> None:
        api_key = self.entry.get().strip()
        if not api_key:
            messagebox.showwarning("入力不足", "APIキーを入力してください。", parent=self)
            return
        self.result_key = api_key
        self.result_save = bool(self.save_var.get())
        self.destroy()

    def _on_cancel(self) -> None:
        self.result_key = ""
        self.result_save = False
        self.result_delete = False
        self.destroy()

    def _on_delete(self) -> None:
        self.result_key = ""
        self.result_save = False
        self.result_delete = True
        self.destroy()


class TTSGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MiniMax TTS GUI (Preview)")
        self.geometry("620x420")

        self.csv_path: str = ""
        self.out_dir: str = ""
        self.process: subprocess.Popen[str] | None = None
        self.stop_requested = False

        # Load saved key first so users can run the GUI without CLI setup.
        if not os.getenv(API_KEY_ENV):
            saved_key = load_saved_api_key()
            if saved_key:
                os.environ[API_KEY_ENV] = saved_key

        # CSV selection
        self.csv_label = tk.Label(self, text="CSV: (未選択)", anchor="w", justify="left")
        self.csv_label.pack(fill="x", padx=10, pady=(10, 2))
        tk.Button(self, text="CSVを選択", command=self.select_csv).pack(padx=10, pady=4)

        # Output directory selection
        self.out_dir_label = tk.Label(self, text="出力フォルダ: (未選択)", anchor="w", justify="left")
        self.out_dir_label.pack(fill="x", padx=10, pady=(12, 2))
        tk.Button(self, text="出力フォルダを選択", command=self.select_out_dir).pack(padx=10, pady=4)

        # Run controls
        button_frame = tk.Frame(self)
        button_frame.pack(padx=10, pady=12)
        self.run_button = tk.Button(button_frame, text="実行", command=self.run_batch, bg="#4CAF50", fg="white")
        self.run_button.pack(side="left", padx=(0, 8))
        self.stop_button = tk.Button(button_frame, text="停止", command=self.stop_batch, state="disabled")
        self.stop_button.pack(side="left")
        self.api_key_button = tk.Button(button_frame, text="APIキー設定", command=self.manage_api_key)
        self.api_key_button.pack(side="left", padx=(8, 0))

        # Log area
        self.log_box = scrolledtext.ScrolledText(self, height=10, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=6)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

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

    def set_running_state(self, running: bool) -> None:
        self.run_button.config(state="disabled" if running else "normal")
        self.stop_button.config(state="normal" if running else "disabled")

    def build_batch_command(self) -> list[str]:
        argv = [
            "--run-batch",
            self.csv_path,
            "--config",
            DEFAULT_CONFIG,
            "--out-dir",
            self.out_dir,
        ]
        if getattr(sys, "frozen", False):
            return [sys.executable, *argv]
        return [sys.executable, "-u", os.path.abspath(__file__), *argv]

    def run_batch(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("実行中", "現在バッチ処理を実行中です。")
            return
        if not self.csv_path:
            messagebox.showwarning("CSV未選択", "先にCSVファイルを選んでください。")
            return
        if not self.out_dir:
            messagebox.showwarning("出力フォルダ未選択", "先に出力フォルダを選んでください。")
            return
        if not os.path.exists(DEFAULT_CONFIG):
            messagebox.showerror("configが見つかりません", f"{DEFAULT_CONFIG} を確認してください。")
            return
        if not self.ensure_api_key():
            return

        self.stop_requested = False
        self.set_running_state(True)
        self.append_log(f"開始: csv={self.csv_path}, out_dir={self.out_dir}")
        thread = threading.Thread(target=self._run_subprocess, daemon=True)
        thread.start()

    def stop_batch(self) -> None:
        process = self.process
        if not process or process.poll() is not None:
            return
        if not messagebox.askyesno("停止確認", "現在の音声生成を停止しますか？"):
            return
        self.stop_requested = True
        self.append_log("停止要求を送信しました。処理を中断します...")
        try:
            process.terminate()
        except OSError as exc:
            self.append_log(f"[warn] 停止要求の送信に失敗しました: {exc}")

    def _read_process_output(self, process: subprocess.Popen[str]) -> None:
        if not process.stdout:
            return
        for line in process.stdout:
            message = line.rstrip("\r\n")
            if message:
                self.after(0, lambda m=message: self.append_log(m))

    def _run_subprocess(self) -> None:
        command = self.build_batch_command()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=os.environ.copy(),
            )
            self.process = process
            self._read_process_output(process)
            return_code = process.wait()
            if self.stop_requested:
                self.after(0, lambda: self.append_log("処理を停止しました。"))
                self.after(0, lambda: messagebox.showinfo("停止", "バッチ処理を停止しました。"))
            elif return_code == 0:
                self.after(0, lambda: messagebox.showinfo("完了", "バッチ処理が完了しました。"))
            else:
                self.after(0, lambda c=return_code: messagebox.showerror("失敗", f"バッチ処理に失敗しました (code={c})"))
        except Exception as exc:  # pragma: no cover
            self.after(0, lambda e=exc: messagebox.showerror("失敗", f"エラーが発生しました: {e}"))
        finally:
            self.process = None
            self.after(0, lambda: self.set_running_state(False))

    def on_close(self) -> None:
        process = self.process
        if process and process.poll() is None:
            if not messagebox.askyesno("終了確認", "実行中の処理を停止してウィンドウを閉じますか？"):
                return
            self.stop_requested = True
            try:
                process.terminate()
            except OSError:
                pass
        self.destroy()

    def ensure_api_key(self) -> bool:
        current = (os.getenv(API_KEY_ENV) or "").strip()
        if current:
            return True

        dialog = ApiKeyDialog(self)
        self.wait_window(dialog)

        if not dialog.result_key:
            self.append_log("[warn] APIキー未設定のため処理を開始できませんでした。")
            return False

        os.environ[API_KEY_ENV] = dialog.result_key

        if dialog.result_save:
            try:
                save_api_key(dialog.result_key)
                self.append_log("[info] APIキーをローカルに保存しました。")
            except Exception as exc:
                messagebox.showwarning(
                    "保存に失敗",
                    f"APIキーの保存に失敗しました。今回の実行には利用できます。\n{exc}",
                )
                self.append_log(f"[warn] APIキー保存に失敗しました: {exc}")

        return True

    def manage_api_key(self) -> None:
        current = (os.getenv(API_KEY_ENV) or "").strip()
        dialog = ApiKeyDialog(self, initial_key=current, allow_delete=True)
        self.wait_window(dialog)

        if dialog.result_delete:
            os.environ.pop(API_KEY_ENV, None)
            try:
                delete_saved_api_key()
                self.append_log("[info] 保存済みAPIキーを削除しました。")
                messagebox.showinfo("APIキー削除", "保存済みAPIキーを削除しました。")
            except OSError as exc:
                messagebox.showwarning("削除に失敗", f"APIキーの削除に失敗しました。\n{exc}")
            return

        if not dialog.result_key:
            return

        os.environ[API_KEY_ENV] = dialog.result_key
        if dialog.result_save:
            try:
                save_api_key(dialog.result_key)
                self.append_log("[info] APIキーを更新しました。")
                messagebox.showinfo("APIキー更新", "APIキーを更新しました。")
            except Exception as exc:
                messagebox.showwarning(
                    "保存に失敗",
                    f"APIキーの保存に失敗しました。今回の実行には利用できます。\n{exc}",
                )
                self.append_log(f"[warn] APIキー更新の保存に失敗しました: {exc}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--run-batch":
        minimax_from_csv.main(sys.argv[2:])
        return

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
