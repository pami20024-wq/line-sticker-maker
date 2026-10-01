# LINE Sticker Maker

添付のような基準キャラクターから、静止画LINEスタンプ24個を生成し、文字入れ、画像最適化、検証、ZIP化まで行うPythonツールです。AIには日本語を書かせず、文字はPillowで確実に合成します。途中で再実行すると完成済みの番号をスキップするため、そのまま再開できます。

> **費用について:** 通常生成はOpenAI Image APIを24回前後利用し、API利用料が発生します。まず `--demo` でローカル処理を確認することを推奨します。

## ファイル構成

```text
config.yaml                 モデル、フォント、サイズなどの設定
stickers.yaml               24個の文言・表情・ポーズ
generate.py                 生成、加工、preview・ZIP作成
validation.py               LINE画像仕様の検証
sticker_maker/              API・画像処理モジュール
reference.png               利用者が置く基準画像（Git管理外）
raw_images/                 APIの生成原画・自動identity画像（Git管理外）
line_stickers/              完成画像（Git管理外）
```

## 1. Pythonの準備（Mac）

Python 3.11以上を使用します。透過処理に利用するsprite-genの対応バージョンに合わせています。ターミナルで確認してください。

```bash
python3 --version
```

入っていなければ [Python公式サイト](https://www.python.org/downloads/macos/) からインストールするか、Homebrewを使います。

```bash
brew install python
```

プロジェクトへ移動し、他のPython環境を汚さない仮想環境を作ります。

```bash
cd /path/to/line-sticker-maker
python3 -m venv .venv
source .venv/bin/activate
```

## 2. ライブラリのインストール

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. APIキー設定

[OpenAI API keys](https://platform.openai.com/api-keys) でキーを作成します。キーをソースへ書かず、見本をコピーして `.env` の値だけ置き換えます。`.env` は `.gitignore` 対象です。

```bash
cp .env.example .env
open -e .env
```

または、そのターミナル内だけ環境変数に設定できます。

```bash
export OPENAI_API_KEY='自分のAPIキー'
```

`config.yaml` の既定モデルは現行の高品質画像モデル `gpt-image-2` です。将来モデル名やAPI仕様が変わった場合は、[OpenAI Image generationガイド](https://developers.openai.com/api/docs/guides/image-generation) を確認して `openai.model` を変更してください。APIには文字なし・均一なクロマキー背景を依頼し、ローカルで透過化するため、日本語文字や背景透過の成否をモデルだけに依存しません。

クロマキーは初期設定で `auto` です。`reference.png` の色を調べ、緑とマゼンタのうちキャラクターから遠い色を選択します。背景除去には [sprite-gen 2.12.1](https://github.com/aldegad/sprite-gen/tree/b058341f7543f3adcbea227bd4e6b7587895b1bc) の実装を直接利用します。モデルが指定色を正確に描かない場合も、画像端から実際の背景色を検出し、ソフトアルファ・アンミックス、デスピル、エッジ除染を行います。バージョンは再現性のため `requirements.txt` でコミットまで固定しており、ライセンス情報は `THIRD_PARTY_NOTICES.md` に記載しています。

## 4. `reference.png` の設置

キャラクター画像をプロジェクト直下へ **`reference.png`** という名前で置きます。今回の添付画像はダウンロードしてその名前で保存してください。PNG/JPEG入力を利用できますが、ファイル名は設定どおりにします。

```text
line-sticker-maker/
└── reference.png
```

この画像は全24回の編集入力に使われます。存在しない場合は、01で作ったデザインを `raw_images/identity.png` として保存し、02以降の基準にします。より高い統一性を得るには `reference.png` の利用を強く推奨します。

## 5. スタンプ生成

まずAPIを使わないサンプルで、フォント、加工、検証まで動くことを確認できます。

```bash
python generate.py --demo
python validation.py
```

サンプルを消して本番を生成します（`--force` が全番号を上書きします）。

```bash
python generate.py --force
```

通常の再実行では `line_stickers/01.png` など、既に完成した画像をスキップします。通信エラー時は指数バックオフで `config.yaml` の `retries` 回まで自動再試行します。再開は同じコマンドです。

```bash
python generate.py
```

文章、ポーズは `stickers.yaml`、モデル、リトライ、余白、色、フォントは `config.yaml` で変更できます。日本語が豆腐（□）になる場合は、Mac上の日本語フォントを絶対パスで指定します。

```yaml
text:
  font_path: /System/Library/Fonts/ヒラギノ角ゴシック W6.ttc
```

## 6. 品質チェック

```bash
python validation.py
```

不足、PNG形式、RGBAと透明ピクセル、サイズ、偶数辺、1MB制限、名前、24枚、main/tabの固定サイズ、ZIP内容・破損・60MB制限を検査します。成功時は次の一行が表示されます。

```text
LINE STICKER VALIDATION: PASS
```

## 7. previewとZIPの再生成

通常は生成の最後に `preview.png` と `line_stickers.zip` も作られます。画像を手作業で差し替えた後、APIを呼ばず再梱包するには次を実行します。

```bash
python generate.py --zip-only
python validation.py
```

出力は次のようになります。`preview.png` は確認用で、アップロードZIPには入りません。

```text
line_stickers/
├── 01.png ... 24.png
├── main.png
├── tab.png
├── preview.png
└── line_stickers.zip
```

## 8. LINE Creators Marketへ登録

1. `line_stickers/preview.png` を開き、文字、表情、キャラクターの一貫性、透過境界を目視確認します。
2. `python validation.py` がPASSすることを確認します。
3. [LINE Creators Market](https://creator.line.me/) にログインし、「新規登録」からスタンプを選びます。
4. タイトル、説明、販売地域などを入力し、スタンプ数を **24個** に設定します。
5. `main.png`、`tab.png`、`01.png`〜`24.png`を登録します。画面がZIPアップロードに対応している場合は `line_stickers.zip` を利用できます。
6. LINEの審査ガイドライン（権利、表現、余白を含む）を再確認し、リクエスト送信します。

AI生成物を登録する権利があること、基準画像・フォント・キャラクター・名称が第三者の権利を侵害しないことは、登録者自身で必ず確認してください。Creators Marketの画面や規約は変更される場合があるため、登録時点の公式案内を優先してください。

## よくあるエラー

- **`OPENAI_API_KEY が未設定`**: `.env` を作り、キー名の前後に余計な空白を入れないでください。
- **日本語フォントが見つからない**: `config.yaml` の `text.font_path` に利用可能な `.ttf` / `.ttc` の絶対パスを指定します。
- **背景色が残る**: 通常は `chroma_key: auto` のままにしてください。固定したい場合は `[0, 255, 0]` または `[255, 0, 255]` を指定できます。透過エンジンの診断が失敗した場合は黙って不完全画像を保存せず、具体的なエラーで停止します。
- **一部だけ再生成したい**: 対象の `line_stickers/NN.png` と `raw_images/NN.png` を削除し、`python generate.py` を再実行します。
- **全て作り直したい**: `python generate.py --force` を使います。
