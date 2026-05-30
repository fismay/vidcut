# YouTube Clipper

Локальный веб-сервис для:

- поиска роликов на YouTube через `yt-dlp`
- скачивания в лучшем доступном качестве
- удаления спонсорских вставок через SponsorBlock
- автоматической нарезки на части примерно по 3 минуты
- распознавания речи через `faster-whisper`
- наложения burn-in субтитров поверх каждого клипа
- сохранения всех готовых файлов в папку `output/`

## Запуск одной командой

Из корня проекта выполните:

```powershell
python run.py
```

Скрипт автоматически:

1. создаст виртуальное окружение `.venv`
2. установит Python-зависимости
3. установит frontend-зависимости через `npm`
4. соберёт React-интерфейс
5. запустит FastAPI-сервер
6. откроет сайт в браузере

По умолчанию интерфейс открывается по адресу:

```text
http://127.0.0.1:8000
```

## Как запускать и как завершать

### Запуск

```powershell
python run.py
```

### Завершение

Если сервис запущен через `python run.py`, можно остановить его:

```powershell
Ctrl+C
```

Либо прямо из интерфейса нажать кнопку `Выключить сервис`.

## Что должно быть установлено заранее

### Обязательно

- `Python 3.11+`
- `Node.js + npm`
- `FFmpeg` и `ffprobe` в `PATH`

### Проверка

```powershell
python --version
npm --version
ffmpeg -version
ffprobe -version
```

## Если FFmpeg не установлен

Для Windows можно взять готовую сборку:

- [Gyan FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/)

После установки добавьте путь к `ffmpeg.exe` и `ffprobe.exe` в системный `PATH`.

## Как пользоваться

1. Откройте сайт.
2. Введите поисковый запрос по YouTube.
3. Выберите ролик из списка.
4. Нажмите `Обработать видео`.
5. Дождитесь завершения этапов:
   - скачивание
   - SponsorBlock
   - нарезка
   - AI-субтитры
6. Готовые файлы появятся в блоке `Готовые файлы` и в папке `output/`.

## Важные замечания

- Поиск реализован через `yt-dlp`, поэтому `YOUTUBE_API_KEY` не нужен.
- `GEMINI_API_KEY` в этом проекте не используется.
- Ключи не захардкожены в коде специально, чтобы не хранить секреты в репозитории.
- Для устойчивости длинные видео обрабатываются пофрагментно, а не целиком.
- Если субтитры не удалось построить для конкретного фрагмента, обработка остальных фрагментов продолжается.
- Если SponsorBlock не вернул сегменты, ролик обрабатывается целиком.

## Настройки через переменные окружения

Скопируйте `.env.example` в свой `.env` или задайте переменные вручную:

```text
APP_HOST=127.0.0.1
APP_PORT=8000
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
CHUNK_DURATION_SECONDS=180
```

### Рекомендации по модели Whisper

- `small` — хороший баланс скорости и качества
- `medium` — лучше качество, но тяжелее по памяти
- `tiny` или `base` — если нужен максимально лёгкий режим

## Структура проекта

```text
.
├── backend
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── models.py
│   ├── task_queue.py
│   ├── utils.py
│   └── services
│       ├── ffmpeg_service.py
│       ├── processing_service.py
│       ├── sponsorblock_service.py
│       ├── subtitle_service.py
│       └── youtube_service.py
├── frontend
│   ├── package.json
│   ├── vite.config.js
│   └── src
│       ├── App.jsx
│       ├── index.css
│       └── main.jsx
├── output
├── requirements.txt
├── run.py
└── README.md
```

## Что где происходит

### Backend

- `FastAPI` отдаёт API и собранный frontend
- `JobManager` держит очередь фоновых задач и статус прогресса
- `YouTubeService` делает поиск и скачивание через `yt-dlp`
- `SponsorBlockService` получает таймкоды рекламных вставок
- `FFmpegService` удаляет сегменты, режет клипы и вшивает субтитры
- `SubtitleService` запускает `faster-whisper` и пишет `.srt`
- `ProcessingService` управляет всем пайплайном и обработкой ошибок

### Frontend

- `React + Vite`
- `Tailwind CSS`
- polling каждые `1.5s` для живого прогресса
- светлая и тёмная темы

## Сохранение результатов

Все итоговые ролики сохраняются в:

```text
output/
```

Формат имени:

```text
{название}_part01.mp4
{название}_part02.mp4
...
```

## Логи

Логи приложения пишутся в:

```text
logs/app.log
```

Там особенно полезно смотреть ошибки `faster-whisper`, `ffmpeg` и сетевые проблемы YouTube/SponsorBlock.

## Ручной запуск без `run.py`

Если нужен запуск по шагам:

### 1. Создать venv

```powershell
python -m venv .venv
```

### 2. Установить backend-зависимости

```powershell
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

### 3. Установить frontend-зависимости

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 4. Запустить сервер

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Возможные проблемы

### `ffmpeg` not found

Установите FFmpeg и проверьте, что команды `ffmpeg` и `ffprobe` доступны из терминала.

### Медленная генерация субтитров

Попробуйте:

- уменьшить модель до `base` или `tiny`
- закрыть тяжёлые приложения
- использовать более короткие ролики

### YouTube не отдаёт видео

Иногда причина в:

- временных ограничениях со стороны YouTube
- нестабильной сети
- обновлениях на стороне YouTube

В этом случае обычно помогает повторный запуск задачи позже.

## Лицензии и внешние инструменты

Проект использует внешние инструменты и сервисы:

- `yt-dlp`
- `FFmpeg`
- `faster-whisper`
- `SponsorBlock API`

Перед публичным использованием стоит отдельно проверить их лицензии и ограничения для вашей среды.
