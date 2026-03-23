import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../../api";

type ContentItem = {
  id: number;
  title: string;
  platform?: string | null;
  content_type?: string | null;
  status: string;
  due_date?: string | null;
  notes?: string | null;
};

type ContentTask = {
  id: number;
  content_item_id: number;
  title: string;
  status: string;
};

const STATUS_COLUMNS = [
  { value: "idea", label: "Idea" },
  { value: "draft", label: "Draft" },
  { value: "recorded", label: "Recorded" },
  { value: "edited", label: "Edited" },
  { value: "scheduled", label: "Scheduled" },
  { value: "published", label: "Published" },
] as const;

const PLATFORM_LANES = [
  { value: "youtube", label: "YouTube" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "other", label: "Other" },
] as const;

const MAIN_PLATFORM_VALUES: Set<string> = new Set(
  PLATFORM_LANES.filter((lane) => lane.value !== "other").map((lane) => lane.value)
);

type PlatformFilter = "all" | (typeof PLATFORM_LANES)[number]["value"];

const PLATFORM_FILTERS: { value: PlatformFilter; label: string }[] = [
  { value: "all", label: "Alle" },
  ...PLATFORM_LANES.map((lane) => ({ value: lane.value, label: lane.label })),
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return apiFetch(path, init) as Promise<T>;
}

