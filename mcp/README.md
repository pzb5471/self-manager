# SQLite MCP usage

This project is configured with SQLite MCP in [.mcp.json](../.mcp.json), pointing to `./productivity_manager.db`.

## What is implemented

- User table: `users`
- Session/auth token table: `auth_tokens`
- Task table includes `user_id` for per-user isolation

## MCP SQL script

Use [auth_schema.sql](./sql/auth_schema.sql) in your SQLite MCP client to initialize/migrate schema.

## Notes

- App runtime uses Python `sqlite3` with the same database file.
- MCP is used as a database tooling/access layer for schema and inspection workflows.
