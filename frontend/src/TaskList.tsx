import { useEffect, useState } from "react";
import { CheckCircle2, Circle, ArrowUpRight, Search } from "lucide-react";
import { api } from "./api";
import type { Task } from "./domain";
export type TaskOverview = Task & {
  note_id: string;
  title: string;
  group_name: string;
};
export function TaskList({ onOpen }: { onOpen: (id: string) => void }) {
  const [tasks, setTasks] = useState<TaskOverview[]>([]);
  const [filter, setFilter] = useState("pending");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    api<TaskOverview[]>("/tasks")
      .then((value) => {
        if (active) setTasks(value);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const shown = tasks.filter(
    (t) =>
      (filter === "all" || t.done === (filter === "done")) &&
      `${t.text} ${t.title} ${t.group_name}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  return (
    <section aria-label="全ノートのタスク">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ONE STEP AT A TIME</p>
          <h1>
            タスク一覧<span className="mint-period">.</span>
          </h1>
          <p className="muted">ノートをまたいで、次にやることを確認する。</p>
        </div>
      </div>
      <div className="list-tools">
        <div className="task-filters" aria-label="完了状態で絞り込み">
          {[
            ["all", "すべて"],
            ["pending", "未完了"],
            ["done", "完了"],
          ].map(([value, title]) => (
            <button
              key={value}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {title}
            </button>
          ))}
        </div>
        <label className="search">
          <Search size={17} />
          <input
            aria-label="タスクを検索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="タスクやノート名で検索"
          />
        </label>
      </div>
      {loading ? (
        <p role="status">タスクを読み込み中…</p>
      ) : error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : (
        <>
          <p className="muted">
            未完了 {tasks.filter((t) => !t.done).length}件 / 完了{" "}
            {tasks.filter((t) => t.done).length}件
          </p>
          <ul className="task-overview">
            {shown.map((t) => (
              <li key={`${t.note_id}-${t.id}`}>
                <span className="task-state">
                  {t.done ? <CheckCircle2 /> : <Circle />}
                  {t.done ? "完了" : "未完了"}
                </span>
                <div>
                  <strong>{t.text}</strong>
                  <p className="muted">
                    {t.group_name} / {t.title}
                  </p>
                  <small>期日: {t.due || "未設定"}</small>
                </div>
                <button
                  aria-label={`ノートを開く: ${t.title}`}
                  onClick={() => onOpen(t.note_id)}
                >
                  ノートを開く
                  <ArrowUpRight size={16} />
                </button>
              </li>
            ))}
          </ul>
          {shown.length === 0 && (
            <p className="empty">該当するタスクはありません。</p>
          )}
        </>
      )}
    </section>
  );
}
