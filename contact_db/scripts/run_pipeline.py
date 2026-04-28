
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="微信建联话术库构建 Pipeline MVP"
    )
    parser.add_argument(
        "--input-dir",
        "-i",
        type=str,
        default=".",
        help="输入目录（默认当前目录）",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="./outputs",
        help="输出目录（默认 ./outputs）",
    )
    parser.add_argument(
        "--prefix",
        "-p",
        type=str,
        default="demo",
        help="输出文件名前缀（默认 demo）",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from src.pipeline import TalkLibraryPipeline
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保在项目根目录下运行，或者 src/ 目录在 PYTHONPATH 中")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=" * 60)
    print("微信建联话术库构建 Pipeline MVP")
    print("=" * 60)
    print(f"输入目录: {args.input_dir}")
    print(f"输出目录: {args.output_dir}")
    print(f"文件名前缀: {args.prefix}")
    print()

    pipeline = TalkLibraryPipeline(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        prefix=args.prefix,
    )

    try:
        pipeline.run()
    except Exception as e:
        print(f"Pipeline 运行错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)
    print("Pipeline 运行完成!")
    print("=" * 60)
    print(f"处理文件数: {len(pipeline.input_files)}")
    print(f"会话数: {len(pipeline.conversations)}")
    print(f"对话回合数: {len(pipeline.turns)}")
    print(f"总样本数: {len(pipeline.all_samples)}")
    print(f"  - Trainable: {len(pipeline.train_samples)}")
    print(f"  - Needs review: {len(pipeline.review_samples)}")
    print(f"  - Excluded: {len(pipeline.excluded_samples)}")
    print(f"模板候选数: {len(pipeline.templates)}")
    print()
    print("输出文件:")
    output_files = list(Path(args.output_dir).glob(f"{args.prefix}_*"))
    for f in sorted(output_files):
        print(f"  - {f.name}")
    print()


if __name__ == "__main__":
    main()

