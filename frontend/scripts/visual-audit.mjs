import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.ORA_VISUAL_URL || 'http://127.0.0.1:3001/';
const phase = process.env.ORA_VISUAL_PHASE || 'before';
const outDir = path.resolve(process.cwd(), 'visual-audit', phase);
const desktop = { width: 1440, height: 960 };

const user = {
  id: 'u_demo',
  email: 'sathish@example.com',
  name: 'Sathish Kumar',
  is_onboarded: true,
  email_verified: true,
  purpose: 'startup',
};

const personalWorkspace = {
  id: 'ws_personal',
  name: 'Personal',
  context: 'personal',
  type: 'study',
  persona: 'general',
  members: [],
  customRoles: [],
};

const companyWorkspace = {
  id: 'ws_company',
  name: 'Teams Lab',
  context: 'company',
  type: 'project',
  persona: 'general',
  organizationId: 'org_teams',
  members: [],
  customRoles: [],
};

const companies = [
  {
    id: 'c_acme',
    workspaceId: 'ws_personal',
    name: 'Acme MVP',
    mission: 'Launch a usable MVP by Sep 30.',
    color: '#2367E8',
    projects: [
      {
        id: 'p_acme',
        workspaceId: 'ws_personal',
        companyId: 'c_acme',
        name: 'Acme MVP',
        type: 'build',
        mission: 'Launch usable MVP by Sep 30 with credible pricing evidence.',
        progress: 42,
        tasks: [
          { id: 't_1', workspaceId: 'ws_personal', projectId: 'p_acme', title: 'Finalize onboarding flow', status: 'in-progress', priority: 'high', estimatedHours: 1.5, dueDate: '2026-08-18T00:00:00.000Z' },
          { id: 't_2', workspaceId: 'ws_personal', projectId: 'p_acme', title: 'Interview three pricing leads', status: 'todo', priority: 'critical', estimatedHours: 2, dueDate: '2026-08-16T00:00:00.000Z' },
          { id: 't_3', workspaceId: 'ws_personal', projectId: 'p_acme', title: 'Draft demo script', status: 'review', priority: 'medium', estimatedHours: 1 },
          { id: 't_4', workspaceId: 'ws_personal', projectId: 'p_acme', title: 'Publish private beta checklist', status: 'todo', priority: 'medium', estimatedHours: 1 },
        ],
      },
    ],
  },
  {
    id: 'c_learning',
    workspaceId: 'ws_personal',
    name: 'Computer Networks',
    mission: 'Master routing, transport, and congestion control.',
    color: '#16865C',
    projects: [
      {
        id: 'p_networks',
        workspaceId: 'ws_personal',
        companyId: 'c_learning',
        name: 'Transport Layer Review',
        type: 'learning',
        mission: 'Close weak TCP and congestion-control concepts before the mock exam.',
        progress: 58,
        tasks: [
          { id: 't_5', workspaceId: 'ws_personal', projectId: 'p_networks', title: 'Review TCP slow start examples', status: 'todo', priority: 'high', estimatedHours: 1 },
        ],
      },
    ],
  },
];

const teamMembers = [
  { id: 'u_demo', userId: 'u_demo', name: 'Sathish Kumar', email: 'sathish@example.com', role: 'owner', joinedAt: '2026-08-01T00:00:00.000Z' },
  { id: 'u_maya', userId: 'u_maya', name: 'Maya Rao', email: 'maya@example.com', role: 'admin', joinedAt: '2026-08-02T00:00:00.000Z' },
  { id: 'u_arun', userId: 'u_arun', name: 'Arun Mehta', email: 'arun@example.com', role: 'contributor', joinedAt: '2026-08-03T00:00:00.000Z' },
];

