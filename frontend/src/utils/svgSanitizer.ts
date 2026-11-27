/**
 * SVG Sanitizer Utility for Yorvyn
 * 
 * Provides rigorous client-side DOM parsing and sanitization for user-uploaded custom SVG icons.
 * Prevents Cross-Site Scripting (XSS), entity expansions (Billion Laughs), inline scripts,
 * remote script execution, malicious event handlers, and data exfiltration.
 */

export interface SanitizationResult {
  success: boolean;
  sanitizedSvg?: string;
  error?: string;
}

const MAX_SVG_BYTES = 256 * 1024; // 256 KB max limit for category icons

// Disallowed element tags (blacklisted for security)
const DISALLOWED_TAGS = new Set([
  'script',
  'foreignobject',
  'iframe',
  'object',
  'embed',
  'audio',
  'video',
  'source',
  'track',
  'canvas',
  'applet',
  'meta',
  'link',
  'frame',
  'frameset',
  'html',
  'body',
  'head',
  'form',
  'input',
  'button',
  'textarea',
  'select',
  'style' // Strip raw styles to prevent @import or CSS expression vector attacks
]);

// Allowed safe SVG tags
const ALLOWED_TAGS = new Set([
  'svg',
  'g',
  'path',
  'rect',
  'circle',
  'ellipse',
  'line',
  'polyline',
  'polygon',
  'defs',
  'lineargradient',
  'radialgradient',
  'stop',
  'clippath',
  'mask',
  'pattern',
  'symbol',
  'title',
  'desc'
]);

/**
 * Strips dangerous attributes and malicious protocols from an element.
 */
function sanitizeElement(el: Element): boolean {
  const tagName = el.tagName.toLowerCase();

  // Remove completely if forbidden
  if (DISALLOWED_TAGS.has(tagName) || !ALLOWED_TAGS.has(tagName)) {
    return false;
  }

  // Inspect all attributes
  const attrsToRemove: string[] = [];
  for (let i = 0; i < el.attributes.length; i++) {
    const attr = el.attributes[i];
    const attrName = attr.name.toLowerCase();
    const attrValue = attr.value.trim().toLowerCase();

    // 1. Block event handlers (onload, onclick, onerror, etc.)
    if (attrName.startsWith('on')) {
      attrsToRemove.push(attr.name);
      continue;
    }

    // 2. Block javascript:, vbscript:, or data:text/html protocol handlers
    if (
      attrValue.includes('javascript:') ||
      attrValue.includes('vbscript:') ||
      attrValue.includes('data:text/html') ||
      attrValue.includes('expression(')
    ) {
      attrsToRemove.push(attr.name);
      continue;
    }

    // 3. Block xlink:href / href pointing to external remote URLs
    if (attrName === 'href' || attrName === 'xlink:href') {
      if (!attrValue.startsWith('#')) {
        // Only allow local symbol/defs references (#icon-id)
        attrsToRemove.push(attr.name);
        continue;
      }
    }
  }

  attrsToRemove.forEach((a) => el.removeAttribute(a));
  return true;
}

/**
 * Recursively inspects and purges malicious nodes from the SVG DOM.
 */
function cleanDomTree(node: Element): void {
  const children = Array.from(node.children);
  for (const child of children) {
    const isSafe = sanitizeElement(child);
    if (!isSafe) {
      child.remove();
    } else {
      cleanDomTree(child);
    }
  }
}

/**
 * Fallback sanitizer for headless Node.js/SSR environments without native DOMParser.
 */
