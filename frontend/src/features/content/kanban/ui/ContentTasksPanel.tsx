import { useState } from 'react'
import { useI18n } from '../../../../shared/i18n/i18n'
import {
  TASK_PRIORITIES,
  TASK_TYPES,
  type ContentTask,
  type ContentTaskPriority,
  type ContentTaskStatus,
  type ContentTaskType,
} from './contentTypes'

type TaskDraft = {
  title: string
  type: ContentTaskType
  priority: ContentTaskPriority
  due_date: string
  required_for_publish: boolean
  can_block_publish: boolean
  notes: string
}

type Props = {
  selectedItemId: string | null
  tasks: ContentTask[]
  onCreate: (itemId: string, draft: Partial<ContentTask>) => Promise<void>
  onUpdate: (taskId: string, patch: Partial<ContentTask>) => Promise<void>
}

const EMPTY_DRAFT: TaskDraft = {
  title: '',
  type: 'record',
  priority: 'medium',
  due_date: '',
  required_for_publish: false,
  can_block_publish: false,
  notes: '',
}

export default function ContentTasksPanel({ selectedItemId, tasks, onCreate, onUpdate }: Props) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<TaskDraft>(EMPTY_DRAFT)

  async function createTask() {
    if (!selectedItemId || !draft.title.trim()) return
    await onCreate(selectedItemId, {
      title: draft.title.trim(),
      type: draft.type,
      priority: draft.priority,
      due_date: draft.due_date || null,
      required_for_publish: draft.required_for_publish,
      can_block_publish: draft.can_block_publish,
      notes: draft.notes.trim() || null,
    })
    setDraft(EMPTY_DRAFT)
  }

  if (!selectedItemId) {
    return <div className="card muted">{t('contentHub.selectItem')}</div>
  }

  return (
    <div className="card stack">
      <div className="title-strong">{t('contentHub.tasksTitle')}</div>
      <div className="form-grid">
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.title')}</span>
          <input
            id="content-task-new-title"
            value={draft.title}
            onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          />
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.type')}</span>
          <select
            value={draft.type}
            onChange={(event) =>
              setDraft({ ...draft, type: event.target.value as ContentTaskType })
            }
          >
            {TASK_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.priority')}</span>
          <select
            value={draft.priority}
            onChange={(event) =>
              setDraft({ ...draft, priority: event.target.value as ContentTaskPriority })
            }
          >
            {TASK_PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {priority}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.dueDate')}</span>
          <input
            type="date"
            value={draft.due_date}
            onChange={(event) => setDraft({ ...draft, due_date: event.target.value })}
          />
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={draft.required_for_publish}
            onChange={(event) => setDraft({ ...draft, required_for_publish: event.target.checked })}
          />
          {t('contentHub.taskFields.required')}
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={draft.can_block_publish}
            onChange={(event) => setDraft({ ...draft, can_block_publish: event.target.checked })}
          />
          {t('contentHub.taskFields.blocksPublish')}
        </label>
        <label className="form-field wide">
          <span className="field-label">{t('contentHub.taskFields.notes')}</span>
          <textarea
            value={draft.notes}
            onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
          />
        </label>
      </div>
      <button className="btn primary" onClick={() => createTask()}>
        {t('contentHub.add')}
      </button>
      <div className="stack">
        {tasks.map((task) => (
          <EditableTask key={task.id} task={task} onUpdate={onUpdate} />
        ))}
        {tasks.length === 0 && <div className="muted">{t('contentHub.noTasks')}</div>}
      </div>
    </div>
  )
}

function EditableTask({
  task,
  onUpdate,
}: {
  task: ContentTask
  onUpdate: (taskId: string, patch: Partial<ContentTask>) => Promise<void>
}) {
  const { t } = useI18n()

  return (
    <div className="card tight stack">
      <div className="row between">
        <input
          value={task.title ?? ''}
          onChange={(event) => onUpdate(task.id, { title: event.target.value })}
          aria-label={t('contentHub.taskFields.title')}
        />
        <select
          value={task.status}
          onChange={(event) =>
            onUpdate(task.id, { status: event.target.value as ContentTaskStatus })
          }
          aria-label={t('contentHub.taskFields.status')}
        >
          {(['todo', 'doing', 'done'] as const).map((status) => (
            <option key={status} value={status}>
              {t(`contentHub.taskStatus.${status}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="form-grid compact">
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.type')}</span>
          <select
            value={task.type}
            onChange={(event) => onUpdate(task.id, { type: event.target.value as ContentTaskType })}
          >
            {TASK_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.priority')}</span>
          <select
            value={task.priority}
            onChange={(event) =>
              onUpdate(task.id, { priority: event.target.value as ContentTaskPriority })
            }
          >
            {TASK_PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {priority}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.taskFields.dueDate')}</span>
          <input
            type="date"
            value={task.due_date ?? ''}
            onChange={(event) => onUpdate(task.id, { due_date: event.target.value || null })}
          />
        </label>
      </div>
      <div className="control-row">
        <label className="filter-check">
          <input
            type="checkbox"
            checked={task.required_for_publish}
            onChange={(event) => onUpdate(task.id, { required_for_publish: event.target.checked })}
          />
          {t('contentHub.taskFields.required')}
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={task.can_block_publish}
            onChange={(event) => onUpdate(task.id, { can_block_publish: event.target.checked })}
          />
          {t('contentHub.taskFields.blocksPublish')}
        </label>
      </div>
      <textarea
        value={task.notes ?? ''}
        onChange={(event) => onUpdate(task.id, { notes: event.target.value || null })}
        aria-label={t('contentHub.taskFields.notes')}
      />
    </div>
  )
}
