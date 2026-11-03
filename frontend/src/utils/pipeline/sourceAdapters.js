// Keep in sync with the AdapterRegistry registrations in collection.py
// (register_builtin_adapters for public sources; wechat_rss for 公众号 RSS).
// A source type in the database does not imply an available collector.
// Adapter capabilities are not the Excel whitelist. News/paper creation stays
// closed until that list is supplied; existing sources must remain visible.
export const sourceAdapters = [
  { key: 'pipechina_group_news', type: 'website', label: '国家管网资讯' },
  { key: 'crossref_works', type: 'paper', label: 'Crossref 论文' },
  { key: 'wechat_rss', type: 'wechat', label: '公众号 RSS' }
]
export const adaptersForSource = type => sourceAdapters.filter(item => item.type === (type === 'news' ? 'website' : type))
export const canCreateSourceType = type => type === 'wechat'
export function supportsSourceAdapter(source) {
  return adaptersForSource(source?.type || source?.sourceType).some(item => item.key === (source?.adapter || source?.adapter_key || source?.adapterKey))
}
