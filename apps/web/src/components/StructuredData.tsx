/**
 * `<StructuredData>` — render one or more JSON-LD `<script>` tags.
 *
 * Server component (no `"use client"`) so the JSON-LD payload ends up
 * in the initial HTML that crawlers and AI agents receive. React does
 * not auto-render `<script type="application/ld+json">` from a server
 * tree (the default `next/script` strategy defers execution), and
 * Google / schema.org tooling expects the literal element in the
 * `<head>` or body — NOT a lazy/hydrated chunk.
 *
 * The architects's `StructuredDataNode` union guarantees the input is
 * JSON-serializable (no Date, no functions, no undefined fields). We
 * `JSON.stringify` it directly into the `<script>` body.
 *
 * Usage:
 *   <StructuredData data={buildOrganizationJsonLd()} />
 *   <StructuredData data={[buildOrganizationJsonLd(), buildWebSiteJsonLd(locale)]} />
 *
 * The optional `id` becomes `<script id="<id>-N">` so test code can
 * query a specific payload by attribute.
 */

import type { StructuredDataNode } from '@ai-news-scraper/shared'

interface Props {
  /** One schema.org node, or an array of sibling nodes (Organization + WebSite). */
  data: StructuredDataNode | StructuredDataNode[]
  /** Optional id prefix; rendering `<script id="<id>-0" />`, `<script id="<id>-1" />`, ... */
  id?: string
}

export function StructuredData({ data, id }: Props) {
  const nodes = Array.isArray(data) ? data : [data]
  return (
    <>
      {nodes.map((node, i) => (
        <script
          key={`${node['@type']}-${i}`}
          type="application/ld+json"
          {...(id ? { id: `${id}-${i}` } : {})}
          // The shape is a JSON-serializable Schema.org object; this is
          // safe by construction (no functions, no Date, no undefined).
          dangerouslySetInnerHTML={{ __html: JSON.stringify(node) }}
        />
      ))}
    </>
  )
}