const home = {
  workspace: { id: 'ws_personal' },
  today: {
    generated_at: '2026-08-14T09:00:00.000Z',
    availability: { minutes: 210, source: 'calendar' },
    now: {
      task_id: 't_1',
      title: 'Finalize onboarding flow',
      project_id: 'p_acme',
      project_name: 'Acme MVP',
      eligibility: 'READY',
      blocked_by: [],
      priority: 'high',
      estimated_effort_minutes: 90,
      schedule_fit: 'fits',
      score: 0.94,
      scheduled_start: '2026-08-14T10:00:00.000Z',
      scheduled_end: '2026-08-14T11:30:00.000Z',
      reasons: ['Highest leverage before beta invites', 'Fits the open focus block', 'Unblocks demo evidence'],
    },
    next: [
      {
        task_id: 't_2',
        title: 'Interview three pricing leads',
        project_id: 'p_acme',
        project_name: 'Acme MVP',
        eligibility: 'READY',
        blocked_by: [],
        priority: 'critical',
        estimated_effort_minutes: 120,
        schedule_fit: 'tight',
        score: 0.86,
        reasons: ['Pricing validation is behind plan'],
      },
    ],
    later_count: 3,
    excluded_count: 0,
    missed_sessions: [{ id: 'e_missed', task_id: 't_3', title: 'Draft demo script' }],
    explanation: [],
  },
  calendar: { event_count: 5, busy_minutes: 260, events: [] },
  active_projects: [
    { id: 'p_acme', name: 'Acme MVP', type: 'build', progress: 42, task_count: 4, done_count: 1 },
    { id: 'p_networks', name: 'Transport Layer Review', type: 'learning', progress: 58, task_count: 1, done_count: 0 },
  ],
  pending_plan: { title: 'Beta launch plan', qualityStatus: 'needs_review', summary: { phaseCount: 3, taskCount: 11 } },
  pending_schedule: { status: 'draft', sessions: [{ id: 's1' }], summary: { title: 'This week', sessionCount: 4 } },
  plan_health: { status: 'AT_RISK', reasons: ['Pricing evidence is weaker than expected.'] },
  pending_revision: { id: 'rev_1', base_plan_id: 'plan_1', trigger: 'Pricing validation is behind.', hard_constraints: [], operations: [{ op: 'move', target: 'Pricing interviews' }], status: 'pending' },
  alerts: [{ type: 'warning', message: 'Pricing validation needs evidence.' }],
};

const calendarEvents = [
  { id: 'e_1', workspaceId: 'ws_personal', title: 'Focus: Finalize onboarding flow', start: '2026-08-14T10:00:00.000Z', end: '2026-08-14T11:30:00.000Z', type: 'task_block', scope: 'personal', taskId: 't_1', color: 'accent', isFlexible: true, sessionStatus: 'SCHEDULED' },
  { id: 'e_2', workspaceId: 'ws_personal', title: 'Customer call', start: '2026-08-14T13:00:00.000Z', end: '2026-08-14T14:00:00.000Z', type: 'meeting', scope: 'personal', color: 'neutral', locked: true },
  { id: 'e_3', workspaceId: 'ws_personal', title: 'Focus: Draft demo script', start: '2026-08-13T16:00:00.000Z', end: '2026-08-13T17:00:00.000Z', type: 'task_block', scope: 'personal', taskId: 't_3', color: 'accent', isFlexible: true, sessionStatus: 'MISSED' },
  { id: 'e_4', workspaceId: 'ws_personal', title: 'Focus: Review TCP slow start examples', start: '2026-08-15T09:00:00.000Z', end: '2026-08-15T10:00:00.000Z', type: 'task_block', scope: 'personal', taskId: 't_5', color: 'accent', isFlexible: true, sessionStatus: 'COMPLETED' },
  { id: 'e_5', workspaceId: 'ws_personal', title: 'Pricing evidence deadline', start: '2026-08-16T09:00:00.000Z', end: '2026-08-16T09:30:00.000Z', type: 'reminder', scope: 'personal', color: 'warning' },
];

const fulfillJson = (route, data) => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(data),
});

async function mockApi(page) {
  await page.route('**/api/v1/**', route => fulfillJson(route, {}));
  await page.route('**/api/v1/auth/me', route => fulfillJson(route, user));
  await page.route('**/api/v1/users/u_demo/workspaces', route => fulfillJson(route, [personalWorkspace, companyWorkspace]));
  await page.route('**/api/v1/workspaces/ws_personal/full-state', route => fulfillJson(route, companies));
  await page.route('**/api/v1/workspaces/ws_company/full-state', route => fulfillJson(route, companies));
  await page.route('**/api/v1/workspaces/ws_personal/home**', route => fulfillJson(route, home));
  await page.route('**/api/v1/workspaces/ws_company/home**', route => fulfillJson(route, home));
  await page.route('**/api/v1/workspaces/*/members', route => fulfillJson(route, teamMembers));
  await page.route('**/api/v1/projects/*/members', route => fulfillJson(route, teamMembers.slice(0, 2)));
  await page.route('**/api/v1/workspaces/*/events**', route => fulfillJson(route, calendarEvents));
  await page.route('**/api/v1/workspaces/*/search**', route => fulfillJson(route, { results: [] }));
}

async function capture(page, name, viewport) {
  await page.setViewportSize(viewport);
  await page.waitForTimeout(450);
  await page.screenshot({ path: path.join(outDir, `${name}-${viewport.width}.png`), fullPage: true });
}

