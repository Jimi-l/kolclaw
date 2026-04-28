import { test, expect } from '@playwright/test';

test.use({
  storageState: 'playwright/.auth/xingtu.json'
});

test('test', async ({ page }) => {
  await page.goto('https://www.xingtu.cn/');
  await page.locator('div').filter({ hasText: /^保乐力加-因赛ID：1815512192324739$/ }).nth(1).click();
  await page.getByRole('link', { name: '找达人' }).click();
  await page.getByRole('button', { name: '美妆 ' }).first().click();
  await page.getByText('美妆测评种草').click();
  await page.getByRole('button', { name: '家居家装 ' }).click();
  await page.locator('#dropdown-menu-4017').getByText('全选').click();
  const page1Promise = page.waitForEvent('popup');
  await page.locator('#layout-content').getByText('路上曹同学').click();
  const page1 = await page1Promise;
  await page1.getByText('所选数据范围内视频播放量中位数（仅统计公开可见视频）播放量中位数-优于-%同类型达人').click();
  await page1.getByText('所选数据范围内视频播放量中位数（仅统计公开可见视频）播放量中位数-优于-%同类型达人').click();
  await page1.getByText('所选数据范围内视频播放量中位数（仅统计公开可见视频）播放量中位数6,344优于73.81%同类型达人').click();
  await page1.getByText('预期CPM8,480').click();
  await page1.getByText('所选数据范围内视频平均完播率（仅统计公开可见视频）完播率14.7%优于89.04%同类型达人').click();
  await page1.getByText('所选数据范围内视频平均互动率（仅统计公开可见视频）互动率2').click();
  await page1.getByText('77.4w', { exact: true }).click();
  await page1.getByText('39.6w').click();
  await page1.getByText('144.7w').click();
  await page1.getByText('6.31%').click();
  await page1.getByText('月涨粉率').click();
  await page1.getByText('粉丝数', { exact: true }).click();
  await page1.getByText('月深度用户数39.6w').click();
  await page1.getByText('月连接用户数77.4w').click();
  await page1.getByText('粉丝数144.7w').click();
  await page1.getByText('月涨粉率6.31%').click();
  await page1.getByText('所选数据范围内视频播放量中位数（仅统计公开可见视频）播放量中位数6,344优于73.81%同类型达人').click();
  await page1.getByText('预期CPM8,480').click();
  await page1.getByText('所选数据范围内视频平均完播率（仅统计公开可见视频）完播率14.7%优于89.04%同类型达人').click();
  await page1.getByText('所选数据范围内视频平均互动率（仅统计公开可见视频）互动率2').click();
});