# ttk

担当君（TannTouKunn）は、ひとつのアクティビティの中で複数メンバーが複数の役割を回って担当することを管理するためのウェブアプリです。

## MVP

- アクティビティの追加、削除
- アクティビティへの役割の追加、削除
- アクティビティへのメンバーの追加、削除

## Docker で起動

```bash
docker compose up --build
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。データは Docker volume `ttk-data` に保存されます。

停止する場合:

```bash
docker compose down
```

## ローカルで起動

`uv` で依存パッケージを同期してから起動します。

```bash
uv sync
uv run python run.py
```

起動後、ブラウザで `http://127.0.0.1:8000` を開きます。データは `data/ttk.sqlite3` に保存されます。

## API

- `GET /api/activities`
- `POST /api/activities` body: `{ "name": "朝会" }`
- `DELETE /api/activities/{activity_id}`
- `POST /api/activities/{activity_id}/roles` body: `{ "name": "司会" }`
- `DELETE /api/activities/{activity_id}/roles/{role_id}`
- `POST /api/activities/{activity_id}/members` body: `{ "name": "田中" }`
- `DELETE /api/activities/{activity_id}/members/{member_id}`

## テスト

```bash
uv run python -m unittest discover -s tests
```
