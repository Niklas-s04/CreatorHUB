import { parseKnowledgeDocsPage } from './validators'

describe('knowledge validators', () => {
  it('parses paginated knowledge response with metadata safely', () => {
    const parsed = parseKnowledgeDocsPage({
      items: [
        {
          id: 'doc-1',
          type: 'policy',
          title: 'Policy',
          content: 'Content',
          source_review_status: 'approved',
          trust_level: 'high',
          is_outdated: false,
          current_version: 3,
          versions: [
            {
              id: 'v-1',
              version_number: 3,
              title: 'Policy',
              type: 'policy',
              workflow_status: 'approved',
              source_review_status: 'approved',
              trust_level: 'high',
              is_outdated: false,
              created_at: '2026-03-30T10:00:00Z',
            },
          ],
          draft_links: [
            {
              id: 'l-1',
              email_draft_id: 'd-1',
              linked_at: '2026-03-30T12:00:00Z',
            },
          ],
        },
      ],
    })

    expect(parsed).toHaveLength(1)
    expect(parsed[0].id).toBe('doc-1')
    expect(parsed[0].source_review_status).toBe('approved')
    expect(parsed[0].trust_level).toBe('high')
    expect(parsed[0].current_version).toBe(3)
    expect(parsed[0].versions?.[0]?.version_number).toBe(3)
    expect(parsed[0].draft_links?.[0]?.email_draft_id).toBe('d-1')
  })
})
