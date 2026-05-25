# ttk

> このプロジェクトは、Codex を使った開発を練習するために作っています。現時点では小さな玩具アプリですが、ちょくちょく手を入れながら、実用に近づけるための骨組みに少しずつ肉をつけていく予定です。

担当君（TanTouKun）は、ひとつのアクティビティの中で複数メンバーが複数の役割を回って担当することを管理するためのウェブアプリです。アクティビティごとに役割とメンバーを登録し、担当履歴をもとに次の担当者を日次でローテーションします。

主な機能:

- アクティビティの作成と削除、アクティビティごとの役割、メンバーの管理
- 担当者の自動ローテーション

## Docker で起動

```bash
make docker-up
```

停止する場合:

```bash
make docker-down
```

日次ローテーションは、crontab から 0 時に実行します。

```cron
0 0 * * * cd /path/to/ttk && make docker-rotate
```

日付を指定して手動実行する場合:

```bash
make docker-rotate DATE=2026-05-24
```

スモークテストを実行する。

> Docker のDBをテストデータで初期化し、確認後にDockerサービスを停止します。

```bash
make docker-smoke
```

簡易性能試験を実行する。

> Docker のDBを空に初期化し、確認後にDockerサービスを停止します。デフォルトではアクティビティ1000件、ローテーション100回、担当情報取得1000回を実行します。

```bash
make docker-perf
```

小さい件数で試す場合:

```bash
make docker-perf PERF_ACTIVITIES=20 PERF_ROTATIONS=5 PERF_READS=50
```

## ローカルで起動

> ローカルで起動するために [uv](https://github.com/astral-sh/uv) が必要です。

```bash
make sync
make dev
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。

DB migration は Alembic で管理します。アプリ起動やテストデータ投入時にも自動で最新化されますが、手動で適用する場合は次を実行します。

```bash
make migrate
```

日次ローテーションは、crontab から毎日0時に実行します。

```cron
0 0 * * * cd /path/to/ttk && make rotate
```

日付を指定して手動実行する場合:

```bash
make rotate DATE=2026-05-24
```

## テスト

テストコードを実行します。

```bash
make test
```
