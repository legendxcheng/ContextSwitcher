"""
搜索工具模块

提供窗口搜索相关的工具函数：
- 多关键词搜索匹配
- 搜索结果高亮显示
- 模糊匹配算法（首字母缩写、连续子序列、编辑距离）
- 搜索结果评分
"""

import re
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """搜索结果数据类"""
    item: Any           # 搜索的原始对象
    score: int          # 匹配评分（越高越匹配）
    highlighted_title: str      # 高亮后的标题
    highlighted_process: str    # 高亮后的进程名
    match_fields: List[str]     # 匹配的字段列表


class SearchHelper:
    """搜索工具类"""
    
    @staticmethod
    def split_search_query(query: str) -> List[str]:
        """分割搜索查询为关键词列表
        
        Args:
            query: 搜索查询字符串
            
        Returns:
            关键词列表（去重、去空、小写）
        """
        if not query or not query.strip():
            return []
        
        # 按空格分割，去除空字符串，转小写，去重
        keywords = []
        for word in query.strip().split():
            word = word.strip().lower()
            if word and word not in keywords:
                keywords.append(word)
        
        return keywords
    
    @staticmethod
    def highlight_text(text: str, keywords: List[str], 
                      highlight_start: str = "**", 
                      highlight_end: str = "**") -> str:
        """在文本中高亮关键词
        
        Args:
            text: 原始文本
            keywords: 要高亮的关键词列表
            highlight_start: 高亮开始标记
            highlight_end: 高亮结束标记
            
        Returns:
            高亮后的文本
        """
        if not text or not keywords:
            return text
        
        result = text
        
        for keyword in keywords:
            if keyword:
                # 使用正则表达式进行大小写不敏感的替换
                pattern = re.escape(keyword)
                replacement = f"{highlight_start}{keyword}{highlight_end}"
                
                # 使用re.IGNORECASE标志进行大小写不敏感匹配
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    @staticmethod
    def calculate_match_score(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
        """计算文本与关键词的匹配分数

        支持多种匹配模式：
        - 精确包含匹配（最高优先级）
        - 首字母缩写匹配（如 "vsc" 匹配 "Visual Studio Code"）
        - 连续子序列匹配（如 "vscode" 匹配 "Visual Studio Code"）
        - 模糊匹配（允许少量编辑距离）

        Args:
            text: 要匹配的文本
            keywords: 关键词列表

        Returns:
            元组 (匹配分数, 匹配的关键词列表)
        """
        if not text or not keywords:
            return 0, []

        text_lower = text.lower()
        matched_keywords = []
        score = 0

        for keyword in keywords:
            keyword_lower = keyword.lower()
            keyword_score = 0

            # 1. 精确包含匹配（最高分）
            if keyword_lower in text_lower:
                if text_lower == keyword_lower:
                    keyword_score = 100  # 完全匹配
                elif text_lower.startswith(keyword_lower):
                    keyword_score = 80   # 前缀匹配
                elif text_lower.endswith(keyword_lower):
                    keyword_score = 60   # 后缀匹配
                else:
                    keyword_score = 40   # 包含匹配

                keyword_score += len(keyword)
                matched_keywords.append(keyword)

            # 2. 首字母缩写匹配（如 "vsc" -> "Visual Studio Code"）
            elif SearchHelper._match_initials(text, keyword_lower):
                keyword_score = 35 + len(keyword)
                matched_keywords.append(keyword)

            # 3. 连续子序列匹配（如 "vscode" -> "Visual Studio Code"）
            elif SearchHelper._match_subsequence(text_lower, keyword_lower):
                keyword_score = 25 + len(keyword)
                matched_keywords.append(keyword)

            # 4. 模糊匹配（编辑距离，允许少量错误）
            elif len(keyword) >= 3:  # 只对较长的关键词进行模糊匹配
                fuzzy_score = SearchHelper._fuzzy_match_score(text_lower, keyword_lower)
                if fuzzy_score > 0:
                    keyword_score = fuzzy_score
                    matched_keywords.append(keyword)

            score += keyword_score

        return score, matched_keywords

    @staticmethod
    def _match_initials(text: str, keyword: str) -> bool:
        """匹配首字母缩写

        例如：
        - "vsc" 匹配 "Visual Studio Code"
        - "np" 匹配 "Notepad++"

        Args:
            text: 原文本
            keyword: 搜索关键词（小写）

        Returns:
            是否匹配
        """
        if not keyword or not text:
            return False

        # 提取文本中单词的首字母
        words = re.split(r'[\s\-_\.]+', text)
        initials = ''.join(word[0].lower() for word in words if word)

        # 检查关键词是否是首字母的子串
        return keyword in initials

    @staticmethod
    def _match_subsequence(text: str, keyword: str) -> bool:
        """匹配连续子序列

        检查关键词的字符是否按顺序出现在文本中

        例如：
        - "vscode" 匹配 "visual studio code"
        - "notep" 匹配 "notepad++"

        Args:
            text: 原文本（小写）
            keyword: 搜索关键词（小写）

        Returns:
            是否匹配
        """
        if not keyword or not text:
            return False

        # 移除空格进行比较
        text_no_space = text.replace(' ', '').replace('-', '').replace('_', '').replace('.', '')

        # 检查关键词是否是无空格文本的子串
        if keyword in text_no_space:
            return True

        # 检查字符是否按顺序出现
        keyword_idx = 0
        for char in text_no_space:
            if keyword_idx < len(keyword) and char == keyword[keyword_idx]:
                keyword_idx += 1

        # 需要匹配至少60%的字符才算成功
        return keyword_idx >= len(keyword) * 0.6

    @staticmethod
    def _fuzzy_match_score(text: str, keyword: str, max_distance: int = 2) -> int:
        """计算模糊匹配分数（基于编辑距离）

        Args:
            text: 原文本（小写）
            keyword: 搜索关键词（小写）
            max_distance: 允许的最大编辑距离

        Returns:
            匹配分数（0表示不匹配）
        """
        if not keyword or not text:
            return 0

        # 对文本中的每个单词进行模糊匹配
        words = re.split(r'[\s\-_\.]+', text)

        best_score = 0
        for word in words:
            if not word:
                continue
            word_lower = word.lower()

            # 计算编辑距离
            distance = SearchHelper._levenshtein_distance(word_lower, keyword)

            # 允许的编辑距离与关键词长度成正比
            allowed_distance = min(max_distance, len(keyword) // 3)

            if distance <= allowed_distance:
                # 编辑距离越小，分数越高
                word_score = 20 - (distance * 5)
                best_score = max(best_score, word_score)

        return best_score

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """计算两个字符串的编辑距离（Levenshtein距离）

        Args:
            s1: 字符串1
            s2: 字符串2

        Returns:
            编辑距离
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
    
    @staticmethod
    def search_windows(windows: List[Any], query: str) -> List[SearchResult]:
        """搜索窗口列表
        
        Args:
            windows: 窗口信息列表（需要有title和process_name属性）
            query: 搜索查询字符串
            
        Returns:
            搜索结果列表，按匹配度排序
        """
        keywords = SearchHelper.split_search_query(query)
        
        if not keywords:
            # 没有搜索关键词，返回所有窗口
            return [
                SearchResult(
                    item=window,
                    score=0,
                    highlighted_title=window.title,
                    highlighted_process=window.process_name,
                    match_fields=[]
                )
                for window in windows
            ]
        
        results = []
        
        for window in windows:
            # 计算标题匹配
            title_score, title_matches = SearchHelper.calculate_match_score(window.title, keywords)
            
            # 计算进程名匹配
            process_score, process_matches = SearchHelper.calculate_match_score(window.process_name, keywords)
            
            # 总分数（标题权重更高）
            total_score = title_score * 2 + process_score
            
            # 只有匹配的窗口才加入结果
            if total_score > 0:
                # 收集匹配的字段
                match_fields = []
                if title_matches:
                    match_fields.append("title")
                if process_matches:
                    match_fields.append("process")
                
                # 生成高亮文本
                highlighted_title = SearchHelper.highlight_text(window.title, keywords)
                highlighted_process = SearchHelper.highlight_text(window.process_name, keywords)
                
                results.append(SearchResult(
                    item=window,
                    score=total_score,
                    highlighted_title=highlighted_title,
                    highlighted_process=highlighted_process,
                    match_fields=match_fields
                ))
        
        # 按匹配分数降序排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    @staticmethod
    def format_highlighted_text_for_table(text: str) -> str:
        """将高亮标记转换为表格显示格式
        
        Args:
            text: 包含**高亮**标记的文本
            
        Returns:
            适合表格显示的文本（移除标记，但可以用于后续处理）
        """
        # 对于表格显示，暂时移除高亮标记
        # 后续可以通过其他方式实现高亮（如行颜色）
        return text.replace("**", "")
    
    @staticmethod
    def extract_highlight_positions(text: str) -> List[Tuple[int, int]]:
        """提取高亮文本的位置信息
        
        Args:
            text: 包含**高亮**标记的文本
            
        Returns:
            高亮位置列表 [(start, end), ...]
        """
        positions = []
        clean_text = ""
        i = 0
        while i < len(text):
            if text[i:i+2] == "**":
                # 找到高亮开始
                i += 2  # 跳过开始标记
                start_pos = len(clean_text)
                
                # 查找结束标记
                end_marker = text.find("**", i)
                if end_marker != -1:
                    # 提取高亮内容
                    highlight_content = text[i:end_marker]
                    clean_text += highlight_content
                    end_pos = len(clean_text)
                    
                    positions.append((start_pos, end_pos))
                    i = end_marker + 2  # 跳过结束标记
                else:
                    # 没有找到结束标记，按普通文本处理
                    clean_text += text[i]
                    i += 1
            else:
                clean_text += text[i]
                i += 1
        
        return positions


def test_search_functionality():
    """测试搜索功能"""
    print("🧪 测试搜索功能...")

    # 模拟窗口数据
    class MockWindow:
        def __init__(self, title, process_name):
            self.title = title
            self.process_name = process_name

    windows = [
        MockWindow("Google Chrome", "chrome.exe"),
        MockWindow("Visual Studio Code", "Code.exe"),
        MockWindow("微信", "WeChat.exe"),
        MockWindow("Notepad++", "notepad++.exe"),
        MockWindow("Windows Terminal", "WindowsTerminal.exe"),
        MockWindow("Microsoft Word", "WINWORD.EXE"),
        MockWindow("File Explorer", "explorer.exe"),
    ]

    # 测试搜索 - 包含模糊匹配测试
    test_queries = [
        ("chrome", "精确匹配"),
        ("code", "精确匹配"),
        ("微信", "中文匹配"),
        ("note", "前缀匹配"),
        ("chrome code", "多关键词"),
        ("vsc", "首字母缩写 - Visual Studio Code"),
        ("np", "首字母缩写 - Notepad++"),
        ("wt", "首字母缩写 - Windows Terminal"),
        ("vscode", "连续子序列"),
        ("msword", "连续子序列"),
        ("chrom", "模糊匹配 - 少一个字母"),
        ("notepadd", "模糊匹配 - 多一个字母"),
    ]

    for query, description in test_queries:
        print(f"\n搜索: '{query}' ({description})")
        results = SearchHelper.search_windows(windows, query)

        if results:
            for i, result in enumerate(results[:3]):  # 只显示前3个结果
                print(f"  {i+1}. {result.item.title} ({result.item.process_name}) - 分数: {result.score}")
        else:
            print("  无匹配结果")


if __name__ == "__main__":
    test_search_functionality()