# ttk

担当君（TanTouKun）は、ひとつのアクティビティの中で複数メンバーが複数の役割を回って担当することを管理するためのウェブアプリです。アクティビティごとに役割とメンバーを登録し、担当履歴をもとに次の担当者を日次でローテーションします。

主な機能:

- アクティビティの作成と削除
- アクティビティごとの役割、メンバーの管理
- 役割ごとの担当者の手動登録
- 担当者の自動ローテーション

## ディレクトリ構成

- `app/`: フロントエンド
- `server/`: バックエンド
- `server/tests/`: バックエンドのテスト

## Docker で起動

Docker Compose では Web API を起動します。データは Docker volume `ttk-data` に保存されます。

```bash
make docker-up
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。

停止する場合:

```bash
make docker-down
```

日次ローテーションは、crontab から 0時に単発実行します。

```cron
0 0 * * * cd /path/to/ttk && make docker-rotate
```

## ローカルで起動

ローカルでは、まず依存パッケージを同期してから Web API を起動します。データは `data/ttk.sqlite3` に保存されます。

```bash
make sync
make dev
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。

日次ローテーションは、crontab から 0時に単発実行します。

```cron
0 0 * * * cd /path/to/ttk && make rotate
```

## テスト

```bash
make test
```

## よく使うコマンド

```bash
make help
make build
make seed
make clean
make clean-data
make docker-up
make docker-down
```
