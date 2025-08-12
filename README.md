# communication-protocol

Python による空気伝搬音 (超音波/可聴域高周波) を使った簡易データ通信デモです。2 周波数による FSK (Frequency Shift Keying) と任意選択のマンチェスター符号化、簡易 MAC (宛先 / 送信元 ID & 長さフィールド) とパリティ(行/列)による誤り検出／一部訂正表示、ACK/NACK 応答までを 1 台の PC + マイク/スピーカーで体験できます。

## 主な機能
- 2-FSK 変調 / 相関による周波数パワー検出
- オプション: マンチェスター符号化 (実効ビットレート 1/2)
- シンプルなフレーム構造: PREAMBLE | 宛先ID | 送信元ID | 長さ | ペイロード | パリティ
- 行/列 (偶数) パリティ生成・検査 (エラー位置の可視化)
- ACK (11) / NACK (00) フレーム返信
- 初期しきい値キャリブレーション
- 受信中リアルタイムプロット (matplotlib)
- 対話コマンドによる状態制御

## ファイル構成
| ファイル | 役割 |
|----------|------|
| `communicationControl.py` | 物理/データリンク層ロジック (FSK 生成/解析, 変調復調, フレーミング, パリティ) |
| `ultrasound_main.py` | 実行エントリ。音声 I/O, 状態遷移, プロット, 対話制御 |
| `test1.txt` `test2.txt` `test3.txt` | 送信用ビット列サンプル (カンマ区切り) |
| `README.md` | この説明 |

## 依存関係
Python 3.9+ を推奨。

必須ライブラリ:
- numpy
- pyaudio (PortAudio 依存 / macOS では `brew install portaudio` が必要な場合あり)
- matplotlib

### インストール例 (macOS / zsh)
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install numpy pyaudio matplotlib
# pyaudio のビルドに失敗する場合は: brew install portaudio && export LDFLAGS="-L/opt/homebrew/lib" && export CFLAGS="-I/opt/homebrew/include"
```

## パラメータ (抜粋: `ultrasound_main.py` 冒頭)
| 変数 | 意味 | 既定値 |
|------|------|--------|
| `FREQUENCY0` | ビット 0 周波数 | 2500 Hz |
| `FREQUENCY1` | ビット 1 周波数 | 3500 Hz |
| `BPS` | ビット毎秒 (マンチェスター有効時 実効 1/2) | 50 |
| `IS_MANCHESTER` | マンチェスター符号化使用 | True |
| `SAMPLING_RATE` | サンプリングレート | 48000 |
| `CHUNK` | 1 回処理サンプル数 | 8192 (macOS) |
| `VOLUME` | 送信音量 (0-1) | 0.7 |

## フレーム構造 (送信データ)
```
Preamble (0001) |
Dest ID (4bit) |
Src ID (4bit) |
Length (8bit: ペイロード長 bit 数) |
Payload (可変) |
Parity (行/列+全体)  
```

ACK/NACK は簡略化され `0001` + `11` (ACK) / `00` (NACK) のみを送出します。

## テキスト送信ファイル形式
カンマ区切りビット列。例 (`test1.txt`):
```
0,0,1,1
0,0,1,1
0,1,0
...
```
改行は無視され順次連結されます。数字以外があればスキップされます。

## 実行手順
1. 依存ライブラリをインストール
2. マイク/スピーカー (ループバックや 2 台間でも可) を準備し音量を適切に調整
3. 初期キャリブレーション (受信環境ノイズしきい値学習)
4. 送信 or 受信を開始

### 起動
```bash
python ultrasound_main.py
```

### 対話コマンド (標準入力)
| コマンド | 動作 |
|----------|------|
| `i` | 初期化 (内部しきい値リセット) |
| `c` | キャリブレーション (一定時間録音してしきい値計算) |
| `r` | 受信モード開始 |
| `t{n}` | 送信: `test{n}.txt` (1〜3)。数字省略/不正時は `test1.txt` |
| `p` | 現在状態表示 |
| `e` | 終了 |

送信後は WAIT_ACKNACK 状態で ACK/NACK を 1 フレーム待機し、受信後 RX に戻ります。

### 推奨ワークフロー例
```text
1) 起動直後 'c' でキャリブレーション
2) 'r' で受信待機 (相手が送信するか自分で送信テスト)
3) 't1' でサンプル送信 -> ACK/NACK 確認
4) 必要に応じて周波数や BPS を調整
```

## 受信ログ/可視化
- 下段グラフ: 周波数0/1 の相関累積値と判定データ (-1=無信号)
- エラーフレームではパリティマトリクスが色付き (ターミナルの ANSI エスケープ) で表示されます。

## 実装レイヤ概要
| レイヤ | 関数 (主) | 内容 |
|--------|-----------|------|
| PHY | `phy_layer_tx`, `phy_layer_rx`, `frequency_analysis_rx` | FSK 波形生成 / 相関によるデモジュレーション / マンチェスター復号 |
| MAC | `mac_layer_tx`, `mac_layer_rx` | フレーム生成, ID/長さ抽出, パリティ検証, ACK/NACK 判定 |
| Network | pass-through | 1 対 1 のため透過 |

## 既知の制限 / 今後の改善案
- パリティは 1bit 誤り推定表示のみ (訂正は未適用)
- しきい値は単純最大値ベースで環境変化への追従が弱い → 移動平均/適応閾値化
- ノイズ除去は近傍置換の簡易フィルタ → Viterbi 等導入可能
- ACK/NACK フレームに ID/長さなし (拡張余地)
- 長さフィールドはビット数指定でバイト境界未整合

## トラブルシュート
| 症状 | 対処 |
|------|------|
| pyaudio のビルド失敗 | `brew install portaudio` し環境変数で include/lib パスを追加 |
| 受信が常に空 | キャリブレーション再実行 (`c`)、音量調整、周波数干渉確認 |
| ACK/NACK が返らない | 相手側が RX 状態か、マイク/スピーカーのミュートを確認 |
| グラフが表示されない | `matplotlib` backend が利用不可の場合は `matplotlib.use('TkAgg')` などに変更 |