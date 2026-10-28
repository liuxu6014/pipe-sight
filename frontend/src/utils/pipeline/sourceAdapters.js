// Keep in sync with register_builtin_adapters in public_source_bridge.py.
// A source type in the database does not imply an available collector.
export const sourceAdapters = [
  { key: 'pipechina_group_news', type: 'website', label: '国家管网资讯' },
  { key: 'crossref_works', type: 'paper', label: 'Crossref 论文' }
]
export const adaptersForSource = type => sourceAdapters.filter(item => item.type === (type === 'news' ? 'website' : type))
export function supportsSourceAdapter(source) {
  return adaptersForSource(source?.type || source?.sourceType).some(item => item.key === (source?.adapter || source?.adapter_key || source?.adapterKey))
}