export default function ContentPage() {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [tasks, setTasks] = useState<ContentTask[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [newTitle, setNewTitle] = useState("");
  const [newPlatform, setNewPlatform] = useState("youtube");
  const [newType, setNewType] = useState("video");
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");

  const selected = useMemo(
    () => items.find((x) => x.id === selectedId) || null,
    [items, selectedId]
  );
  const selectedTasks = useMemo(
    () => tasks.filter((t) => t.content_item_id === selectedId),
    [tasks, selectedId]
  );

  const load = useCallback(async () => {
    const [it, tk] = await Promise.all([
      api<ContentItem[]>("/content/items"),
      api<ContentTask[]>("/content/tasks"),
    ]);
    setItems(it);
    setTasks(tk);
    if (selectedId && !it.find((x) => x.id === selectedId)) setSelectedId(null);
  }, [selectedId]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  async function createItem() {
    if (!newTitle.trim()) return;
    const created = await api<ContentItem>("/content/items", {
      method: "POST",
      body: JSON.stringify({
        title: newTitle.trim(),
        platform: newPlatform,
        content_type: newType,
        status: "idea",
      }),
    });
    setItems((p) => [created, ...p]);
    setNewTitle("");
    setSelectedId(created.id);
  }

  async function updateItem(id: number, patch: Partial<ContentItem>) {
    const updated = await api<ContentItem>(`/content/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    setItems((p) => p.map((x) => (x.id === id ? updated : x)));
  }

  async function deleteItem(id: number) {
    await api(`/content/items/${id}`, { method: "DELETE" });
    setItems((p) => p.filter((x) => x.id !== id));
    setTasks((p) => p.filter((t) => t.content_item_id !== id));
    setSelectedId((cur) => (cur === id ? null : cur));
  }

  async function createTask(content_item_id: number, title: string) {
    const created = await api<ContentTask>("/content/tasks", {
      method: "POST",
      body: JSON.stringify({ content_item_id, title, status: "todo" }),
    });
    setTasks((p) => [created, ...p]);
  }

  async function updateTask(id: number, patch: Partial<ContentTask>) {
    const updated = await api<ContentTask>(`/content/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    setTasks((p) => p.map((x) => (x.id === id ? updated : x)));
  }

  async function deleteTask(id: number) {
    await api(`/content/tasks/${id}`, { method: "DELETE" });
    setTasks((p) => p.filter((x) => x.id !== id));
  }

  const laneData = useMemo(() => {
    return PLATFORM_LANES.map((lane) => {
      const laneItems = items.filter((it) => {
        const normalized = (it.platform || "").toLowerCase();
        if (lane.value === "other") {
          if (!normalized) return true;
          return !MAIN_PLATFORM_VALUES.has(normalized);
        }
        return normalized === lane.value;
      });
      return { ...lane, items: laneItems };
    });
  }, [items]);

  const visibleLanes = useMemo(() => {
    if (platformFilter === "all") return laneData;
    return laneData.filter((lane) => lane.value === platformFilter);
  }, [laneData, platformFilter]);

  return (
    <div className="container board-layout">
      <div className="page-header">
        <div>
          <h2 className="page-title">Content</h2>
          <div className="page-subtitle">Planung, Status und Tasks pro Plattform.</div>
        </div>
        <div className="page-actions">
          <div className="control-row">
            <input
              className="composer-input"
              placeholder="Titel…"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <select value={newPlatform} onChange={(e) => setNewPlatform(e.target.value)}>
              <option value="youtube">YouTube</option>
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="blog">Blog</option>
              <option value="podcast">Podcast</option>
            </select>
            <select value={newType} onChange={(e) => setNewType(e.target.value)}>
              <option value="video">Video</option>
              <option value="short">Short/Reel</option>
              <option value="post">Post</option>
              <option value="article">Article</option>
              <option value="podcast">Podcast</option>
            </select>
          </div>
          <button className="btn primary" onClick={() => createItem().catch(alert)}>
            + Add
          </button>
          <button className="btn" onClick={() => load().catch(alert)}>
            Refresh
          </button>
        </div>
      </div>

      <div className="content-shell">
        <div className="content-main">
          <div className="board-filters">
            {PLATFORM_FILTERS.map((option) => (
              <button
                key={option.value}
                className={platformFilter === option.value ? "btn primary" : "btn"}
                onClick={() => setPlatformFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="swimlane-stack">
            {visibleLanes.map((lane) => (
              <div key={lane.value} className="swimlane card">
                <div className="row between swimlane-label">
                  <div>{lane.label}</div>
                  <span className="muted small">{lane.items.length} Items</span>
                </div>
                <div className="swimlane-columns">
                  {STATUS_COLUMNS.map((col) => {
                    const cards = lane.items.filter((it) => it.status === col.value);
                    return (
                      <div key={col.value} className="swimlane-column">
                        <div className="swimlane-column-title">{col.label}</div>
                        <div className="stack">
                          {cards.map((it) => (
                            <div
                              key={it.id}
                              className={it.id === selectedId ? "kanban-card active" : "kanban-card"}
                              onClick={() => setSelectedId(it.id)}
                            >
                              <div>{it.title}</div>
                              <div className="small muted">
                                {(it.platform || "").toUpperCase()} • {(it.content_type || "").toUpperCase()}
                              </div>

                              <div className="kanban-actions">
                                {STATUS_COLUMNS.filter((next) => next.value !== it.status)
                                  .slice(0, 2)
                                  .map((next) => (
                                    <button
                                      key={next.value}
                                      className="btn ghost"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        updateItem(it.id, { status: next.value }).catch(alert);
                                      }}
                                    >
                                      → {next.label}
                                    </button>
                                  ))}
                              </div>
                            </div>
                          ))}
                          {cards.length === 0 && <div className="muted small">–</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="content-side">
          {!selected ? (
            <div className="card">
              <h3>Details</h3>
              <div className="muted">Links ein Item wählen.</div>
            </div>
          ) : (
            <div className="stack">
              <div className="card">
                <div className="section-head">
                  <h3 className="no-margin">{selected.title}</h3>
                  <button className="btn danger" onClick={() => deleteItem(selected.id).catch(alert)}>
                    Delete
                  </button>
                </div>

                <hr />

                <div className="stack">
                  <div>
                    <div className="field-label">Status</div>
                    <select
                      className="full-width"
                      value={selected.status}
                      onChange={(e) => updateItem(selected.id, { status: e.target.value }).catch(alert)}
                    >
                      {STATUS_COLUMNS.map((st) => (
                        <option key={st.value} value={st.value}>
                          {st.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div className="field-label">Notes</div>
                    <textarea
                      value={selected.notes || ""}
                      onChange={(e) =>
                        updateItem(selected.id, { notes: e.target.value }).catch(console.error)
                      }
                      placeholder="Notizen…"
                    />
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="title-strong">Tasks</div>
                <TaskComposer onAdd={(t) => createTask(selected.id, t).catch(alert)} />

                <div className="stack section-gap">
                  {selectedTasks.map((t) => (
                    <div key={t.id} className="card tight">
                      <div className="section-head no-margin">
                        <div>{t.title}</div>
                        <button className="btn" onClick={() => deleteTask(t.id).catch(alert)}>
                          ✕
                        </button>
                      </div>
                      <div className="control-row section-gap">
                        {["todo", "doing", "done"].map((st) => (
                          <button
                            key={st}
                            className={t.status === st ? "btn primary" : "btn"}
                            onClick={() => updateTask(t.id, { status: st }).catch(alert)}
                          >
                            {st}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  {selectedTasks.length === 0 && <div className="muted">Keine Tasks.</div>}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TaskComposer({ onAdd }: { onAdd: (title: string) => void }) {
  const [title, setTitle] = useState("");
  return (
    <div className="control-row stretch">
      <input
        className="grow"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Neue Task…"
      />
      <button
        className="btn primary"
        onClick={() => {
          if (!title.trim()) return;
          onAdd(title.trim());
          setTitle("");
        }}
      >
        + Add
      </button>
    </div>
  );
}