// 轻量 Markdown 转纯文本:去掉 ** 加粗、# 标题符、无序列表符,保留换行与数字编号
export const mdToText = (text) => {
  if (!text) return ''
  return String(text)
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^[-*]\s+/gm, '· ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
