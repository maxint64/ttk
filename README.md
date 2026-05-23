# ttk

担当君（TanTouKun）は、ひとつのアクティビティの中で複数メンバーが複数の役割を回って担当することを管理するためのウェブアプリです。アクティビティごとに役割とメンバーを登録し、担当履歴をもとに次の担当者を日次でローテーションします。

主な機能:

- アクティビティの作成と削除
- アクティビティごとの役割、メンバーの管理
- 役割ごとの担当者の手動登録
- 担当者の自動ローテーション

## Docker で起動

Docker Compose では、Web API とローテーション処理を別サービスとして起動します。どちらも同じ Docker volume `ttk-data` にある SQLite データベースを使います。

```bash
docker compose up --build
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。

停止する場合:

```bash
docker compose down
```

## ローカルで起動

ローカルでは、まず依存パッケージを同期してから Web API を起動します。データは `data/ttk.sqlite3` に保存されます。

```bash
uv sync
uv run python run.py
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。

日次ローテーションも動かす場合は、別のターミナルで worker を起動します。

```bash
uv run python run_rotation.py
```

## テスト

```bash
uv run python -m unittest discover -s tests
```
