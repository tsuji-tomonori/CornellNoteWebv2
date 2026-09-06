export type Task = {
  id: string;
  text: string;
  done: boolean;
  due: string | null;
};
export type NoteInput = {
  title: string;
  group: string;
  cue: string;
  content: string;
  summary: string;
  tasks: Task[];
};
export type Note = NoteInput & {
  id: string;
  version: number;
  updated_at: string;
};
export const blankNote = (): NoteInput => ({
  title: "無題のノート",
  group: "未分類",
  cue: "",
  content: "",
  summary: "",
  tasks: [],
});
export const editable = (note: NoteInput): NoteInput => ({
  title: note.title,
  group: note.group,
  cue: note.cue,
  content: note.content,
  summary: note.summary,
  tasks: note.tasks,
});
export function groupedNotes(
  notes: Note[],
  query: string,
  group: string,
): Record<string, Note[]> {
  const result: Record<string, Note[]> = Object.create(null);
  for (const note of notes) {
    if (group && note.group !== group) continue;
    if (
      !`${note.title} ${note.content} ${note.cue} ${note.summary}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase())
    )
      continue;
    (result[note.group] ??= []).push(note);
  }
  return result;
}
export function progress(tasks: Task[]): string {
  return `${tasks.filter((t) => t.done).length} / ${tasks.length}`;
}
