# Car AI Assistant — Stage 3

Локальный автомобильный музыкальный ассистент для Windows с текстовым CLI и push-to-talk голосовым вводом. Он индексирует MP3 в SQLite, воспроизводит их через Windows Media Player, выполняет короткие команды напрямую, а естественные запросы разбирает локальной моделью `qwen3:4b` через Ollama. Модель управляет музыкой только через MCP tools.

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

## Голосовой ввод

Голос распознаётся локально через multilingual-модель `Systran/faster-whisper-small`. По умолчанию используются CPU, `int8` и русский язык. Аудио не отправляется во внешние сервисы и не сохраняется постоянно.

После установки зависимостей модель нужно загрузить вручную. Обычный запуск приложения никогда не скачивает её автоматически:

```powershell
New-Item -ItemType Directory -Force data\models | Out-Null
hf download Systran/faster-whisper-small --local-dir data/models/faster-whisper-small
```

Путь к модели задаётся через `STT_MODEL_PATH`. Каталог `data/models` исключён из Git.

Посмотреть доступные устройства ввода можно без запуска Ollama и без загрузки STT-модели:

```powershell
python -m app.main --list-audio-devices
```

Укажите индекс или имя микрофона в `.env`:

```dotenv
AUDIO_INPUT_DEVICE=1
```

Либо выберите его для одного запуска:

```powershell
python -m app.main --voice --audio-device 1
```

Запуск поддерживаемых режимов:

```powershell
python -m app.main
python -m app.main --voice
python -m app.main --voice --mock
python -m app.main --list-audio-devices
python -m app.main --debug --voice
python -m app.main --transcribe-file path\to\command.wav
```

В режиме `--voice` приложение ждёт Enter, явно показывает `Listening...`, записывает одну фразу и завершает запись примерно после секунды тишины. Затем распознанный текст передаётся в тот же `Assistant.handle`, что используется текстовым CLI. После ответа цикл повторяется; `Ctrl+C` завершает работу. Wake Word, постоянное прослушивание и голосовой ответ на этом этапе отсутствуют.

Настройки по умолчанию:

```dotenv
STT_MODEL_PATH=data/models/faster-whisper-small
STT_LANGUAGE=ru
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_BEAM_SIZE=1
AUDIO_INPUT_DEVICE=
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_SILENCE_THRESHOLD=0.015
AUDIO_SILENCE_DURATION=1.0
AUDIO_SPEECH_TIMEOUT=8.0
AUDIO_MAX_RECORD_SECONDS=15.0
```

Если тихая речь не определяется, немного уменьшите `AUDIO_SILENCE_THRESHOLD`; при постоянном фоновом шуме увеличьте его. `AUDIO_SILENCE_DURATION` задаёт паузу после речи, `AUDIO_SPEECH_TIMEOUT` — ожидание начала речи, `AUDIO_MAX_RECORD_SECONDS` — жёсткий предел записи. Все интервалы задаются в секундах.

Флаг `--debug` показывает выбранный маршрут, причину завершения записи и отдельно измеренные длительность аудио, ожидание речи, STT, Assistant и общее время голосового запроса. Длительность произнесённой фразы не считается временем вычисления STT.

Если микрофон не найден, проверьте `--list-audio-devices` и значение `AUDIO_INPUT_DEVICE`. Если устройство занято, закройте использующую его программу. Если модель отсутствует, повторите команду `hf download` выше и проверьте `STT_MODEL_PATH`.

Качество зависит от микрофона, фонового шума, произношения и иностранных имён. Распознавание на CPU может занимать заметное время; конкретную задержку следует измерить на целевом ноутбуке через `--debug`. Текстовый режим остаётся режимом по умолчанию и не открывает микрофон и не загружает Whisper.

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

Наборы команд для ручной проверки находятся в `benchmarks/commands.txt` и `benchmarks/voice_commands.txt`. В debug-режиме для каждого запроса выводятся route, модель, tool arguments и раздельные latency. Скрытые рассуждения модели не выводятся.

Файлы музыки, рабочая SQLite-база и логи исключены из Git. Технические ошибки сохраняются в `data/car_assistant.log`.
