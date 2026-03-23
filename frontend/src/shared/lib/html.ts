export function stripHtml(value: string) {
  return value.replace(/<[^>]*>/g, '').trim()
}
