# Car AI Assistant — Stage 2

Локальный текстовый автомобильный музыкальный ассистент для Windows. Он индексирует MP3 в SQLite, воспроизводит их через Windows Media Player, выполняет короткие команды напрямую, а естественные запросы разбирает локальной моделью `qwen3:4b` через Ollama. Модель управляет музыкой только через MCP tools.

Помимо управления музыкой, локальная модель может кратко отвечать на простые общеобразовательные вопросы из собственных знаний. Доступа к интернету и гарантированно актуальным данным у неё нет.

## Установка

Требуется Python 3.12+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Установите [Ollama](https://ollama.com/download), затем вручную загрузите единственную модель проекта:

```powershell
ollama pull qwen3:4b
```

Ollama должна быть запущена во время обычной работы приложения. Модель никогда не скачивается автоматически. Параметры подключения находятся в `.env`:

```dotenv
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT=60
```

Положите MP3 в `media/music` (вложенные каталоги поддерживаются) и проиндексируйте библиотеку:

```powershell
python -m app.main --scan
python -m app.main
```

Доступные параметры:

```powershell
python -m app.main          # Ollama + qwen3:4b
python -m app.main --mock   # детерминированная замена LLM для разработки
python -m app.main --debug  # маршрут, tool и latency
python -m app.main --scan   # обновление музыкального индекса
```

Если Ollama выключена, приложение покажет понятное сообщение. Если модели нет, оно предложит выполнить `ollama pull qwen3:4b`.

## Команды

- `Пауза`, `Продолжи`, `Следующий`, `Предыдущий`
- `Громче`, `Тише`, `Громкость 35`
- `Давай что-нибудь из Кино`, `Я хочу послушать Linkin Park`
- `Что сейчас играет?`, `help`, `exit`

Очевидные команды паузы, навигации и громкости идут по быстрому пути `CommandRouter → MusicService`, без запуска LLM. Естественные или неоднозначные формулировки идут по пути `CommandRouter → Qwen3 4B → MCP tool → MusicService`.

Запросы по настроению, жанру и истории прослушивания не поддерживаются, пока в музыкальной базе нет таких данных. Модель проинструктирована не выдумывать результат.

## MCP server

После установки зависимостей сервер с реальными MCP tools запускается по stdio:

```powershell
python -m mcp_server.server
```

## Проверка

```powershell
pytest
```

Набор команд для ручной проверки находится в `benchmarks/commands.txt`. В debug-режиме для каждого запроса выводятся route, модель, tool arguments, router/direct/LLM/total latency. Скрытые рассуждения модели не выводятся.

Файлы музыки, рабочая SQLite-база и логи исключены из Git. Технические ошибки сохраняются в `data/car_assistant.log`.
