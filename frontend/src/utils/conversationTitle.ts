const DEFAULT_TITLE = 'New Chat';
const MAX_TITLE_LENGTH = 18;

const LEADING_PHRASES = [
  /^请(你)?帮我/,
  /^帮我/,
  /^请/,
  /^麻烦(你)?/,
  /^我想/,
  /^能不能/,
  /^可以/,
  /^please\s+/i,
  /^help\s+me\s+/i,
  /^can\s+you\s+/i,
];

const TOPIC_PATTERNS: Array<[RegExp, string]> = [
  [/C\+\+.*线段树|线段树.*C\+\+/i, 'C++ 线段树实现'],
  [/Python.*爬虫|爬虫.*Python/i, 'Python 爬虫实现'],
  [/README|readme/i, 'README 总结'],
  [/简历|resume/i, '简历项目描述'],
  [/架构|architecture/i, '架构设计'],
  [/登录|注册|认证|JWT/i, '用户认证'],
  [/数据库|MySQL|SQLAlchemy|Alembic/i, '数据库设计'],
  [/前端|React|页面|UI/i, '前端界面优化'],
  [/流式|SSE|stream/i, '流式事件输出'],
];

export function generateConversationTitle(content: string): string {
  const normalized = normalizeContent(content);
  for (const [pattern, title] of TOPIC_PATTERNS) {
    if (pattern.test(normalized)) {
      return title;
    }
  }

  const cleaned = stripLeadingPhrases(normalized)
    .replace(/[，。！？；：,.!?;:]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (!cleaned) {
    return DEFAULT_TITLE;
  }

  return trimTitle(cleaned);
}

export function shouldAutoTitleConversation(title: string, messageCount: number): boolean {
  return messageCount === 0 && title.trim().toLowerCase() === DEFAULT_TITLE.toLowerCase();
}

function normalizeContent(content: string): string {
  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/\r?\n+/g, ' ')
    .trim();
}

function stripLeadingPhrases(content: string): string {
  let result = content.trim();
  for (const phrase of LEADING_PHRASES) {
    result = result.replace(phrase, '').trim();
  }
  return result;
}

function trimTitle(content: string): string {
  const words = content.split(/\s+/).filter(Boolean);
  const hasChinese = /[\u4e00-\u9fff]/.test(content);
  if (!hasChinese && words.length > 0) {
    return words.slice(0, 5).join(' ').slice(0, MAX_TITLE_LENGTH).trim();
  }
  return Array.from(content).slice(0, MAX_TITLE_LENGTH).join('').trim();
}
