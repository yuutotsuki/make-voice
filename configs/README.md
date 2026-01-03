# MiniMax TTS 設定メモ (configs/tts.json)

## 使い方
- 実行例（デフォルト設定を使用）  
  `python scripts/minimax_tts.py scripts/test_script.txt --config configs/tts.json --out output.mp3`
- 事前に `MINIMAX_API_KEY` を環境変数で設定すること。
- CLI で指定した値は JSON より優先される（例: `--model ...` を渡すと JSON の model よりそちらが使われる）。

## tts.json の主な項目
- `base_url`: 通常は `https://api.minimax.io/v1/t2a_v2`。TTFA を使う場合は `https://api-uw.minimax.io/v1/t2a_v2` に変更。
- `model`: `speech-2.6-hd`（高品質）。スピード重視なら `speech-2.6-turbo`。
- `output_format`: `hex` 推奨。`url` にすると返却 URL をダウンロードする挙動になる。
- `voice_setting`
  - `voice_id`: 使用する声の ID。例: `Japanese_DecisivePrincess`。
  - `speed`: 話速 0.5–2.0。1.0 標準、1.1–1.2 元気め、0.9 落ち着き。
  - `vol`: 音量。通常 1.0 でOK。
  - `pitch`: 高さ。大きくすると明るめ/若め、下げると落ち着き。
  - `emotion`: 例 `calm` / `cheerful` / `excited` など（モデル対応が必要）。
  - `text_normalization` / `latex_read`: 特殊読みが必要な場合のみ true。
- `audio_setting`
  - `format`: `mp3` 推奨。非ストリーミングで `wav` も可。
  - `sample_rate`: 32000 デフォルト。クリアさ重視なら 44100。
  - `bitrate`: `128000`（mp3 の場合）。用途に応じて上下。
  - `channel`: 1=モノラル、2=ステレオ。
  - `force_cbr`: ストリーミング mp3 の CBR を強制したいときのみ true。
- `voice_modify`
  - `pitch` / `intensity` / `timbre`: 声質の後掛け調整。小さめ(0.1〜0.3)で軽く色付け。
  - `sound_effects`: `spacious_echo` / `auditorium_echo` / `lofi_telephone` / `robotic` など。未使用なら null。
- `language_boost`: 読み上げ言語の優先。日本語なら `Japanese` のままでOK。
- `subtitle_enable`: 非ストリーミング時に字幕 JSON を返すか。不要なら false。
- `pronunciation_dict`: 単語ごとの読みを固定したいときに設定（例: `"tone": ["omg/oh my god"]`）。
- `timbre_weights`: 複数 voice のミックス用。未使用なら空配列のまま。

## よく触る調整ポイント（推奨）
- 話速: `voice_setting.speed` を 0.95–1.05 の間で微調整。
- 高さ: `voice_setting.pitch` を +2〜+3 で明るめ、-2 で落ち着き。
- 感情: `voice_setting.emotion` を `calm` / `cheerful` / `excited` などで試す。
- 仕上げ: `voice_modify.pitch/intensity/timbre` を 0.1〜0.3 にして軽く色付け。

## 注意
- JSON はコメント不可。説明はこの README に記載。
- CLI で `--model` や `--voice-id` を渡すと、JSON の値より優先される。

## emotion の補足
- 指定可能: `happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`, `calm`, `fluent`, `whisper`
- デフォルトではテキストに応じて自動選択される。明示指定が必要なときのみ設定する。
- 対応モデル: `speech-2.6-hd`, `speech-2.6-turbo`, `speech-02-hd`, `speech-02-turbo`, `speech-01-hd`, `speech-01-turbo`
- `fluent`, `whisper` は `speech-2.6-hd` / `speech-2.6-turbo` のみ対応。

## CSV バッチ実行 (minimax_from_csv.py)
- コマンド例  
  `python scripts/minimax_from_csv.py data/lines.csv --config configs/tts.json --out-dir voice/`
- CSVヘッダー（この順・名称で用意すること）  
  `no, filename, text, voice_id, speed, pitch, emotion, notes, output`
- 行ごとに上書きできるのは `voice_id` / `speed` / `pitch` / `emotion` のみ。空セルは configs/tts.json をそのまま使う。  
- `text` が空の行はスキップ。  
- ファイル名の決定: `filename` があればそれを使用。なければ `line_{no}`、それも無ければ `line_{row_index}`（1始まり）。拡張子は自動で `.mp3` 付与。  
- `--out-dir` は存在しなければ自動作成。デフォルトは `voice/`。
- `output` が空でない行はスキップ（書き戻しは行わない）。
