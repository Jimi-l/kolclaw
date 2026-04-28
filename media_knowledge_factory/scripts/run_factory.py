#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 AI 媒介知识与标签工厂 V1")
    parser.add_argument(
        "--input-dir",
        "-i",
        type=str,
        default="/home/tuo/project/contact_db/outputs/file_transfer_assistant_cleaned/reconstructed_weflow",
        help="输入 WeFlow JSON 目录",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="/home/tuo/project/media_knowledge_factory/outputs/seed_v1",
        help="输出目录",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    from src.pipeline import MediaKnowledgeFactoryPipeline

    pipeline = MediaKnowledgeFactoryPipeline(args.input_dir, args.output_dir)
    pipeline.run()

    print("=" * 60)
    print("Media Knowledge Factory V1 completed")
    print("=" * 60)
    print(f"input_dir: {args.input_dir}")
    print(f"output_dir: {args.output_dir}")
    print(f"messages: {len(pipeline.messages)}")
    print(f"brief_cards: {len(pipeline.brief_cards)}")
    print(f"episodes: {len(pipeline.episodes)}")
    print(f"talk_templates: {len(pipeline.talk_templates)}")
    print(f"workflow_playbook: {len(pipeline.playbook_steps)}")
    print(f"retrieval_chunks: {len(pipeline.retrieval_chunks)}")


if __name__ == "__main__":
    main()
