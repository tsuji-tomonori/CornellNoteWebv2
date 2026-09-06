import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { editable, progress, type Note, type NoteInput } from "./domain";
export function Editor({
  note,
  onSave,
  onDirty,
  busy,
  readOnly = false,
}: {
  note: Note;
  onSave: (d: NoteInput) => Promise<void>;
  onDirty: () => void;
  busy: boolean;
  readOnly?: boolean;
}) {
  const [draft, setDraft] = useState<NoteInput>(editable(note));
  const [tab, setTab] = useState("content");
  const [task, setTask] = useState("");
  function change<K extends keyof NoteInput>(key: K, value: NoteInput[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
    onDirty();
  }
  useEffect(() => {
    const save = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (!readOnly && !busy) void onSave(editable(draft));
      }
    };
    window.addEventListener("keydown", save);
    return () => window.removeEventListener("keydown", save);
  }, [draft, busy, readOnly, onSave]);
  function addTask() {
    if (!task.trim() || draft.tasks.length >= 100) return;
    change("tasks", [
      ...draft.tasks,
      { id: crypto.randomUUID(), text: task.trim(), done: false, due: null },
    ]);
    setTask("");
  }
  return (
    <section className="editor">
      <div className="note-heading">
        <div>
          <label className="group-label">
            コレクション
            <input
              aria-label="コレクション"
              maxLength={80}
              readOnly={readOnly}
              disabled={busy}
              value={draft.group}
              onChange={(e) => change("group", e.target.value)}
            />
          </label>
          <input
            className="note-title"
            aria-label="ノートのタイトル"
            maxLength={200}
            readOnly={readOnly}
            disabled={busy}
            value={draft.title}
            onChange={(e) => change("title", e.target.value)}
          />
          <p className="note-date">
            {new Date(note.updated_at).toLocaleDateString("ja-JP")} · Cornell
            note
          </p>
        </div>
        {!readOnly && (
          <button
            className="primary"
            disabled={busy || !draft.title.trim() || !draft.group.trim()}
            onClick={() => void onSave(editable(draft))}
          >
            <Save size={17} />
            {busy ? "保存中…" : "保存"}
          </button>
        )}
      </div>
      <div className="mobile-tabs" role="tablist" aria-label="ノートの入力欄">
        {[
          ["cue", "問い"],
          ["content", "ノート"],
          ["summary", "まとめ"],
        ].map(([key, label]) => (
          <button
            role="tab"
            aria-selected={tab === key}
            key={key}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="cornell-grid">
        <label
          className={"cue-panel " + (tab === "cue" ? "mobile-active" : "")}
        >
          <span className="section-label">
            CUE <small>問い・キーワード</small>
          </span>
          <textarea
            aria-label="問い・キーワード"
            maxLength={20000}
            readOnly={readOnly}
            disabled={busy}
            value={draft.cue}
            onChange={(e) => change("cue", e.target.value)}
            placeholder={
              "何が大切？\nなぜ、そうなる？\n\n気になる問いを書いてみよう。"
            }
          />
        </label>
        <label
          className={
            "content-panel " + (tab === "content" ? "mobile-active" : "")
          }
        >
          <span className="section-label">
            NOTE <small>自由に書き留める</small>
          </span>
          <textarea
            aria-label="ノート本文"
            maxLength={80000}
            readOnly={readOnly}
            disabled={busy}
            value={draft.content}
            onChange={(e) => change("content", e.target.value)}
            placeholder={
              "学んだこと、考えたこと。\nまだまとまっていなくても、大丈夫。"
            }
          />
        </label>
      </div>
      <div className="note-bottom">
        <label
          className={
            "summary-panel " + (tab === "summary" ? "mobile-active" : "")
          }
        >
          <span className="section-label">
            SUMMARY <small>自分の言葉でまとめる</small>
          </span>
          <textarea
            aria-label="まとめ"
            maxLength={20000}
            readOnly={readOnly}
            disabled={busy}
            value={draft.summary}
            onChange={(e) => change("summary", e.target.value)}
            placeholder="今日の学びを、ひとことで。"
          />
        </label>
        <section className="action-panel">
          <div className="section-label">
            ACTION <small>{progress(draft.tasks)}</small>
          </div>
          {draft.tasks.map((t) => (
            <div className="task-row" key={t.id}>
              <input
                type="checkbox"
                aria-label={t.text + "を完了"}
                checked={t.done}
                disabled={readOnly || busy}
                onChange={(e) =>
                  change(
                    "tasks",
                    draft.tasks.map((x) =>
                      x.id === t.id ? { ...x, done: e.target.checked } : x,
                    ),
                  )
                }
              />
              <span className={t.done ? "completed" : ""}>{t.text}</span>
              <input
                className="task-date"
                type="date"
                aria-label={t.text + "の期日"}
                value={t.due || ""}
                readOnly={readOnly}
                disabled={busy}
                onChange={(e) =>
                  change(
                    "tasks",
                    draft.tasks.map((x) =>
                      x.id === t.id ? { ...x, due: e.target.value || null } : x,
                    ),
                  )
                }
              />
              {!readOnly && (
                <button
                  className="icon-button"
                  aria-label={t.text + "を削除"}
                  disabled={busy}
                  onClick={() =>
                    change(
                      "tasks",
                      draft.tasks.filter((x) => x.id !== t.id),
                    )
                  }
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
          {!readOnly && (
            <form
              className="task-add"
              onSubmit={(e) => {
                e.preventDefault();
                addTask();
              }}
            >
              <input
                aria-label="新しいアクション"
                maxLength={500}
                value={task}
                disabled={busy}
                onChange={(e) => setTask(e.target.value)}
                placeholder="次の一歩を追加"
              />
              <button
                aria-label="アクションを追加"
                disabled={busy || draft.tasks.length >= 100}
              >
                <Plus size={18} />
              </button>
            </form>
          )}
        </section>
      </div>
      <div className="editor-foot">
        問いを見つけて、記録して、振り返る。
        {!readOnly && <span>Ctrl / ⌘ + S で保存</span>}
      </div>
    </section>
  );
}
