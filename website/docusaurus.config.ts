import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const GH = 'https://github.com/trivoallan/houba';

export default async function createConfig(): Promise<Config> {
  // remark-code-import is ESM-only; dynamic import is the Docusaurus 3 workaround.
  const {default: codeImport} = await import('remark-code-import');

  return {
  title: 'houba',
  tagline: 'The single front door for external container images',
  url: 'https://trivoallan.github.io',
  baseUrl: '/houba/',
  organizationName: 'trivoallan',
  projectName: 'houba',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'throw',

  // .md => CommonMark (NOT MDX), so the machine-generated reference under docs/reference/
  // renders without MDX parse errors. Pages needing JSX opt in with a .mdx extension.
  markdown: {
    format: 'detect',
    mermaid: true,
  },
  themes: [
    '@docusaurus/theme-mermaid',
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        indexBlog: false,
        docsRouteBasePath: '/',
        highlightSearchTermsOnTargetPage: true,
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs',
          routeBasePath: '/', // docs-only mode: docs at the site root
          sidebarPath: './sidebars.ts',
          editUrl: `${GH}/tree/main/docs/`,
          // Contributor docs + working specs + the runnable fixtures are NOT site content.
          exclude: [
            'architecture/**',
            'superpowers/**',
            'roadmap.md',
            '**/_export/**',
          ],
          remarkPlugins: [[codeImport, {allowImportingFromOutside: true}]],
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // The generated reference nests headings 5–6 levels deep; cap the on-page TOC at 3
    // so the right rail stays navigable.
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 3,
    },
    navbar: {
      title: 'houba',
      items: [
        {type: 'doc', docId: 'tutorials/getting-started', label: 'Tutorials', position: 'left'},
        {to: '/how-to', label: 'How-to', position: 'left'},
        {to: '/reference', label: 'Reference', position: 'left'},
        {to: '/explanation', label: 'Explanation', position: 'left'},
        {href: GH, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Deep dives',
          items: [
            {label: 'Architecture & design', href: `${GH}/blob/main/docs/architecture/design.md`},
            {label: 'Roadmap & product thesis', href: `${GH}/blob/main/docs/roadmap.md`},
            {label: 'Decision records', href: `${GH}/tree/main/docs/architecture/decisions`},
            {label: 'GitHub', href: GH},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Tristan Rivoallan and contributors. Apache-2.0.`,
    },
  } satisfies Preset.ThemeConfig,
  };
}
