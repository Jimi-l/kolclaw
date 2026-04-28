MVP fixture set for Xingtu CPM VLM screenshot parsing.

The regression tests now build deterministic VLM payload fixtures in code. If
you want to run the optional real-image smoke test, keep the source PNGs under
`data/xingtu_cpm/real_images/` in folders such as `eg_1/`, `eg_2/`,
and `eg_3/`. For deterministic fixture authoring, use these filenames:

- `overview_pricing.png`
- `value_personal_video.png`
- `latest15_personal_chart.png`
- `latest15_star_chart.png`

The expected parse and assessment summaries document the same business case for
rules and API regression.
