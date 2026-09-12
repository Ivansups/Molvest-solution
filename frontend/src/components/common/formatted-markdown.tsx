"use client";

import Markdown, { type Components } from "react-markdown";
import { cn } from "@/src/lib/utils";

const MARKDOWN_ELEMENTS = [
  "p",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "h1",
  "h2",
  "h3",
  "a",
  "code",
  "pre",
  "blockquote",
] as const;

const markdownComponents: Components = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 text-sm leading-6 text-foreground">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-6">{children}</li>,
  h1: ({ children }) => (
    <h3 className="mb-2 mt-3 text-sm font-semibold text-secondary first:mt-0">
      {children}
    </h3>
  ),
  h2: ({ children }) => (
    <h3 className="mb-2 mt-3 text-sm font-semibold text-secondary first:mt-0">
      {children}
    </h3>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-3 text-sm font-semibold text-secondary first:mt-0">
      {children}
    </h3>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-secondary">{children}</strong>
  ),
  em: ({ children }) => <em>{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline underline-offset-2"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-white/80 px-1 py-0.5 text-[0.85em]">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded-xl bg-white/80 p-3 text-[0.85em] last:mb-0">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 border-primary/30 pl-3 text-slate-600 last:mb-0">
      {children}
    </blockquote>
  ),
};

function breakCollapsedMarkdown(content: string): string {
  // GigaChat часто склеивает разметку в одну строку: «### Шаги: 1. **foo** - bar».
  return content
    .replace(/(^| )(#{1,3} )/g, "\n\n$2")
    .replace(/ (\d+\. )/g, "\n$1")
    .replace(/ ([-*] )/g, "\n$1")
    .trim();
}

/** Безопасный Markdown: без HTML, со склейкой однострочных списков GigaChat. */
export function FormattedMarkdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={cn("text-sm leading-6 text-foreground", className)}>
      <Markdown
        skipHtml
        unwrapDisallowed
        allowedElements={[...MARKDOWN_ELEMENTS]}
        components={markdownComponents}
      >
        {breakCollapsedMarkdown(children)}
      </Markdown>
    </div>
  );
}
