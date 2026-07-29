// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';
import starlightLinksValidator from 'starlight-links-validator';

// https://astro.build/config
export default defineConfig({
	site: 'https://observability.opensearch.org',
	base: '/docs',
	redirects: {
		'/get-started': '/get-started/installation/',
		'/sdks/python': '/send-data/ai-agents/python/',
		'/sdks/javascript': '/send-data/ai-agents/typescript/',
		'/sdks/python-experiments': '/ai-observability/evaluation/',
		'/sdks/python-retrieval': '/ai-observability/evaluation/',
		'/sdks/faq': '/ai-observability/getting-started/',
		'/sdks': '/send-data/ai-agents/',
		'/send-data/ai-agents/javascript': '/send-data/ai-agents/typescript/',
		'/dashboards/transformations': '/dashboards/visualize/transformations/',
		'/dashboards/visualize/visualization-editor': '/dashboards/visualize/',
		'/dashboards/visualize/visualization-editor/area-chart': '/dashboards/visualize/area-chart/',
		'/dashboards/visualize/visualization-editor/bar-chart': '/dashboards/visualize/bar-chart/',
		'/dashboards/visualize/visualization-editor/bar-gauge-chart': '/dashboards/visualize/bar-gauge-chart/',
		'/dashboards/visualize/visualization-editor/configuring-visualizations': '/dashboards/visualize/configuring-visualizations/',
		'/dashboards/visualize/visualization-editor/configuring-visualizations/thresholds': '/dashboards/visualize/configuring-visualizations/thresholds/',
		'/dashboards/visualize/visualization-editor/configuring-visualizations/value-calculations': '/dashboards/visualize/configuring-visualizations/value-calculations/',
		'/dashboards/visualize/visualization-editor/gauge-chart': '/dashboards/visualize/gauge-chart/',
		'/dashboards/visualize/visualization-editor/heatmap-chart': '/dashboards/visualize/heatmap-chart/',
		'/dashboards/visualize/visualization-editor/histogram-chart': '/dashboards/visualize/histogram-chart/',
		'/dashboards/visualize/visualization-editor/line-chart': '/dashboards/visualize/line-chart/',
		'/dashboards/visualize/visualization-editor/metric-chart': '/dashboards/visualize/metric-chart/',
		'/dashboards/visualize/visualization-editor/pie-chart': '/dashboards/visualize/pie-chart/',
		'/dashboards/visualize/visualization-editor/scatter-chart': '/dashboards/visualize/scatter-chart/',
		'/dashboards/visualize/visualization-editor/state-timeline-chart': '/dashboards/visualize/state-timeline-chart/',
		'/dashboards/visualize/visualization-editor/table-chart': '/dashboards/visualize/table-chart/',
	},
	integrations: [
		mermaid({
			autoTheme: true,
		}),
		starlight({
			title: 'OpenSearch - Observability Stack',
			head: [
				{
					tag: 'script',
					attrs: {
						async: true,
						src: 'https://www.googletagmanager.com/gtag/js?id=G-BQV14XK08F',
					},
				},
				{
					tag: 'script',
					content: `
						window.dataLayer = window.dataLayer || [];
						function gtag(){dataLayer.push(arguments);}
						gtag('js', new Date());
						gtag('config', 'G-BQV14XK08F');
					`,
				},
			],
			plugins: [starlightLinksValidator({
				errorOnLocalLinks: false,
			})],
			logo: {
				src: './src/assets/opensearch-logo-darkmode.svg',
			},
			editLink: {
				baseUrl: 'https://github.com/opensearch-project/observability-stack/edit/main/docs/starlight-docs/',
			},
			customCss: [
				'./src/styles/custom.css',
			],
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/opensearch-project/observability-stack' }],
			components: {
				Header: './src/components/CustomHeader.astro',
				PageSidebar: './src/components/PageSidebar.astro',
				Sidebar: './src/components/Sidebar.astro',
			},
			sidebar: [
				{
					label: 'Overview',
					link: '/',
				},
				{
					label: 'Get Started',
					collapsed: true,
					items: [
						{ label: 'Installation', link: '/get-started/installation/' },
						{ label: 'Platform Overview', link: '/get-started/overview/' },
						{ label: 'Core Concepts', link: '/get-started/core-concepts/' },
						{
							label: 'Quickstart',
							items: [
								{ label: 'Ingest Your First Traces', link: '/get-started/quickstart/first-traces/' },
								{ label: 'Create Your First Dashboard', link: '/get-started/quickstart/first-dashboard/' },
							],
						},
					],
				},
				{
					label: 'Deploy to Cloud',
					collapsed: true,
					items: [
						{ label: 'Overview', link: '/deploy/' },
						{ label: 'Kubernetes (Helm)', link: '/deploy/kubernetes/' },
						{ label: 'AWS Managed Services', link: '/deploy/aws/' },
					],
				},
				{
					label: 'Send Data',
					collapsed: true,
					items: [
						{ label: 'Overview', link: '/send-data/' },
						{
							label: 'OpenTelemetry',
							autogenerate: { directory: 'send-data/opentelemetry' },
						},
						{
							label: 'Applications',
							autogenerate: { directory: 'send-data/applications' },
						},
						{
							label: 'Infrastructure',
							autogenerate: { directory: 'send-data/infrastructure' },
						},
						{
							label: 'From Vendor Agents',
							autogenerate: { directory: 'send-data/from-vendor' },
						},
						{
							label: 'Data Pipeline',
							autogenerate: { directory: 'send-data/data-pipeline' },
						},
					],
				},
				{
					label: 'PPL - Query Language',
					collapsed: true,
					items: [
						{ label: 'Overview', link: '/ppl/' },
						{ label: 'Command Reference', link: '/ppl/commands/' },
						{
							label: 'Search & Filter',
							collapsed: true,
							items: [
								{ label: 'search', link: '/ppl/commands/search/' },
								{ label: 'where', link: '/ppl/commands/where/' },
							],
						},
						{
							label: 'Fields & Transformation',
							collapsed: true,
							items: [
								{ label: 'fields', link: '/ppl/commands/fields/' },
								{ label: 'eval', link: '/ppl/commands/eval/' },
								{ label: 'rename', link: '/ppl/commands/rename/' },
								{ label: 'fillnull', link: '/ppl/commands/fillnull/' },
								{ label: 'expand', link: '/ppl/commands/expand/' },
								{ label: 'flatten', link: '/ppl/commands/flatten/' },
							],
						},
						{
							label: 'Aggregation & Statistics',
							collapsed: true,
							items: [
								{ label: 'stats', link: '/ppl/commands/stats/' },
								{ label: 'eventstats', link: '/ppl/commands/eventstats/' },
								{ label: 'streamstats', link: '/ppl/commands/streamstats/' },
								{ label: 'timechart', link: '/ppl/commands/timechart/' },
								{ label: 'trendline', link: '/ppl/commands/trendline/' },
							],
						},
						{
							label: 'Sorting & Limiting',
							collapsed: true,
							items: [
								{ label: 'sort', link: '/ppl/commands/sort/' },
								{ label: 'head', link: '/ppl/commands/head/' },
								{ label: 'dedup', link: '/ppl/commands/dedup/' },
								{ label: 'top', link: '/ppl/commands/top/' },
								{ label: 'rare', link: '/ppl/commands/rare/' },
							],
						},
						{
							label: 'Text Extraction',
							collapsed: true,
							items: [
								{ label: 'parse', link: '/ppl/commands/parse/' },
								{ label: 'grok', link: '/ppl/commands/grok/' },
								{ label: 'rex', link: '/ppl/commands/rex/' },
								{ label: 'patterns', link: '/ppl/commands/patterns/' },
								{ label: 'spath', link: '/ppl/commands/spath/' },
							],
						},
						{
							label: 'Data Combination',
							collapsed: true,
							items: [
								{ label: 'join', link: '/ppl/commands/join/' },
								{ label: 'lookup', link: '/ppl/commands/lookup/' },
							],
						},
						{
							label: 'Machine Learning',
							collapsed: true,
							items: [
								{ label: 'ml', link: '/ppl/commands/ml/' },
							],
						},
						{
							label: 'Metadata',
							collapsed: true,
							items: [
								{ label: 'describe', link: '/ppl/commands/describe/' },
							],
						},
						{ label: 'Function Reference', link: '/ppl/functions/' },
						{ label: 'Observability Examples', link: '/ppl/examples/' },
						{ label: 'PPL Query Builder', link: '/ppl/query-builder/' },
						{ label: 'PPL for DQL/Lucene Users', link: '/ppl/dql-lucene-users/' },
						{ label: 'PPL for SPL Users', link: '/ppl/spl-users/' },
					],
				},
				{
					label: 'Discover',
					collapsed: true,
					autogenerate: { directory: 'investigate' },
				},
				{
					label: 'Agent Observability',
					collapsed: true,
					items: [
						{ label: 'Overview', link: '/ai-observability/' },
						{ label: 'Getting Started', link: '/ai-observability/getting-started/' },
						{ label: 'Framework Integrations', link: '/send-data/ai-agents/integrations/' },
						{ label: 'Agent Tracing', link: '/ai-observability/agent-tracing/' },
						{ label: 'Agent Graph & Path', link: '/ai-observability/agent-tracing/graph/' },
						{ label: 'Evaluation & Scoring', link: '/ai-observability/evaluation/' },
						{ label: 'Evaluation Integrations', link: '/ai-observability/evaluation-integrations/' },
					],
				},
				{
					label: 'Application Monitoring',
					collapsed: true,
					autogenerate: { directory: 'apm' },
				},
				{
					label: 'Dashboards & Visualize',
					collapsed: true,
					items: [
						{ label: 'Overview', link: '/dashboards/' },
						{ label: 'Build a Dashboard', link: '/dashboards/build/' },
						{ label: 'Sharing Dashboards', link: '/dashboards/sharing/' },
						{ label: 'Troubleshooting Dashboards', link: '/dashboards/troubleshooting/' },
						{
							label: 'Dashboard Variables',
							collapsed: true,
							items: [
								{ label: 'Overview', link: '/dashboards/variables/' },
								{ label: 'Managing Variables', link: '/dashboards/variables/managing-variables/' },
								{ label: 'Using Variables', link: '/dashboards/variables/using-variables/' },
							],
						},
						{
							label: 'Visualize',
							collapsed: true,
							items: [
								{ label: 'Visualization Editor', link: '/dashboards/visualize/' },
								{ label: 'Visualization Transformations', link: '/dashboards/visualize/transformations/' },
								{
									label: 'Chart Types',
									collapsed: true,
									items: [
										{ label: 'Area Chart', link: '/dashboards/visualize/area-chart/' },
										{ label: 'Bar Chart', link: '/dashboards/visualize/bar-chart/' },
										{ label: 'Bar Gauge Chart', link: '/dashboards/visualize/bar-gauge-chart/' },
										{ label: 'Gauge Chart', link: '/dashboards/visualize/gauge-chart/' },
										{ label: 'Heatmap', link: '/dashboards/visualize/heatmap-chart/' },
										{ label: 'Histogram', link: '/dashboards/visualize/histogram-chart/' },
										{ label: 'Line Chart', link: '/dashboards/visualize/line-chart/' },
										{ label: 'Metric Chart', link: '/dashboards/visualize/metric-chart/' },
										{ label: 'Pie Chart', link: '/dashboards/visualize/pie-chart/' },
										{ label: 'Scatter Plot', link: '/dashboards/visualize/scatter-chart/' },
										{ label: 'State Timeline', link: '/dashboards/visualize/state-timeline-chart/' },
										{ label: 'Table', link: '/dashboards/visualize/table-chart/' },
									],
								},
								{
									label: 'Configuration',
									collapsed: true,
									items: [
										{ label: 'Configure Visualizations', link: '/dashboards/visualize/configuring-visualizations/' },
										{ label: 'Thresholds', link: '/dashboards/visualize/configuring-visualizations/thresholds/' },
										{ label: 'Value Calculations', link: '/dashboards/visualize/configuring-visualizations/value-calculations/' },
									],
								},
							],
						},
					],
				},
				{
					label: 'Alerting',
					collapsed: true,
					items: [
						{ label: 'Alerting', link: '/alerting/' },
						{ label: 'Anomaly Detection', link: '/anomaly-detection/' },
						{ label: 'Forecasting', link: '/forecasting/' },
					],
				},
				{
					label: 'Agent Health',
					collapsed: true,
					autogenerate: { directory: 'agent-health' },
				},
				{
					label: 'SDKs, MCP & Clients',
					collapsed: true,
					items: [
						{ label: 'Python SDK', link: '/send-data/ai-agents/python/' },
						{ label: 'TypeScript SDK', link: '/send-data/ai-agents/typescript/' },
						{ label: 'MCP Server', link: '/mcp/' },
					],
				},
				{
					label: 'Claude Code',
					collapsed: true,
					autogenerate: { directory: 'claude-code' },
				},
			],
		}),
	],
});
