import { useState } from "react";

import { analyzeXingtuCpmFilesWithMode, evaluateXingtuCpm, fetchXingtuCpmSample } from "../lib/api";
import type { XingtuExtractionMode } from "../lib/api";
import type { PoolEstimate, XingtuCpmAssessment, XingtuCpmInput, XingtuCpmParseResult } from "../lib/types";

function formatNumber(value?: number | null) {
  if (value === null || value === undefined) {
    return "-";
  }
  return Math.round(value).toLocaleString();
}

function formatCpm(value?: number | null) {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toFixed(2);
}

function parseNumber(value: string) {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value.replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function poolText(pool?: PoolEstimate | null) {
  if (!pool?.center) {
    return "未识别";
  }
  return `${formatNumber(pool.low)} - ${formatNumber(pool.high)}，中心 ${formatNumber(pool.center)}`;
}

function poolMetaText(pool?: PoolEstimate | null) {
  if (!pool?.center) {
    return "";
  }
  const source = pool.source === "quantile_fallback" ? "估算次级池" : pool.source === "observed_cluster" ? "稳定簇" : pool.source;
  const weighted = pool.age_weighted ? "，已做时间衰减" : "";
  const outliers = pool.outlier_count ? `，排除爆款 ${pool.outlier_count} 个` : "";
  return `${source}，置信度 ${Math.round(pool.confidence)}，样本 ${pool.sample_count}${weighted}${outliers}`;
}

const emptyInput: XingtuCpmInput = {
  natural_plays: [],
  sponsored_plays: [],
  personal_chart_points: [],
  star_chart_points: [],
  cooperate_brands: [],
};

export function XingtuCpmPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<XingtuCpmParseResult | null>(null);
  const [form, setForm] = useState<XingtuCpmInput>(emptyInput);
  const [fieldSources, setFieldSources] = useState<Record<string, string>>({});
  const [extractionMode] = useState<XingtuExtractionMode>("vlm_only");
  const [assessment, setAssessment] = useState<XingtuCpmAssessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function applyResponse(response: { parse_result: XingtuCpmParseResult; assessment: XingtuCpmAssessment }) {
    setParseResult(response.parse_result);
    setForm(response.parse_result.parsed_input);
    setFieldSources(response.parse_result.field_sources ?? {});
    setAssessment(response.assessment);
  }

  async function handleSample() {
    setBusy(true);
    setStatus("正在载入样例...");
    setError(null);
    try {
      applyResponse(await fetchXingtuCpmSample());
      setStatus("样例已载入。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "载入样例失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    if (files.length === 0) {
      setError("请先选择至少一张截图。");
      return;
    }
    setBusy(true);
    setStatus(`正在上传并用 VLM 解析 ${files.length} 张截图，可能需要几十秒，请稍等...`);
    setError(null);
    try {
      applyResponse(await analyzeXingtuCpmFilesWithMode(files, extractionMode));
      setStatus("解析完成，可以校正字段或重新计算。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "VLM 解析失败");
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }

  function addSelectedFiles(selectedFiles: FileList | null) {
    if (!selectedFiles) {
      return;
    }
    setFiles((current) => {
      const next = [...current];
      for (const file of Array.from(selectedFiles)) {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (!next.some((item) => `${item.name}:${item.size}:${item.lastModified}` === key)) {
          next.push(file);
        }
      }
      if (next.length > current.length) {
        setStatus(`已选择 ${next.length} 张截图。点击“上传并解析”开始处理。`);
        setError(null);
      }
      return next;
    });
  }

  async function handleEvaluate() {
    setBusy(true);
    setStatus("正在按校正后的字段重新计算...");
    setError(null);
    try {
      setAssessment(await evaluateXingtuCpm(form));
      setStatus("重新计算完成。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "重新计算失败");
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }

  function updateNumberField(field: keyof XingtuCpmInput, value: string) {
    setForm((current) => ({
      ...current,
      [field]: parseNumber(value),
      ...(field === "post_count_30d" ? { post_count_30d_source: "manual" as const } : {}),
    }));
    setFieldSources((current) => ({ ...current, [field]: "manual" }));
  }

  function updateNaturalPlays(value: string) {
    const plays = value
      .split(/[,\n\s]+/)
      .map((item) => parseNumber(item))
      .filter((item): item is number => item !== null)
      .map((item) => Math.round(item));
    setForm((current) => ({ ...current, natural_plays: plays }));
    setFieldSources((current) => ({ ...current, natural_plays: "manual" }));
  }

  function updateSponsoredPlays(value: string) {
    const plays = value
      .split(/[,\n\s]+/)
      .map((item) => parseNumber(item))
      .filter((item): item is number => item !== null)
      .map((item) => Math.round(item));
    setForm((current) => ({ ...current, sponsored_plays: plays }));
    setFieldSources((current) => ({ ...current, sponsored_plays: "manual" }));
  }

  function updateTextField(field: keyof XingtuCpmInput, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldSources((current) => ({ ...current, [field]: "manual" }));
  }

  function sourceText(field: keyof XingtuCpmInput) {
    return fieldSources[field] ?? "-";
  }

  return (
    <main className="xingtu-page">
      <section className="xingtu-header">
        <div>
          <p>星图截图 VLM 商单评估</p>
          <h1>上传截图，校正字段，得到可复核的 CPM 结果</h1>
        </div>
        <button type="button" onClick={handleSample} disabled={busy}>
          载入样例
        </button>
      </section>

      {error ? <div className="xingtu-error">{error}</div> : null}
      {status ? <div className="xingtu-status">{status}</div> : null}

      <section className="xingtu-grid">
        <div className="xingtu-panel">
          <h2>截图</h2>
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => {
              addSelectedFiles(event.target.files);
              event.currentTarget.value = "";
            }}
          />
          <p className="xingtu-muted">提取模式：VLM 提取。样例模式使用 fixture，不代表真实上传结果。</p>
          <p className="xingtu-muted">一次选择 4 张，或分批追加：报价/概览、传播价值、近15个人视频图、近15星图视频图。全部 tab 图已废弃。</p>
          <div className="xingtu-file-list">
            <strong>已选择 {files.length} 张</strong>
            {files.length > 0 ? (
              <>
                <button type="button" className="xingtu-secondary-button" onClick={() => setFiles([])} disabled={busy}>
                  清空
                </button>
                <ul>
                  {files.map((file) => (
                    <li key={`${file.name}-${file.size}-${file.lastModified}`}>{file.name}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
          <button type="button" disabled={busy || files.length === 0} onClick={handleAnalyze}>
            {busy ? "处理中..." : "上传并解析"}
          </button>

          {parseResult ? (
            <div className="xingtu-stack">
              <h3>提取信息</h3>
              <p>提取模式：{parseResult.extraction_engine_used ?? "-"}</p>
              <p>VLM：{parseResult.vlm_model_used ?? "-"}</p>
              <p>自然播放量：{parseResult.parsed_input.natural_plays.length} 个</p>
              <p>星图播放量：{parseResult.parsed_input.sponsored_plays.length} 个</p>
              <p>
                报价字段：
                20s {parseResult.parsed_input.price_20s == null ? "缺失" : "已识别"} / 20-60s{" "}
                {parseResult.parsed_input.price_20_60s == null ? "缺失" : "已识别"} / 60s+{" "}
                {parseResult.parsed_input.price_60s_plus == null ? "缺失" : "已识别"}
              </p>
              {parseResult.parsed_input.natural_plays.length === 0 && parseResult.parsed_input.sponsored_plays.length === 0 ? (
                <div className="xingtu-error">VLM 有响应但未提取到有效播放量字段，请查看 warnings 和 raw preview。</div>
              ) : null}
              {parseResult.warnings.length > 0 ? (
                <>
                  <h3>Warnings</h3>
                  <ul>
                    {parseResult.warnings.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              ) : null}
              {parseResult.vlm_raw_response_preview ? (
                <details>
                  <summary>VLM raw preview</summary>
                  <pre className="xingtu-raw-preview">{parseResult.vlm_raw_response_preview}</pre>
                </details>
              ) : null}
              <h3>截图类型</h3>
              <p>已识别：{parseResult.detected_screenshot_types.join(", ") || "-"}</p>
              <p>缺失：{parseResult.missing_required_screenshot_types.join(", ") || "无"}</p>
              <h3>字段来源</h3>
              {Object.entries(parseResult.extracted_fields_by_screenshot_type).map(([type, fields]) => (
                <details key={type}>
                  <summary>{type}</summary>
                  <ul>
                    {fields.map((field, index) => (
                      <li key={`${field.field_name}-${index}`}>
                        {field.field_name}: {String(field.normalized_value ?? field.raw_value ?? "-")}（{field.source}）
                      </li>
                    ))}
                  </ul>
                </details>
              ))}
            </div>
          ) : null}
        </div>

        <div className="xingtu-panel">
          <h2>VLM 字段校正</h2>
          <label>
            达人名称
            <span className="xingtu-source">来源：{sourceText("creator_name")}</span>
            <input value={form.creator_name ?? ""} onChange={(event) => updateTextField("creator_name", event.target.value)} />
          </label>
          <label>
            近15条自然播放量
            <span className="xingtu-source">来源：{sourceText("natural_plays")}</span>
            <textarea value={form.natural_plays.join("\n")} onChange={(event) => updateNaturalPlays(event.target.value)} />
          </label>
          <label>
            近15条星图视频播放量
            <span className="xingtu-source">来源：{sourceText("sponsored_plays")}</span>
            <textarea value={form.sponsored_plays.join("\n")} onChange={(event) => updateSponsoredPlays(event.target.value)} />
          </label>
          <div className="xingtu-fields">
            <label>
              近30天发文数
              <span className="xingtu-source">来源：{sourceText("post_count_30d")}</span>
              <input value={form.post_count_30d ?? ""} onChange={(event) => updateNumberField("post_count_30d", event.target.value)} />
              <span className="xingtu-muted">当前口径：{form.post_count_30d_source ?? "-"}</span>
            </label>
            <label>
              星图序列派生分桶众数
              <span className="xingtu-source">来源：{sourceText("ad_bucketed_mode_play")}</span>
              <input value={form.ad_bucketed_mode_play ?? ""} onChange={(event) => updateNumberField("ad_bucketed_mode_play", event.target.value)} />
            </label>
            <label>
              星图序列派生中位数
              <span className="xingtu-source">来源：{sourceText("ad_median_play")}</span>
              <input value={form.ad_median_play ?? ""} onChange={(event) => updateNumberField("ad_median_play", event.target.value)} />
            </label>
            <label>
              20s 报价
              <span className="xingtu-source">来源：{sourceText("price_20s")}</span>
              <input value={form.price_20s ?? ""} onChange={(event) => updateNumberField("price_20s", event.target.value)} />
            </label>
            <label>
              20-60s 报价
              <span className="xingtu-source">来源：{sourceText("price_20_60s")}</span>
              <input value={form.price_20_60s ?? ""} onChange={(event) => updateNumberField("price_20_60s", event.target.value)} />
            </label>
            <label>
              60s+ 报价
              <span className="xingtu-source">来源：{sourceText("price_60s_plus")}</span>
              <input value={form.price_60s_plus ?? ""} onChange={(event) => updateNumberField("price_60s_plus", event.target.value)} />
            </label>
            <label>
              平台预期 CPM
              <span className="xingtu-source">来源：{sourceText("platform_expected_cpm")}</span>
              <input value={form.platform_expected_cpm ?? ""} onChange={(event) => updateNumberField("platform_expected_cpm", event.target.value)} />
            </label>
            <label>
              平台预期播放
              <span className="xingtu-source">来源：{sourceText("platform_expected_play")}</span>
              <input value={form.platform_expected_play ?? ""} onChange={(event) => updateNumberField("platform_expected_play", event.target.value)} />
            </label>
            <label>
              个人图均值
              <span className="xingtu-source">来源：{sourceText("personal_chart_avg_play")}</span>
              <input value={form.personal_chart_avg_play ?? ""} onChange={(event) => updateNumberField("personal_chart_avg_play", event.target.value)} />
            </label>
            <label>
              星图图均值
              <span className="xingtu-source">来源：{sourceText("star_chart_avg_play")}</span>
              <input value={form.star_chart_avg_play ?? ""} onChange={(event) => updateNumberField("star_chart_avg_play", event.target.value)} />
            </label>
          </div>
          <button type="button" disabled={busy} onClick={handleEvaluate}>
            重新计算
          </button>
        </div>

        <div className="xingtu-panel">
          <h2>评估结果</h2>
          {assessment ? (
            <>
              <div className="xingtu-result-grid">
                <span>自然初级流量池</span>
                <strong>
                  {poolText(assessment.primary_pool)}
                  {poolMetaText(assessment.primary_pool) ? <small>{poolMetaText(assessment.primary_pool)}</small> : null}
                </strong>
                <span>自然次级流量池</span>
                <strong>
                  {poolText(assessment.secondary_pool)}
                  {poolMetaText(assessment.secondary_pool) ? <small>{poolMetaText(assessment.secondary_pool)}</small> : null}
                </strong>
                <span>星图商单流量池</span>
                <strong>
                  {poolText(assessment.commercial_primary_pool)}
                  {poolMetaText(assessment.commercial_primary_pool) ? <small>{poolMetaText(assessment.commercial_primary_pool)}</small> : null}
                </strong>
                <span>星图商单次级池</span>
                <strong>
                  {poolText(assessment.commercial_secondary_pool)}
                  {poolMetaText(assessment.commercial_secondary_pool) ? <small>{poolMetaText(assessment.commercial_secondary_pool)}</small> : null}
                </strong>
                <span>商单 CPM 播放量基准</span>
                <strong>{formatNumber(assessment.commercial_cpm_play_basis ?? assessment.commercial_pool_center_for_cpm)}</strong>
                <span>自然 CPM 播放量基准</span>
                <strong>{formatNumber(assessment.natural_cpm_play_basis ?? assessment.natural_pool_center_for_cpm)}</strong>
                <span>商单能力等级</span>
                <strong>{assessment.commercial_level}</strong>
                <span>预估商单播放量</span>
                <strong>{formatNumber(assessment.predicted_ad_play)}</strong>
                <span>加权预估播放量</span>
                <strong>{formatNumber(assessment.weighted_predicted_ad_play)}</strong>
                <span>置信度</span>
                <strong>{assessment.confidence_score}</strong>
                <span>人工复核</span>
                <strong>{assessment.review_flag ? "建议复核" : "暂不需要"}</strong>
              </div>

              <h3>预测辅助指标</h3>
              <div className="xingtu-result-grid">
                <span>商单制作能力</span>
                <strong>{assessment.commercial_ability ? `${assessment.commercial_ability.ability_level} / 系数 ${assessment.commercial_ability.coefficient}` : "-"}</strong>
                <span>能力说明</span>
                <strong>{assessment.commercial_ability?.explanation || "-"}</strong>
                <span>自然流量趋势</span>
                <strong>{assessment.natural_trend_metrics ? `${assessment.natural_trend_metrics.trend_direction} / 系数 ${assessment.natural_trend_metrics.trend_coefficient.toFixed(2)}` : "-"}</strong>
                <span>自然趋势中位数</span>
                <strong>
                  {assessment.natural_trend_metrics
                    ? `${formatNumber(assessment.natural_trend_metrics.first_half_median)} -> ${formatNumber(assessment.natural_trend_metrics.second_half_median)}`
                    : "-"}
                </strong>
                <span>星图流量趋势</span>
                <strong>{assessment.commercial_trend_metrics ? `${assessment.commercial_trend_metrics.trend_direction} / 系数 ${assessment.commercial_trend_metrics.trend_coefficient.toFixed(2)}` : "-"}</strong>
                <span>全部流量趋势</span>
                <strong>{assessment.overall_trend_metrics ? `${assessment.overall_trend_metrics.trend_direction} / 系数 ${assessment.overall_trend_metrics.trend_coefficient.toFixed(2)}` : "-"}</strong>
                <span>互动修正系数</span>
                <strong>暂未启用</strong>
                <span>基础预测</span>
                <strong>{formatNumber(assessment.base_predicted_play)}</strong>
                <span>加权因子</span>
                <strong>{Object.entries(assessment.final_prediction_factors ?? {}).map(([key, value]) => `${key}:${value}`).join(" / ") || "-"}</strong>
                <span>时间衰减</span>
                <strong>
                  {assessment.primary_pool.age_weighted || assessment.commercial_primary_pool?.age_weighted
                    ? "已按图表日期加权，近期视频影响更高"
                    : "未启用，缺少可用日期"}
                </strong>
              </div>

              <h3>CPM</h3>
              <table>
                <thead>
                  <tr>
                    <th>档位</th>
                    <th>报价</th>
                    <th>商单 CPM</th>
                    <th>自然 CPM</th>
                    <th>播放量基准来源</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(assessment.cpm_by_tier).map(([tier, value]) => (
                    <tr key={tier}>
                      <td>{tier}</td>
                      <td>{formatNumber(value.price)}</td>
                      <td>{formatCpm(value.predicted_cpm)}</td>
                      <td>{formatCpm(value.natural_cpm)}</td>
                      <td>{value.commercial_cpm_play_basis_source ?? "-"} / {value.natural_cpm_play_basis_source ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h3>解释</h3>
              <ul>
                {assessment.explanations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
                {assessment.review_reasons.map((item) => (
                  <li key={item}>复核：{item}</li>
                ))}
              </ul>
              <p className="xingtu-muted">
                平台参考：预期 CPM {formatCpm(assessment.reference.platform_expected_cpm)}，预期播放{" "}
                {formatNumber(assessment.reference.platform_expected_play)}
              </p>
            </>
          ) : (
            <p className="xingtu-muted">先载入样例或上传截图。</p>
          )}
        </div>
      </section>
    </main>
  );
}
