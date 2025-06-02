# NLLBTranslator 使用说明与性能观察

本文档介绍了 `NLLBTranslator` 类（位于 [`core/translators/nllb_translator.py`](core/translators/nllb_translator.py)）的使用方法，并总结了通过测试观察到的关于其处理长文本、编号和自定义分隔符时的性能特点。

## 1. NLLBTranslator 简介

`NLLBTranslator` 是一个基于 Hugging Face `transformers` 库和 Facebook AI 的 NLLB (No Language Left Behind) 系列模型的翻译工具。它主要设计用于实现高质量的多语言翻译，在本项目中，我们特别关注其在日文到中文（简体和繁体）翻译任务上的应用。

默认使用的模型是 `facebook/nllb-200-distilled-600M`。

## 2. 如何使用 `NLLBTranslator`

### 初始化

可以通过以下方式初始化 `NLLBTranslator`：

```python
from core.translators.nllb_translator import NLLBTranslator

# 使用默认设置:
# - 模型: facebook/nllb-200-distilled-600M
# - 源语言: "jpn_Jpan" (日语)
# - 目标语言: "zho_Hans" (简体中文)
# cache_dir 参数是必需的，用于指定模型下载和缓存的目录。
translator = NLLBTranslator(cache_dir="path/to/your/model_cache_directory")

# 自定义模型、语言和缓存目录:
translator_custom = NLLBTranslator(
    model_name="facebook/nllb-200-distilled-600M", # 或其他兼容的 NLLB 模型
    cache_dir="path/to/your/model_cache_directory",
    source_lang_code="jpn_Jpan",       # 例如，日语
    target_lang_code="zho_Hant"        # 例如，翻译为繁体中文
)
```

### 翻译文本

`translate` 方法接收一个**字符串列表**作为输入，并返回一个包含对应翻译结果的字符串列表。

```python
texts_to_translate = ["こんにちは、世界。", "これはテストです。"]
translations = translator.translate(texts_to_translate)

# 示例输出 (实际输出可能因模型版本略有不同):
# translations 将是: ['您好,世界.', '这是一个测试.'] 
print(translations)
```

**重要提示**：`translate` 方法的核心设计是处理独立的文本片段。如果向其传递一个包含单个长字符串（该字符串内部可能包含您手动添加的编号或分隔符）的列表，例如 `["片段1<sep>片段2"]`，它会将整个长字符串视为一个翻译单元，并返回一个包含对该长字符串整体翻译结果的单个字符串的列表。模型本身不保证解析或保留您在字符串内部添加的结构。

## 3. 性能测试与观察结论

通过一系列测试，我们对 `NLLBTranslator`（使用 `facebook/nllb-200-distilled-600M` 模型）的性能特点进行了观察：

### a. 标准处理方式
- 当输入一个文本列表（例如 `["句子1", "句子2", "句子3"]`）时，`NLLBTranslator` 会为列表中的每个字符串生成独立的翻译，并返回一个对应翻译的列表（例如 `["翻译1", "翻译2", "翻译3"]`）。这是推荐的使用方式。

### b. 处理单一长文本输入（包含手动结构）
当将多个逻辑片段拼接成一个单一的长字符串（可能包含手动编号或自定义分隔符）并作为列表中的唯一元素传递给 `translate` 方法时，观察到以下行为：

-   **可处理性与输出长度**：
    -   模型能够接收并处理相对较长的单一文本输入。例如，一次测试中约1200个日文字符的输入得到了约443个中文字符的输出。
    -   输出的字符长度通常会显著少于输入字符长度。这部分是由于不同语言的信息密度差异，以及模型可能对输入中的重复内容进行了一定的语义压缩。

-   **截断风险**：
    -   尽管可以处理长文本，但当输入非常长，接近或可能超过模型内部的token限制（NLLB-600M 的上下文窗口大约是 512-1024 tokens）时，仍然存在内容被部分截断的风险，导致翻译不完整。
    -   在一次测试中，包含5个编号日文片段（通过换行符和 "数字." 格式拼接）的单一输入字符串，其翻译结果只包含了前3个片段的内容。

-   **对内部结构（编号、分隔符）的处理**：
    -   **手动编号 (例如 "1. text\n2. text")**：模型**不保证保留**原始的数字编号格式。在测试中，输入的 "1.", "2." 等编号在输出中被转换为了中文的序数词，如“首先,”、“第二,”。
    -   **自定义分隔符 (例如 `<#-#>`)**：模型在翻译过程中**不会保留**这些自定义的特殊字符序列分隔符。如果输入是 `"片段1<#-#>片段2<#-#>片段3"`，输出的将是一个移除了 `<#-#>` 的连续文本块，导致无法通过原始分隔符进行切分。
    -   **换行符 (`\n`)**：输入中的换行符可能会被模型部分保留或被忽略，输出文本的分行情况与输入不完全一致。

## 4. 使用建议

基于以上观察，为了获得最佳且最可控的翻译结果：

-   **最佳实践：分段翻译**
    -   强烈建议将待翻译的长篇内容（如一整页漫画的所有对话框文本）在送入翻译器之前，**预先分割成独立的、有意义的短句或文本片段**。
    -   然后，将这些独立的片段组成一个列表，传递给 `NLLBTranslator.translate()` 方法。
    -   最后，根据这些独立翻译结果的原始顺序，将它们重新组合或应用到您的目标位置。

    ```python
    # 推荐的使用方式
    individual_japanese_sentences = [
        "こんにちは、世界。", 
        "これはテストです。",
        "ありがとうございます。"
    ]
    translated_chinese_sentences = translator.translate(individual_japanese_sentences)
    # translated_chinese_sentences 示例: ['您好,世界.', '这是一个测试.', '谢谢你.']
    
    # 后续可以根据原始文本的标识符或顺序来使用这些翻译结果
    for i, original_text in enumerate(individual_japanese_sentences):
        print(f"原文: {original_text} -> 译文: {translated_chinese_sentences[i]}")
    ```

-   **避免拼接长文本进行单次翻译**
    -   不推荐将多个独立的文本片段（尤其是如果您试图通过内部编号或特殊分隔符来维持结构）拼接成一个单一的长字符串，然后期望模型能完美地按结构返回分段翻译。模型很可能无法满足这种期望，且存在内容截断和结构丢失的风险。

-   **注意单个句子的长度**
    -   虽然模型可以处理较长的单个句子，但对于远超数百字符的极长单句，也应注意可能出现的翻译质量下降或不完整的问题。将其拆分为更短的子句可能更稳妥。

## 5. 依赖项

确保您的环境中安装了以下主要依赖：
-   `transformers` (Hugging Face Transformers 库)
-   `sentencepiece` (NLLB 模型通常需要)
-   `torch` (PyTorch，作为 `transformers` 的后端)

这些通常可以通过项目的 `requirements.txt` 文件进行安装。