function fallbackSanitizeSvg(rawSvg: string): SanitizationResult {
  let cleaned = rawSvg;

  // 1. Strip disallowed tags including their content
  for (const tag of DISALLOWED_TAGS) {
    const tagRegex = new RegExp(`<${tag}[^>]*>[\\s\\S]*?<\\/${tag}>|<${tag}[^>]*\\/?>`, 'gi');
    cleaned = cleaned.replace(tagRegex, '');
  }

  // 2. Strip event handlers (onload, onclick, onerror, onmouseover, etc.)
  cleaned = cleaned.replace(/\s+on[a-z0-9_-]+\s*=\s*(['"]).*?\1/gi, '');
  cleaned = cleaned.replace(/\s+on[a-z0-9_-]+\s*=\s*[^\s>]+/gi, '');

  // 3. Strip dangerous protocol schemes (javascript:, vbscript:, data:text/html)
  cleaned = cleaned.replace(/(href|xlink:href)\s*=\s*(['"])(?:javascript|vbscript|data:text\/html):.*?\2/gi, '');

  // 4. Ensure root <svg> exists
  const svgMatch = cleaned.match(/<svg[^>]*>([\s\S]*?)<\/svg>/i);
  if (!svgMatch) {
    return { success: false, error: 'No valid root <svg> element found.' };
  }

  return {
    success: true,
    sanitizedSvg: cleaned.trim()
  };
}

/**
 * Sanitizes an SVG string and returns a safe SVG string.
 */
export function sanitizeSvgString(rawSvg: string): SanitizationResult {
  if (!rawSvg || typeof rawSvg !== 'string') {
    return { success: false, error: 'Empty or invalid SVG content.' };
  }

  // 1. File size check
  const byteSize = typeof Blob !== 'undefined'
    ? new Blob([rawSvg]).size
    : (typeof TextEncoder !== 'undefined' ? new TextEncoder().encode(rawSvg).length : rawSvg.length);
  if (byteSize > MAX_SVG_BYTES) {
    return {
      success: false,
      error: `SVG file exceeds maximum allowed size of 256 KB (got ${(byteSize / 1024).toFixed(1)} KB).`
    };
  }

  // 2. Fast regex pre-check for dangerous tokens
  const lower = rawSvg.toLowerCase();
  if (
    lower.includes('<script') ||
    lower.includes('javascript:') ||
    lower.includes('<!entity') ||
    lower.includes('<!doctype')
  ) {
    // We will parse anyway but be extra vigilant against DTD entity attacks
    if (lower.includes('<!entity')) {
      return { success: false, error: 'XML entities and DTD declarations are disallowed for security.' };
    }
  }

  // 3. Check for DOMParser availability
  const DOMParserClass = typeof DOMParser !== 'undefined' ? DOMParser : (typeof window !== 'undefined' ? window.DOMParser : null);
  if (!DOMParserClass) {
    return fallbackSanitizeSvg(rawSvg);
  }

  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(rawSvg, 'image/svg+xml');

    const parserError = doc.querySelector('parsererror');
    if (parserError) {
      return { success: false, error: `Invalid SVG format: ${parserError.textContent?.slice(0, 120)}` };
    }

    const svgEl = doc.querySelector('svg');
    if (!svgEl) {
      return { success: false, error: 'No valid root <svg> element found.' };
    }

    // Ensure root SVG itself is safe
    if (!sanitizeElement(svgEl)) {
      return { success: false, error: 'Invalid root SVG element attributes.' };
    }

    // Clean all descendants
    cleanDomTree(svgEl);

    // Standardize essential SVG root attributes
    if (!svgEl.getAttribute('xmlns')) {
      svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    }
    if (!svgEl.getAttribute('viewBox')) {
      const w = svgEl.getAttribute('width') || '24';
      const h = svgEl.getAttribute('height') || '24';
      svgEl.setAttribute('viewBox', `0 0 ${parseInt(w, 10) || 24} ${parseInt(h, 10) || 24}`);
    }

    // Ensure default sizing classes
    svgEl.setAttribute('width', '100%');
    svgEl.setAttribute('height', '100%');

    return {
      success: true,
      sanitizedSvg: svgEl.outerHTML
    };
  } catch (err: any) {
    return {
      success: false,
      error: `Failed to sanitize SVG: ${err.message || 'Unknown parser error'}`
    };
  }
}

export const sanitizeSvgIcon = sanitizeSvgString;