async function metrics(page) {
  return page.evaluate(() => {
    const buckets = { white: 0, canvas: 0, nav: 0, accent: 0, semantic: 0, other: 0 };
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const parse = (color) => {
      const nums = color.match(/\d+(\.\d+)?/g)?.map(Number) || [];
      return nums.length >= 3 ? nums.slice(0, 3).map(Math.round) : null;
    };
    const close = (rgb, target, tolerance = 3) => rgb.every((value, i) => Math.abs(value - target[i]) <= tolerance);
    const classify = (rgb) => {
      if (!rgb) return 'other';
      if (rgb.every(value => value >= 252)) return 'white';
      if ([[242, 244, 241], [233, 237, 232], [246, 247, 245], [240, 242, 239]].some(target => close(rgb, target))) return 'canvas';
      if ([[23, 32, 30], [32, 44, 40], [24, 32, 29], [15, 23, 42]].some(target => close(rgb, target))) return 'nav';
      if ([[35, 103, 232], [25, 87, 203], [234, 241, 255]].some(target => close(rgb, target, 8))) return 'accent';
      if ([[255, 243, 214], [231, 247, 239], [252, 232, 230], [234, 243, 255]].some(target => close(rgb, target, 8))) return 'semantic';
      return 'other';
    };
    const stepX = Math.max(12, Math.floor(vw / 80));
    const stepY = Math.max(12, Math.floor(vh / 50));
    for (let y = 0; y < vh; y += stepY) {
      for (let x = 0; x < vw; x += stepX) {
        let el = document.elementFromPoint(x, y);
        while (el) {
          const color = getComputedStyle(el).backgroundColor;
          if (color !== 'transparent' && color !== 'rgba(0, 0, 0, 0)') {
            buckets[classify(parse(color))] += 1;
            break;
          }
          el = el.parentElement;
        }
        if (!el) buckets.other += 1;
      }
    }
    const total = Object.values(buckets).reduce((a, b) => a + b, 0) || 1;
    return Object.fromEntries(Object.entries(buckets).map(([k, v]) => [k, Math.round((v / total) * 100)]));
  });
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await mockApi(page);

  const viewports = [
    desktop,
    { width: 1024, height: 820 },
    { width: 390, height: 844 },
  ];

  const records = {};

  const unauthContext = await browser.newContext();
  const unauthPage = await unauthContext.newPage();
  await unauthPage.goto(baseUrl);
  await unauthPage.waitForLoadState('networkidle');
  records.auth = await metrics(unauthPage);
  for (const viewport of viewports) await capture(unauthPage, 'auth', viewport);
  await unauthContext.close();

  await page.goto(baseUrl);
  await page.evaluate(() => {
    localStorage.setItem('ora_auth_token', 'visual-token');
    localStorage.setItem('ora_user_id', 'u_demo');
    localStorage.setItem('ora_active_workspace', 'ws_personal');
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  records.home = await metrics(page);
  for (const viewport of viewports) await capture(page, 'home', viewport);

  await page.setViewportSize(desktop);
  await page.getByRole('button', { name: /^Work$/ }).first().click();
  await page.waitForTimeout(500);
  records.work = await metrics(page);
  for (const viewport of viewports) await capture(page, 'work', viewport);

  await page.setViewportSize(desktop);
  await page.locator('aside').getByText('Acme MVP').first().click();
  await page.waitForTimeout(500);
  records.companyHome = await metrics(page);
  for (const viewport of viewports) await capture(page, 'company-home', viewport);

  await page.setViewportSize(desktop);
  await page.mouse.click(430, 452);
  await page.waitForTimeout(500);
  records.project = await metrics(page);
  for (const viewport of viewports) await capture(page, 'project', viewport);

  await page.setViewportSize(desktop);
  await page.getByRole('button', { name: /Calendar detail/ }).first().click();
  await page.waitForTimeout(700);
  records.calendar = await metrics(page);
  for (const viewport of viewports) await capture(page, 'calendar', viewport);

  await page.setViewportSize(desktop);
  await page.evaluate(() => localStorage.setItem('ora_active_workspace', 'ws_company'));
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /^Team$/ }).first().click();
  await page.waitForTimeout(700);
  records.team = await metrics(page);
  for (const viewport of viewports) await capture(page, 'team', viewport);

  await fs.writeFile(path.join(outDir, 'coverage.json'), JSON.stringify(records, null, 2));
  await browser.close();
  console.log(`Visual audit written to ${outDir}`);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
