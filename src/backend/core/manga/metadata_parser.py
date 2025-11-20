# core/manga/metadata_parser.py
"""
定义了元数据解析器，负责从漫画文件名中提取标签和标题。
"""
import re
from typing import Tuple, Set

class MetadataParser:
    """一个独立的、无状态的元数据解析器"""

    @staticmethod
    def parse(file_basename: str) -> Tuple[str, Set[str]]:
        """
        从漫画文件名中解析出干净的标题和标签集合。

        Args:
            file_basename (str): 漫画的文件名 (不含扩展名)。

        Returns:
            Tuple[str, Set[str]]: (解析后的干净标题, 标签集合)
        """
        tags = set()
        original_title = file_basename

        # 解析杂志/平台信息 (Fantia) 等
        platform_match = re.match(r"[\(（](.*?)[\)）](.*)", original_title)
        if platform_match:
            platform = platform_match.group(1)
            if not re.search(r"\d", platform):
                tags.add(f"平台:{platform}")
                original_title = platform_match.group(2).strip()

        # 解析作者和团队 [团队 (作者)]
        group_author_match = re.search(r"\[(.*?) \((.*?)\)\]", original_title)
        if group_author_match:
            tags.add(f"组:{group_author_match.group(1)}")
            tags.add(f"作者:{group_author_match.group(2)}")
            original_title = original_title.replace(
                group_author_match.group(0), "", 1
            ).strip()
        else:
            # 解析单独的作者 [作者]
            author_match = re.search(r"\[(.*?)\]", original_title)
            if author_match and "汉化" not in author_match.group(1):
                tags.add(f"作者:{author_match.group(1)}")
                original_title = original_title.replace(
                    author_match.group(0), "", 1
                ).strip()

        # 解析会场信息 (C97) 等
        event_match = re.match(r"\(([Cc][0-9]+)\)(.*)", original_title)
        if event_match:
            tags.add(f"会场:{event_match.group(1)}")
            original_title = event_match.group(2).strip()

        # 解析作品名 (作品名)
        series_match = re.search(r"[\(（]([^()（）\d]*?)[\)）](?![^[]*\])", original_title)
        if series_match and series_match.group(1).strip():
            tags.add(f"作品:{series_match.group(1)}")
            original_title = original_title[
                : original_title.rfind(series_match.group(0))
            ].strip()

        # 处理其他方括号标签
        while True:
            bracket_match = re.search(r"\[(.*?)\]", original_title)
            if not bracket_match:
                break
            tag_content = bracket_match.group(1)
            if any(
                keyword in tag_content
                for keyword in ["中国翻訳", "中国翻译", "中國翻譯", "中國翻訳"]
            ):
                tags.add("汉化:中国翻译")
            elif any(
                keyword in tag_content
                for keyword in ["汉化", "漢化", "翻訳", "翻译", "翻譯"]
            ):
                tags.add(f"汉化:{tag_content}")
            elif any(
                keyword in tag_content for keyword in ["無修正", "无修正", "無修"]
            ):
                tags.add("其他:无修正")
            else:
                tags.add(f"其他:{tag_content}")
            original_title = original_title.replace(f"[{tag_content}]", "", 1).strip()

        clean_title = original_title.strip()
        if clean_title:
            tags.add(f"标题:{clean_title}")

        return clean_title, tags