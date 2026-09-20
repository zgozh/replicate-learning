# -*- coding: utf-8 -*-
"""Assemble a lecture from a fixed skeleton and independently drafted sections.

Only complete ``##`` sections can be replaced. This prevents a local repair from
accidentally deleting another section or a source-code fence. The content gate
still has to run on the assembled lecture.
"""

import argparse
import os
import re
import tempfile
from pathlib import Path


HEADING = re.compile(r"^## (.+?)\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


def split_sections(document, *, allow_preamble):
    lines = document.splitlines(keepends=True)
    positions = []
    opened = None
    for index, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        fence = FENCE.match(stripped)
        if fence:
            marker = fence.group(1)
            if opened is None:
                opened = (marker[0], len(marker))
            elif marker[0] == opened[0] and len(marker) >= opened[1] and not fence.group(2).strip():
                opened = None
            continue
        if opened is None and HEADING.match(stripped):
            positions.append(index)
    if opened is not None:
        raise ValueError("未闭合的 Markdown 代码围栏")
    if not positions:
        raise ValueError("没有 ## 章节")
    preamble = "".join(lines[:positions[0]])
    if not allow_preamble and preamble.strip():
        raise ValueError("章节片段只能包含完整的 ## 章节")
    sections = {}
    for position, end in zip(positions, positions[1:] + [len(lines)]):
        heading = lines[position].rstrip("\r\n")
        if heading in sections:
            raise ValueError("重复章节：" + heading)
        sections[heading] = "".join(lines[position:end])
    return preamble, sections


def assemble(base, parts, *, expected_sections=17):
    preamble, sections = split_sections(base, allow_preamble=True)
    if len(sections) != expected_sections:
        raise ValueError("骨架章节数 %d，预期 %d" % (len(sections), expected_sections))
    replacements = {}
    for part in parts:
        _, parsed = split_sections(part, allow_preamble=False)
        for heading, body in parsed.items():
            if heading not in sections:
                raise ValueError("片段章节未在骨架中：" + heading)
            if heading in replacements:
                raise ValueError("章节重复提交：" + heading)
            replacements[heading] = body
    output = preamble + "".join(replacements.get(h, body) for h, body in sections.items())
    _, final_sections = split_sections(output, allow_preamble=True)
    if len(final_sections) != expected_sections:
        raise ValueError("组装后章节数发生变化")
    return output


def write_batch(path, content, *, force=False):
    path = Path(path)
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        if not force:
            raise FileExistsError("目标已有不同内容；确认后加 --force：" + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=path.name + ".", suffix=".tmpnew", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="从 17 节骨架与章节片段组装讲解")
    parser.add_argument("--base", type=Path, required=True, help="new_batch.py 生成的骨架")
    parser.add_argument("--part", type=Path, action="append", required=True, help="一个或多个完整的 ## 章节")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="覆盖已有且内容不同的目标")
    args = parser.parse_args()
    base = args.base.read_text(encoding="utf-8")
    parts = [path.read_text(encoding="utf-8") for path in args.part]
    result = assemble(base, parts)
    write_batch(args.out, result, force=args.force)
    print("组装完成：%s；下一步运行 gate_lecture.py" % args.out)


if __name__ == "__main__":
    main()
