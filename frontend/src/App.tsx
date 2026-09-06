import { useEffect, useState } from "react";
import {
  BookOpen,
  Plus,
  Search,
  Share2,
  ArrowLeft,
  LogOut,
  Folder,
  CheckSquare,
  Leaf,
  Trash2,
  ArrowUpRight,
  Copy,
  Link2,
  X,
} from "lucide-react";
import { api } from "./api";
import { loginCognito, localMode, logout } from "./auth";
import {
  blankNote,
  groupedNotes,
  progress,
  type Note,
  type NoteInput,
} from "./domain";
import { Editor } from "./Editor";
export function App({ initialError = "" }: { initialError?: string }) {
  const [logged, setLogged] = useState(
    !!sessionStorage.getItem("access_token"),
  );
  const [notes, setNotes] = useState<Note[]>([]);
  const [selected, setSelected] = useState<Note | null>(null);
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const sharedToken = new URLSearchParams(location.hash.slice(1)).get("share");
  const [shared, setShared] = useState<Note | null>(null);
  const load = async () => {
    try {
      setNotes(await api<Note[]>("/notes"));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    const expired = () => {
      setLogged(false);
      setNotes([]);
      setSelected(null);
      setError("セッションが切れました。再ログインしてください");
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (logged && !sharedToken) void load();
  }, [logged, sharedToken]);
  useEffect(() => {
    if (sharedToken)
      api<Note>("/shared/" + encodeURIComponent(sharedToken))
        .then(setShared)
        .catch((e) => setError(e.message));
  }, [sharedToken]);
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  const leave = () =>
    !dirty || confirm("未保存の変更があります。破棄して移動しますか？");
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
      setStatus("操作を完了できませんでした");
    } finally {
      setBusy(false);
    }
  }
  async function create() {
    if (!leave()) return;
    await action(async () => {
      const note = await api<Note>("/notes", "POST", blankNote());
      setSelected(note);
      setDirty(false);
      setStatus("保存済み");
      await load();
    });
  }
  async function save(data: NoteInput) {
    if (!selected) return;
    setStatus("保存中…");
    await action(async () => {
      const note = await api<Note>("/notes/" + selected.id, "PUT", {
        ...data,
        version: selected.version,
      });
      setSelected(note);
      setDirty(false);
      setStatus("保存しました");
      await load();
    });
  }
  if (sharedToken)
    return (
      <div className="shared-shell">
        <Brand />
        <span className="pill">
          <Link2 size={14} />
          共有ノート · 閲覧のみ
        </span>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {shared ? (
          <Editor
            key={shared.id}
            note={shared}
            readOnly
            onSave={async () => {}}
            onDirty={() => {}}
            busy={false}
          />
        ) : (
          !error && <p>読み込み中…</p>
        )}
      </div>
    );
  if (!logged)
    return (
      <LoginView
        error={error}
        onError={setError}
        onLogin={() => setLogged(true)}
      />
    );
  const groups = [...new Set(notes.map((n) => n.group))].sort();
  const shown = groupedNotes(notes, query, group);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <p className="eyebrow">YOUR WORKSPACE</p>
        <button
          className={!group ? "nav active" : "nav"}
          onClick={() => {
            if (leave()) {
              setSelected(null);
              setDirty(false);
              setGroup("");
            }
          }}
        >
          <BookOpen size={18} />
          すべてのノート<span>{notes.length}</span>
        </button>
        <p className="eyebrow spaced">COLLECTIONS</p>
        {groups.map((g) => (
          <button
            className={group === g ? "nav active" : "nav"}
            key={g}
            onClick={() => {
              if (leave()) {
                setSelected(null);
                setDirty(false);
                setGroup(g);
              }
            }}
          >
            <Folder size={17} />
            {g}
          </button>
        ))}
        <div className="sidebar-bottom">
          <div className="tip">
            <Leaf size={20} />
            <p>
              書いて、問いかけて、
              <br />
              自分の言葉にする。
            </p>
            <small>小さな気づきが、知識になる。</small>
          </div>
          <button
            className="nav"
            onClick={() => {
              if (leave()) logout();
            }}
          >
            <LogOut size={17} />
            ログアウト
          </button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            <span className="muted">ワークスペース</span> /{" "}
            {selected ? "ノートを編集" : "マイノート"}
          </span>
          <span className="pill">Personal workspace</span>
        </header>
        <div className="workspace">
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          {selected ? (
            <>
              <div className="editor-toolbar">
                <button
                  className="text-button"
                  onClick={() => {
                    if (leave()) {
                      setSelected(null);
                      setDirty(false);
                    }
                  }}
                >
                  <ArrowLeft size={17} />
                  ノート一覧
                </button>
                <span role="status" className="save-status">
                  {dirty ? "未保存の変更" : status}
                </span>
                <button
                  disabled={busy || dirty}
                  onClick={() => {
                    setShareUrl("");
                    setShareOpen(true);
                  }}
                >
                  <Share2 size={16} />
                  共有
                </button>
                <button
                  className="icon-button"
                  aria-label="ノートを削除"
                  disabled={busy}
                  onClick={() => {
                    if (confirm("このノートを削除しますか？"))
                      void action(async () => {
                        await api("/notes/" + selected.id, "DELETE");
                        setSelected(null);
                        setDirty(false);
                        await load();
                      });
                  }}
                >
                  <Trash2 size={17} />
                </button>
              </div>
              <Editor
                key={selected.id}
                note={selected}
                onSave={save}
                onDirty={() => setDirty(true)}
                busy={busy}
              />
            </>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">A LITTLE SPACE FOR BIG IDEAS</p>
                  <h1>
                    {group || "マイノート"}
                    <span className="mint-period">.</span>
                  </h1>
                  <p className="muted">今日の気づきを、明日の知識に。</p>
                </div>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => void create()}
                >
                  <Plus size={18} />
                  新しいノート
                </button>
              </div>
              <div className="overview">
                <div>
                  <BookOpen />
                  <strong>{notes.length}</strong>
                  <span>ノート</span>
                </div>
                <div>
                  <Folder />
                  <strong>{groups.length}</strong>
                  <span>コレクション</span>
                </div>
                <div>
                  <CheckSquare />
                  <strong>
                    {
                      notes.flatMap((n) => n.tasks).filter((t) => !t.done)
                        .length
                    }
                  </strong>
                  <span>これからのアクション</span>
                </div>
              </div>
              <div className="list-tools">
                <h2>あなたの記録</h2>
                <label className="search">
                  <Search size={17} />
                  <input
                    aria-label="ノートを検索"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="タイトルや内容で検索"
                  />
                </label>
              </div>
              {Object.entries(shown).map(([name, items]) => (
                <section className="collection" key={name}>
                  <h3>
                    <Folder size={16} />
                    {name}
                    <span>{items.length}</span>
                  </h3>
                  <div className="note-grid">
                    {items.map((note) => (
                      <button
                        className="note-card"
                        key={note.id}
                        onClick={() => {
                          setSelected(note);
                          setDirty(false);
                          setStatus("保存済み");
                        }}
                      >
                        <div className="card-top">
                          <span className="note-symbol">
                            <BookOpen size={19} />
                          </span>
                          <ArrowUpRight size={17} />
                        </div>
                        <h4>{note.title}</h4>
                        <p>
                          {note.summary ||
                            note.content ||
                            "問いと記録を書いて、考えを整理しましょう。"}
                        </p>
                        <div className="card-foot">
                          <time>
                            {new Date(note.updated_at).toLocaleDateString(
                              "ja-JP",
                            )}
                          </time>
                          <span>
                            <CheckSquare size={14} />
                            {progress(note.tasks)}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
              ))}
              {Object.keys(shown).length === 0 && (
                <div className="empty">
                  <BookOpen size={36} />
                  <h2>
                    {query
                      ? "一致するノートはありません"
                      : "最初の一枚から、はじめよう。"}
                  </h2>
                  <p>問い・記録・まとめ。3つの欄が思考を整えます。</p>
                  <button onClick={() => void create()}>
                    <Plus size={17} />
                    ノートを作成
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>
      {shareOpen && selected && (
        <div className="modal-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="share-heading"
            className="modal"
          >
            <button
              className="close"
              aria-label="共有画面を閉じる"
              onClick={() => setShareOpen(false)}
            >
              <X size={18} />
            </button>
            <span className="note-symbol">
              <Share2 />
            </span>
            <h2 id="share-heading">ノートを共有</h2>
            <p>
              リンクを知っている人は、ログインせずにこのノートとチェック項目を閲覧できます。編集はできません。有効期限は7日間です。
            </p>
            {shareUrl ? (
              <>
                <label>
                  共有リンク
                  <input readOnly value={shareUrl} />
                </label>
                <button
                  onClick={() =>
                    void action(async () => {
                      await navigator.clipboard.writeText(shareUrl);
                      setStatus("リンクをコピーしました");
                    })
                  }
                >
                  <Copy size={16} />
                  リンクをコピー
                </button>
              </>
            ) : (
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    const result = await api<{ token: string }>(
                      "/notes/" + selected.id + "/share",
                      "POST",
                    );
                    setShareUrl(location.origin + "/#share=" + result.token);
                  })
                }
              >
                <Link2 size={16} />
                閲覧リンクを発行
              </button>
            )}
            <button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await api("/notes/" + selected.id + "/share", "DELETE");
                  setShareUrl("");
                  setShareOpen(false);
                  setStatus("共有を解除しました");
                })
              }
            >
              共有を解除
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span>
        <BookOpen size={23} />
      </span>
      <b>
        Cornell<span className="brand-dot">.</span>
      </b>
    </div>
  );
}
function LoginView({
  error,
  onError,
  onLogin,
}: {
  error: string;
  onError: (v: string) => void;
  onLogin: () => void;
}) {
  const [user, setUser] = useState("alice");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    onError("");
    try {
      if (localMode) {
        const token = await api<{ access_token: string }>(
          "/auth/local",
          "POST",
          { username: user, password },
        );
        sessionStorage.setItem("access_token", token.access_token);
        onLogin();
      } else await loginCognito();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-layout">
      <section className="login-story">
        <Brand />
        <div>
          <p className="eyebrow">THINK. CONNECT. REMEMBER.</p>
          <h1>
            思考を、
            <br />
            育てるノート。
          </h1>
          <p>
            ただ書き留めるだけでなく、
            <br />
            問いを見つけて、自分の言葉に。
          </p>
          <div className="mini-note">
            <div>
              <span>CUE</span>
              <b>なぜ、そうなる？</b>
            </div>
            <div>
              <span>NOTE</span>
              <p>
                気づいたことを書き留める。
                <br />
                考えと考えを、つないでいく。
              </p>
            </div>
            <footer>
              <span>SUMMARY</span>今日の学びを、ひとことで。
            </footer>
          </div>
        </div>
        <small>CORNELL METHOD · YOUR EVERYDAY COMPANION</small>
      </section>
      <section className="login-form">
        <span className="pill">
          <Leaf size={14} />A fresh page awaits
        </span>
        <h2>おかえりなさい。</h2>
        <p className="muted">あなたのノートの続きを、ここから。</p>
        <form onSubmit={(e) => void submit(e)}>
          {localMode && (
            <>
              <label>
                ユーザー
                <select value={user} onChange={(e) => setUser(e.target.value)}>
                  <option value="alice">Alice</option>
                  <option value="bob">Bob</option>
                </select>
              </label>
              <label>
                パスワード
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <small>ローカル検証用アカウント</small>
            </>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "ログイン中…" : "ログイン"}
            <ArrowUpRight size={18} />
          </button>
        </form>
        <p className="login-foot">
          書く。問いかける。振り返る。
          <br />
          あなたらしい学びのリズムを。
        </p>
      </section>
    </div>
  );
}
