import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const GH = 'https://github.com/trivoallan/houba';

const config: Config = {
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
  themes: ['@docusaurus/theme-mermaid'],

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
        {type: 'doc', docId: 'how-to/index', label: 'How-to', position: 'left'},
        {type: 'doc', docId: 'reference/mirror-policy', label: 'Reference', position: 'left'},
        {type: 'doc', docId: 'explanation/index', label: 'Explanation', position: 'left'},
        {href: GH, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [],
      copyright: `Copyright © ${new Date().getFullYear()} Tristan Rivoallan and contributors. Apache-2.0.`,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
