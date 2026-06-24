import { useI18n } from '../../../../shared/i18n/i18n'
import type { ChecklistTemplate, PlanningView } from './contentTypes'

type Props = {
  planning: PlanningView | null
  templates: ChecklistTemplate[]
  selectedItemId: string | null
  onApplyTemplate: (templateId: string) => Promise<void>
}

export default function ContentPlanningPanel({
  planning,
  templates,
  selectedItemId,
  onApplyTemplate,
}: Props) {
  const { t } = useI18n()

  if (!selectedItemId || !planning) {
    return <div className="card muted">{t('contentHub.selectItemForPlanning')}</div>
  }

  const matchingTemplates = templates.filter(
    (template) =>
      (!template.applies_to_platform ||
        template.applies_to_platform === planning.item.platform) &&
      (!template.applies_to_type || template.applies_to_type === planning.item.type)
  )

  return (
    <div className="card stack">
      <div className="section-head">
        <div>
          <h3 className="no-margin">{t('contentHub.checklistStatus')}</h3>
          <div className="small muted">
            {planning.open_task_count} {t('contentHub.openTasks')} /{' '}
            {planning.required_open_count} {t('contentHub.requiredOpenTasks')}
          </div>
        </div>
        <div className={planning.publish_ready ? 'pill success' : 'pill'}>
          {planning.publish_ready ? t('contentHub.publishReady') : t('contentHub.notReady')}
        </div>
      </div>
      <div>
        {t('contentHub.readiness')}: <strong>{planning.readiness_score}%</strong>
      </div>
      {planning.blockers.length > 0 && (
        <div className="stack">
          {planning.blockers.map((blocker) => (
            <div key={blocker} className="pill">
              {blocker}
            </div>
          ))}
        </div>
      )}
      <div className="title-strong">{t('contentHub.applyTemplate')}</div>
      <div className="control-row">
        {matchingTemplates.map((template) => (
          <button key={template.id} className="btn" onClick={() => onApplyTemplate(template.id)}>
            {template.name}
          </button>
        ))}
        {matchingTemplates.length === 0 && (
          <div className="muted">{t('contentHub.noMatchingTemplates')}</div>
        )}
      </div>
      <div className="stack">
        {planning.tasks.map((task) => (
          <div key={task.id} className="row between card tight">
            <div>
              <strong>{task.title || t('contentHub.taskFallback')}</strong>
              <div className="small muted">
                {task.type} / {task.priority}
                {task.due_date ? ` / ${task.due_date}` : ''}
              </div>
            </div>
            <span className="pill">{t(`contentHub.taskStatus.${task.status}`)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
