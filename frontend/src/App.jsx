import { useEffect, useMemo, useState } from "react";
import {
  Captions,
  Clapperboard,
  FolderOpen,
  LoaderCircle,
  MoonStar,
  Power,
  Search,
  Smartphone,
  Sparkles,
  SunMedium,
  Youtube
} from "lucide-react";

const STAGE_LABELS = {
  queued: "В очереди",
  starting: "Подготовка",
  download: "Скачивание",
  sponsorblock: "SponsorBlock",
  cutting: "Нарезка",
  subtitles: "AI-субтитры",
  rendering: "Вертикальный шортс",
  completed: "Готово",
  failed: "Ошибка"
};

function cn(...values) {
  return values.filter(Boolean).join(" ");
}

function formatDate(value) {
  return new Date(value).toLocaleString("ru-RU");
}

function statusTone(status) {
  if (status === "completed") return "text-emerald-300 bg-emerald-500/15 border-emerald-400/30";
  if (status === "partial") return "text-amber-300 bg-amber-500/15 border-amber-400/30";
  if (status === "failed") return "text-rose-300 bg-rose-500/15 border-rose-400/30";
  return "text-sky-200 bg-sky-500/15 border-sky-400/30";
}

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState(null);
  const [outputs, setOutputs] = useState([]);
  const [isStartingJob, setIsStartingJob] = useState(false);
  const [addSubtitles, setAddSubtitles] = useState(true);
  const [isStoppingService, setIsStoppingService] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    loadOutputs();
  }, []);

  useEffect(() => {
    if (!jobId) return undefined;

    const interval = window.setInterval(async () => {
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) {
        return;
      }

      const payload = await response.json();
      setJob(payload);

      if (["completed", "partial", "failed"].includes(payload.status)) {
        loadOutputs();
        window.clearInterval(interval);
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [jobId]);

  const logs = useMemo(() => (job?.logs || []).slice().reverse(), [job]);

  async function loadOutputs() {
    const response = await fetch("/api/outputs");
    if (!response.ok) return;
    const payload = await response.json();
    setOutputs(payload.items || []);
  }

  async function handleSearch(event) {
    event.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setSearchError("");

    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(query.trim())}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Не удалось выполнить поиск");
      }
      setResults(payload.items || []);
    } catch (error) {
      setSearchError(error.message || "Ошибка поиска");
    } finally {
      setIsSearching(false);
    }
  }

  async function startProcessing(video) {
    setSelectedVideo(video);
    setIsStartingJob(true);
    setJob(null);
    setJobId("");
    setSearchError("");

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          ...video,
          add_subtitles: addSubtitles
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Не удалось создать задачу");
      }
      setJobId(payload.job_id);
    } catch (error) {
      setSearchError(error.message || "Ошибка запуска обработки");
    } finally {
      setIsStartingJob(false);
    }
  }

  async function openFolder(path = null) {
    await fetch("/api/open-output-folder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ path })
    });
  }

  async function stopService() {
    if (isStoppingService) return;

    setIsStoppingService(true);
    setSearchError("");

    try {
      const response = await fetch("/api/shutdown", {
        method: "POST"
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Не удалось остановить сервис");
      }
      setSearchError("Сервис останавливается. Страница перестанет отвечать через секунду.");
      window.setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (error) {
      setIsStoppingService(false);
      setSearchError(error.message || "Ошибка остановки сервиса");
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(251,191,36,0.14),_transparent_30%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-7xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
        <section className="glass-panel overflow-hidden p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/8 px-4 py-2 text-sm text-[var(--muted)]">
                <Sparkles size={16} />
                Вертикальные Shorts-клипы, SponsorBlock и AI-субтитры в одном окне
              </div>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
                Локальная студия для нарезки YouTube в формат Shorts
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted)] sm:text-lg">
                Сервис всегда сохраняет финальные ролики вертикально в формате <span className="font-semibold text-[var(--text)]">9:16</span>.
                При желании можно включать или отключать AI-субтитры, которые вшиваются строго по центру кадра.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm font-medium transition hover:bg-white/15"
              >
                {theme === "dark" ? <SunMedium size={18} /> : <MoonStar size={18} />}
                {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
              </button>

              <button
                type="button"
                onClick={stopService}
                disabled={isStoppingService}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-400/25 bg-rose-500/12 px-4 py-3 text-sm font-medium text-rose-200 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isStoppingService ? <LoaderCircle className="animate-spin" size={18} /> : <Power size={18} />}
                {isStoppingService ? "Останавливаем..." : "Выключить сервис"}
              </button>
            </div>
          </div>

          <form onSubmit={handleSearch} className="mt-8 flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted)]" size={18} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Например: podcast motivation clips"
                className="h-14 w-full rounded-2xl border border-white/15 bg-[var(--surface-strong)] pl-12 pr-4 text-base outline-none transition placeholder:text-[var(--muted)] focus:border-sky-400/50 focus:ring-4 focus:ring-sky-400/10"
              />
            </div>

            <button
              type="submit"
              disabled={isSearching}
              className="inline-flex h-14 items-center justify-center gap-2 rounded-2xl bg-[var(--accent)] px-6 font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSearching ? <LoaderCircle className="animate-spin" size={18} /> : <Youtube size={18} />}
              {isSearching ? "Ищем..." : "Найти видео"}
            </button>
          </form>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-start gap-3">
                <Smartphone className="mt-0.5 text-sky-300" size={18} />
                <div>
                  <h2 className="text-base font-semibold">Финальный формат</h2>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Каждый готовый файл рендерится вертикально под Shorts: 1080x1920, с адаптацией кадра под экран телефона.
                  </p>
                </div>
              </div>
            </div>

            <label className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <Captions className="mt-0.5 text-amber-300" size={18} />
                  <div>
                    <h2 className="text-base font-semibold">AI-субтитры по центру</h2>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      Включай, если хочешь вшитые субтитры посередине ролика. Выключай, если нужен чистый вертикальный клип без текста.
                    </p>
                  </div>
                </div>

                <span className={cn(
                  "relative inline-flex h-7 w-12 shrink-0 rounded-full transition",
                  addSubtitles ? "bg-amber-400" : "bg-white/15"
                )}>
                  <input
                    type="checkbox"
                    checked={addSubtitles}
                    onChange={(event) => setAddSubtitles(event.target.checked)}
                    className="peer sr-only"
                  />
                  <span
                    className={cn(
                      "absolute top-1 h-5 w-5 rounded-full bg-white transition",
                      addSubtitles ? "left-6" : "left-1"
                    )}
                  />
                </span>
              </div>
            </label>
          </div>

          {searchError ? <p className="mt-4 text-sm text-rose-300">{searchError}</p> : null}
        </section>

        <section className="grid gap-8 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="glass-panel p-5 sm:p-6">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">Результаты поиска</h2>
                <p className="text-sm text-[var(--muted)]">Выбери ролик и запусти его обработку в вертикальный Shorts-формат.</p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-[var(--muted)]">
                {results.length} результатов
              </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {results.map((video) => (
                <article
                  key={video.video_id}
                  className={cn(
                    "group overflow-hidden rounded-3xl border border-white/10 bg-white/5 transition hover:-translate-y-0.5 hover:border-sky-400/35",
                    selectedVideo?.video_id === video.video_id && "border-sky-400/60 shadow-[0_0_0_1px_rgba(56,189,248,0.35)]"
                  )}
                >
                  <div className="relative aspect-video overflow-hidden bg-slate-900/60">
                    {video.thumbnail ? (
                      <img src={video.thumbnail} alt={video.title} className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-[var(--muted)]">No preview</div>
                    )}
                    <span className="absolute bottom-3 right-3 rounded-full bg-black/65 px-3 py-1 text-xs font-semibold text-white">
                      {video.duration_label}
                    </span>
                  </div>
                  <div className="space-y-4 p-4">
                    <div>
                      <h3 className="line-clamp-2 text-base font-semibold">{video.title}</h3>
                      <p className="mt-2 text-sm text-[var(--muted)]">{video.uploader || "YouTube"}</p>
                    </div>
                    <button
                      type="button"
                      disabled={isStartingJob}
                      onClick={() => startProcessing(video)}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm font-medium transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isStartingJob && selectedVideo?.video_id === video.video_id ? (
                        <>
                          <LoaderCircle className="animate-spin" size={16} />
                          Создаём задачу...
                        </>
                      ) : (
                        <>
                          <Clapperboard size={16} />
                          Обработать видео
                        </>
                      )}
                    </button>
                  </div>
                </article>
              ))}

              {!results.length && !isSearching ? (
                <div className="rounded-3xl border border-dashed border-white/15 bg-white/3 p-8 text-center text-[var(--muted)] md:col-span-2">
                  Здесь появятся результаты поиска после первого запроса.
                </div>
              ) : null}
            </div>
          </div>

          <div className="space-y-8">
            <section className="glass-panel p-5 sm:p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">Текущая задача</h2>
                  <p className="text-sm text-[var(--muted)]">Обновляется автоматически каждые 1.5 секунды.</p>
                </div>
                {job ? (
                  <span className={cn("rounded-full border px-3 py-1 text-sm", statusTone(job.status))}>
                    {job.status === "partial" ? "Частично готово" : STAGE_LABELS[job.stage] || job.status}
                  </span>
                ) : null}
              </div>

              {job ? (
                <div className="mt-6 space-y-5">
                  <div>
                    <p className="text-sm text-[var(--muted)]">Видео</p>
                    <h3 className="mt-1 text-lg font-semibold">{job.title}</h3>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-white/10 bg-black/10 p-4 text-sm text-[var(--muted)]">
                      <p>Формат: <span className="font-medium text-[var(--text)]">9:16 Shorts</span></p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-black/10 p-4 text-sm text-[var(--muted)]">
                      <p>
                        Субтитры: <span className="font-medium text-[var(--text)]">{job.add_subtitles ? "включены" : "выключены"}</span>
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>{job.message}</span>
                      <span>{Math.round(job.progress)}%</span>
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-white/8">
                      <div className="h-full rounded-full bg-[linear-gradient(90deg,_#38bdf8,_#fbbf24)] transition-all duration-500" style={{ width: `${job.progress}%` }} />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-black/10 p-4 text-sm text-[var(--muted)]">
                    <p>Этап: <span className="font-medium text-[var(--text)]">{STAGE_LABELS[job.stage] || job.stage}</span></p>
                    <p className="mt-2">
                      Фрагмент: <span className="font-medium text-[var(--text)]">{job.current_part || 0}</span> /{" "}
                      <span className="font-medium text-[var(--text)]">{job.total_parts || 0}</span>
                    </p>
                    {job.error ? <p className="mt-2 text-rose-300">{job.error}</p> : null}
                  </div>

                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <h4 className="font-medium">Логи</h4>
                      <span className="text-xs text-[var(--muted)]">{formatDate(job.updated_at)}</span>
                    </div>
                    <div className="max-h-64 space-y-2 overflow-auto rounded-2xl border border-white/10 bg-black/10 p-3">
                      {logs.map((entry, index) => (
                        <div key={`${entry.timestamp}-${index}`} className="rounded-xl border border-white/8 bg-white/4 p-3 text-sm">
                          <div className="flex items-center justify-between gap-3 text-xs text-[var(--muted)]">
                            <span>{entry.level.toUpperCase()}</span>
                            <span>{formatDate(entry.timestamp)}</span>
                          </div>
                          <p className="mt-2 text-[var(--text)]">{entry.message}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-3xl border border-dashed border-white/15 bg-white/3 p-8 text-center text-[var(--muted)]">
                  После запуска обработки здесь появится живой прогресс по этапам.
                </div>
              )}
            </section>

            <section className="glass-panel p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">Готовые файлы</h2>
                  <p className="text-sm text-[var(--muted)]">Все клипы сохраняются локально в папку output/.</p>
                </div>
                <button
                  type="button"
                  onClick={() => openFolder()}
                  className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm font-medium transition hover:bg-white/15"
                >
                  <FolderOpen size={16} />
                  Открыть output
                </button>
              </div>

              <div className="mt-5 space-y-3">
                {outputs.map((file) => (
                  <div key={file.path} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{file.name}</p>
                        <p className="mt-1 break-all text-sm text-[var(--muted)]">{file.path}</p>
                        <p className="mt-2 text-xs text-[var(--muted)]">
                          {file.size_mb} MB • {formatDate(file.modified_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => openFolder(file.path)}
                        className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-2 text-sm font-medium transition hover:bg-white/15"
                      >
                        <FolderOpen size={15} />
                        Открыть папку
                      </button>
                    </div>
                  </div>
                ))}

                {!outputs.length ? (
                  <div className="rounded-3xl border border-dashed border-white/15 bg-white/3 p-8 text-center text-[var(--muted)]">
                    Готовых клипов пока нет.
                  </div>
                ) : null}
              </div>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
