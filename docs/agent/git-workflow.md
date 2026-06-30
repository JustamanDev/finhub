# Git workflow

> Читай **только** при создании веток, коммитов или PR. How-to коммитов/PR — в Cursor user rules.

## Base branch

- **`main`** — единственная база для новых веток
- Перед веткой: `git checkout main && git pull origin main`

## Ветки

| Префикс | Когда |
|---------|-------|
| `feature/<short-name>` | новая функциональность |
| `fix/<short-name>` | багфикс |
| `hotfix/<short-name>` | срочный prod fix |

**Правила:**

- Ветвиться **только от `main`**
- **Запрещено** ответвляться от другой feature/fix/hotfix ветки
- Одна фича = одна ветка = один PR в `main`

## Коммиты

- **Атомарные:** один логический шаг за коммит; в рамках одной фичи коммитов может быть много
- Предпочтительно рабочее состояние после каждого коммита
- Миграции — в том же коммите/серии, что и изменения моделей
- Сообщение: императив, фокус на «зачем», не на «что»

## Merge

- **Только через Pull Request** в `main` (без прямого push в `main`)
- После merge: удалить ветку, локально `git checkout main && git pull`

## Агент

- Не commit / push / PR без явного запроса пользователя
- Не `--no-verify`, не force-push в `main`

## Быстрый цикл

```bash
git checkout main && git pull origin main
git checkout -b feature/voice-input
# ... atomic commits ...
git push -u origin feature/voice-input
# gh pr create → merge → delete branch
```
