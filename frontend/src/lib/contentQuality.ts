const INVALID_CONTENT_PHRASES = [
  "i've analyzed the json data",
  "i've analyzed",
  'i have analyzed',
  'json data',
  'provided json',
  'overall structure',
  'key findings',
  'article highlights',
  'potential use cases',
  'potential uses',
  'important considerations',
  'this json represents',
  'the data represents',
  'key fields',
  'further considerations',
  'this data could',
  'this topic could be used',
  'for a python developer, this is a strong content angle',
  "if you'd like",
];

export function looksLikeInvalidGeneratedContent(value?: string | null) {
  const text = String(value || '').trim().toLowerCase();
  if (!text) return false;
  return INVALID_CONTENT_PHRASES.some((phrase) => text.includes(phrase));
}

export function shortText(value?: string | null, limit = 180) {
  const text = String(value || '').trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trim()}...`;
}
