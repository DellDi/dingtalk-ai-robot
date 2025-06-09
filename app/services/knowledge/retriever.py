#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库检索服务
"""
import json
import os
from typing import List, Dict, Any, Optional
from loguru import logger
from openai import OpenAI

from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from autogen_core.memory import MemoryContent, MemoryMimeType
from autogen_ext.memory.chromadb import ChromaDBVectorMemory, PersistentChromaDBVectorMemoryConfig

from app.core.config import settings

# 从settings获取配置，提供默认值以防万一
DEFAULT_TONGYI_EMBEDDING_MODEL = getattr(
    settings, "TONGYI_EMBEDDING_MODEL_NAME", "text-embedding-v4"
)
DEFAULT_TONGYI_API_KEY = getattr(settings, "OPENAI_API_KEY", None)
DEFAULT_TONGYI_EMBEDDING_API_ENDPOINT = getattr(settings, "TONGYI_EMBEDDING_API_ENDPOINT", None)
DEFAULT_VECTOR_DB_PATH = getattr(settings, "VECTOR_DB_PATH", "./.chromadb_autogen")

# 默认模型名称，如果未在配置中指定
DEFAULT_TONGYI_EMBEDDING_MODEL = "text-embedding-v4"
DEFAULT_EMBEDDING_DIMENSIONS = 1024


class TongyiQWenOpenAIEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    自定义ChromaDB嵌入函数，通过OpenAI SDK兼容模式调用通义千问文本嵌入API。
    """

    def __init__(
        self,
        model_name: str = DEFAULT_TONGYI_EMBEDDING_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dimensions: Optional[int] = DEFAULT_EMBEDDING_DIMENSIONS,
    ):
        self.model_name = model_name
        self.api_key = api_key or settings.TONGYI_API_KEY
        self.base_url = base_url or settings.TONGYI_EMBEDDING_API_ENDPOINT
        self.dimensions = dimensions

        if not self.api_key:
            raise ValueError(
                "通义千问API密钥未配置。请设置 TONGYI_API_KEY 环境变量或在初始化时传入。"
            )
        if not self.base_url:
            raise ValueError(
                "通义千问API Base URL未配置。请设置 TONGYI_EMBEDDING_API_ENDPOINT 或在初始化时传入。"
            )

        try:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            logger.error(f"初始化OpenAI客户端失败: {e}", exc_info=True)
            raise ValueError(f"初始化OpenAI客户端失败: {e}") from e

        logger.info(
            f"通义千问OpenAI兼容嵌入函数初始化完成，使用模型: {self.model_name}, Base URL: {self.base_url}, Dimensions: {self.dimensions}"
        )

    def __call__(self, input_texts: Documents) -> Embeddings:
        """
        为输入的文档列表生成嵌入 (同步方法)。
        """
        if not isinstance(input_texts, list):
            raise ValueError(f"输入必须是文本列表，但得到的是: {type(input_texts)}")
        if not input_texts:
            return []

        # 确保所有输入都是字符串
        if not all(isinstance(text, str) for text in input_texts):
            raise ValueError("输入列表中的所有元素都必须是字符串。")

        try:
            logger.debug(
                f"使用OpenAI兼容模式为 {len(input_texts)} 个文本生成嵌入，模型: {self.model_name}, 维度: {self.dimensions}"
            )
            response = self.client.embeddings.create(
                model=self.model_name,
                input=input_texts,
                dimensions=self.dimensions,
                encoding_format="float",
            )

            # OpenAI SDK 返回的 response.data 是一个列表，每个对象有 'embedding' 和 'index'
            # 我们需要根据 'index' 排序以确保与输入顺序一致
            if not response.data or len(response.data) != len(input_texts):
                logger.error(
                    f"OpenAI兼容API调用成功，但返回的嵌入数量与输入不匹配。输入: {len(input_texts)}, 输出: {len(response.data) if response.data else 0}"
                )
                raise ValueError("OpenAI兼容API返回的嵌入数量与输入不匹配。")

            # 创建一个足够大的列表来存放结果，并按index填充
            sorted_embeddings: List[Optional[List[float]]] = [None] * len(input_texts)
            for item in response.data:
                idx = item.index
                if 0 <= idx < len(input_texts):
                    sorted_embeddings[idx] = item.embedding
                else:
                    logger.warning(
                        f"API返回的嵌入索引 {idx} 超出输入文本列表范围 {len(input_texts)}。"
                    )

            if any(e is None for e in sorted_embeddings):
                # 这种情况理论上不应该发生，如果API行为符合预期且上面长度检查通过
                logger.error("未能正确处理所有从API返回的嵌入（部分索引可能无效或丢失）。")
                raise ValueError("OpenAI兼容API返回的嵌入数据不完整或索引错误。")

            # 类型断言，此时 sorted_embeddings 中不应有 None
            final_embeddings = [emb for emb in sorted_embeddings if emb is not None]
            logger.debug(f"成功生成 {len(final_embeddings)} 个嵌入向量。")
            return final_embeddings

        except Exception as e:
            # 捕获OpenAI API调用时可能发生的任何异常
            logger.error(f"使用OpenAI兼容模式生成嵌入时发生错误: {e}", exc_info=True)
            # 可以根据具体的OpenAI异常类型进行更细致的处理
            # 例如: openai.APIError, openai.APIConnectionError, openai.RateLimitError, etc.
            raise ValueError(f"OpenAI兼容嵌入API调用失败: {e}") from e


class KnowledgeRetriever:
    """知识库检索器，使用AutoGen的ChromaDBVectorMemory和自定义通义千问HTTP嵌入进行RAG。"""

    def __init__(
        self,
        collection_name: str = "autogen_knowledge_collection",
        persistence_path: Optional[str] = None,
        embedding_model_name: str = DEFAULT_TONGYI_EMBEDDING_MODEL,
        tongyi_api_key: Optional[str] = None,
        tongyi_base_url: Optional[str] = None,
        embedding_dimensions: Optional[int] = DEFAULT_EMBEDDING_DIMENSIONS,
        retrieve_k: int = 5,
        retrieve_score_threshold: float = 0.4,
    ):
        """
        初始化知识库检索器。

        参数:
            collection_name (str): ChromaDB中的集合名称。
            persistence_path (Optional[str]): ChromaDB持久化路径。如果为None，则使用内存模式。
                                            默认为 settings.VECTOR_DB_PATH。
            embedding_model_name (str): 用于嵌入的通义千问模型名称。
            tongyi_api_key (Optional[str]): 通义千问API密钥。默认为 settings.TONGYI_API_KEY。
            tongyi_base_url (Optional[str]): 通义千问API端点。默认为 settings.TONGYI_EMBEDDING_API_ENDPOINT。
            embedding_dimensions (Optional[int]): 嵌入向量的维度。
            retrieve_k (int): 检索时返回的top k结果数量。
            retrieve_score_threshold (float): 检索结果的最小相似度得分。
        """
        self.collection_name = collection_name
        self.persistence_path = (
            persistence_path if persistence_path is not None else DEFAULT_VECTOR_DB_PATH
        )
        self.embedding_model_name = embedding_model_name
        self.tongyi_api_key = (
            tongyi_api_key if tongyi_api_key is not None else DEFAULT_TONGYI_API_KEY
        )
        self.tongyi_base_url = (
            tongyi_base_url
            if tongyi_base_url is not None
            else DEFAULT_TONGYI_EMBEDDING_API_ENDPOINT
        )
        self.embedding_dimensions = embedding_dimensions
        self.retrieve_k = retrieve_k
        self.retrieve_score_threshold = retrieve_score_threshold

        self.tongyi_embedding_function: Optional[TongyiQWenOpenAIEmbeddingFunction] = None
        self.vector_memory: Optional[ChromaDBVectorMemory] = None
        self.initialized = False
        logger.info(
            f"KnowledgeRetriever已配置: 集合='{self.collection_name}', 路径='{self.persistence_path}', 嵌入模型='{self.embedding_model_name}'"
        )

    async def initialize(self):
        """异步初始化嵌入函数和ChromaDB向量内存。"""
        if self.initialized:
            logger.info("KnowledgeRetriever已初始化，跳过。")
            return

        try:
            logger.info("开始初始化KnowledgeRetriever...")
            if not self.tongyi_api_key:
                logger.error("通义千问API密钥未在设置中配置 (TONGYI_API_KEY)。")
                raise ValueError("通义千问API密钥未配置。")
            if not self.tongyi_base_url:
                logger.error("通义千问API端点未在设置中配置 (TONGYI_EMBEDDING_API_ENDPOINT)。")
                raise ValueError("通义千问API端点未配置。")

            self.tongyi_embedding_function = TongyiQWenOpenAIEmbeddingFunction(
                api_key=self.tongyi_api_key,
                model_name=self.embedding_model_name,
                base_url=self.tongyi_base_url,
                dimensions=self.embedding_dimensions,
            )
            logger.info("通义千问OpenAI兼容嵌入函数已创建。")

            if self.persistence_path:
                os.makedirs(self.persistence_path, exist_ok=True)
                logger.info(f"持久化路径 '{self.persistence_path}' 已确认/创建。")

            chroma_config = PersistentChromaDBVectorMemoryConfig(
                collection_name=self.collection_name,
                persistence_path=self.persistence_path,
                embedding_function=self.tongyi_embedding_function,  # 传递自定义嵌入函数
                k=self.retrieve_k,
                score_threshold=self.retrieve_score_threshold,
            )
            logger.info(f"ChromaDB配置准备就绪。")

            self.vector_memory = ChromaDBVectorMemory(config=chroma_config)
            logger.info("ChromaDBVectorMemory已实例化。")

            # 尝试添加一个虚拟条目以确保连接和集合创建成功
            # AutoGen的ChromaDBVectorMemory的add方法是同步的。
            # 我们需要确保这里的调用方式是合适的。
            # MemoryContent的创建是同步的，add的调用也是同步的。
            # 嵌入函数内部的异步转同步调用是这里的关键点。
            logger.info("尝试添加初始化测试条目到向量内存...")
            await self.vector_memory.add(
                MemoryContent(
                    content="系统初始化测试条目",
                    mime_type=MemoryMimeType.TEXT,
                    metadata={"source": "initialization"},
                )
            )
            logger.info("初始化测试条目添加成功（或已存在）。")
            # 如果需要，可以立即清除，但这通常用于测试连接
            # self.vector_memory.clear()

            self.initialized = True
            logger.info("KnowledgeRetriever初始化完成。")

        except Exception as e:
            logger.error(f"KnowledgeRetriever初始化失败: {e}", exc_info=True)
            self.initialized = False  # 确保状态正确
            # OpenAI embedding function does not require explicit session closing
            raise  # 重新抛出异常，让调用者知道失败了

    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        text_key: str = "content",
        metadata_key: Optional[str] = "metadata",
    ):
        """
        异步添加文档到向量数据库。

        参数:
            documents (List[Dict[str, Any]]): 文档字典列表。每个字典应包含文本内容，并可选地包含元数据。
            text_key (str): 文档字典中包含文本内容的键名，默认为 "content"。
            metadata_key (Optional[str]): 文档字典中包含元数据字典的键名，默认为 "metadata"。
        """
        if not self.initialized or not self.vector_memory:
            logger.error("KnowledgeRetriever尚未初始化。请先调用initialize()。")
            raise RuntimeError("KnowledgeRetriever尚未初始化。")

        if not documents:
            logger.info("没有文档需要添加。")
            return

        memory_contents = []
        for doc in documents:
            content = doc.get(text_key)
            if not content or not isinstance(content, str):
                logger.warning(f"文档缺少有效的文本内容或格式不正确，已跳过: {doc}")
                continue

            metadata = doc.get(metadata_key) if metadata_key else {}
            if not isinstance(metadata, dict):
                logger.warning(f"文档元数据格式不正确（应为字典），已使用空元数据: {doc}")
                metadata = {}

            memory_contents.append(
                MemoryContent(content=content, mime_type=MemoryMimeType.TEXT, metadata=metadata)
            )

        if not memory_contents:
            logger.info("处理后没有有效的MemoryContent对象可添加。")
            return

        try:
            # ChromaDBVectorMemory.add is called for each item
            for mc_item in memory_contents:
                await self.vector_memory.add(mc_item)
            logger.info(f"成功添加 {len(memory_contents)} 个文档到 '{self.collection_name}' 集合。")
        except Exception as e:
            logger.error(f"添加文档到ChromaDB时发生错误: {e}", exc_info=True)
            raise

    async def search(
        self, query_text: str, k: Optional[int] = None, threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        异步从向量数据库检索相关文档。

        参数:
            query_text (str): 查询文本。
            k (Optional[int]): 要检索的文档数量。如果为None，则使用初始化时的retrieve_k。
            threshold (Optional[float]): 相似度阈值。如果为None，则使用初始化时的retrieve_score_threshold。

        返回:
            List[Dict[str, Any]]: 检索到的文档列表，每个文档包含内容和元数据及相似度得分。
        """
        if not self.initialized or not self.vector_memory:
            logger.error("KnowledgeRetriever尚未初始化。请先调用initialize()。")
            raise RuntimeError("KnowledgeRetriever尚未初始化。")

        # ChromaDBVectorMemory.query 是同步方法
        # 它内部会使用配置的k和score_threshold，但这里允许覆盖
        # 注意：ChromaDBVectorMemory的query方法不直接接受k和threshold参数，
        # 它们是在配置中设置的。如果需要动态调整，可能需要重新配置或扩展该类。
        # AutoGen的Memory协议的query方法通常只接受查询文本。
        # 我们将遵循Memory协议，k和threshold在初始化时设置。
        # 如果确实需要动态k和threshold，需要查看ChromaDBVectorMemory是否支持或需要自定义。
        # 目前，我们将忽略这里的k和threshold参数，依赖于初始化设置。
        if k is not None or threshold is not None:
            logger.warning("search方法中的k和threshold参数当前被忽略，依赖于初始化配置。")

        try:
            # Memory.query 通常返回 MemoryQueryResult 对象
            retrieved_memory_contents_obj = await self.vector_memory.query(query_text)

            results = []
            logger.debug(
                f"Raw retrieved_memory_contents_obj type: {type(retrieved_memory_contents_obj)}"
            )

            list_of_memory_content = []
            if retrieved_memory_contents_obj is not None:
                for yielded_item in retrieved_memory_contents_obj:
                    if (
                        isinstance(yielded_item, tuple)
                        and len(yielded_item) == 2
                        and yielded_item[0] == "results"
                        and isinstance(yielded_item[1], list)
                    ):
                        list_of_memory_content = yielded_item[1]
                        logger.debug(
                            f"Successfully extracted list of MemoryContent objects. Count: {len(list_of_memory_content)}"
                        )
                        if list_of_memory_content and isinstance(
                            list_of_memory_content[0], MemoryContent
                        ):
                            logger.debug(f"First MemoryContent object: {list_of_memory_content[0]}")
                        break  # Assuming only one such tuple ('results', ...) is yielded by MemoryQueryResult
                    else:
                        logger.warning(
                            f"Unexpected item yielded by MemoryQueryResult: {type(yielded_item)}. Value: {yielded_item}. Skipping this item."
                        )

            if not list_of_memory_content:
                logger.info(
                    f"No MemoryContent objects found in the query result for '{query_text[:50]}...'"
                )

            for mem_content in list_of_memory_content:
                if not isinstance(mem_content, MemoryContent):
                    logger.warning(
                        f"Item in list is not MemoryContent: {type(mem_content)}. Skipping."
                    )
                    continue

                score = mem_content.metadata.get("score") if mem_content.metadata else None

                results.append(
                    {
                        "content": mem_content.content,
                        "metadata": mem_content.metadata,  # Contains original metadata and score
                        "score": score,  # Explicitly adding score here for clarity, though it's in metadata
                    }
                )

            logger.info(f"为查询 '{query_text[:50]}...' 检索到 {len(results)} 个结果。")
            return results
        except Exception as e:
            logger.error(f"从ChromaDB检索文档时发生错误: {e}", exc_info=True)
            raise

    def close(self):
        """关闭资源。对于OpenAI SDK和ChromaDBVectorMemory，通常不需要显式关闭。"""
        # TongyiQWenOpenAIEmbeddingFunction (使用 OpenAI SDK) 不需要显式关闭会话。
        # AutoGen 中的 ChromaDBVectorMemory 也没有需要用户调用的公开异步 close() 方法。
        # 如果 ChromaDB 客户端本身需要清理，通常由库内部同步处理或自动管理。
        logger.info("KnowledgeRetriever.close() 已调用。资源通常由底层库管理。")
        self.initialized = False
        logger.info("KnowledgeRetriever资源已关闭状态更新。")


# 示例用法 (通常在其他模块中调用):
async def example_usage():  # pragma: no cover
    if not DEFAULT_TONGYI_API_KEY or not DEFAULT_TONGYI_EMBEDDING_API_ENDPOINT:
        logger.error("示例用法中止：请配置通义千问API密钥和端点。")
        return

    retriever = KnowledgeRetriever(
        collection_name="data_autogen", persistence_path="./.chroma_test_db"
    )
    try:
        await retriever.initialize()

        # 添加文档
        docs_to_add = [
            {"content": "AutoGen是一个多智能体对话框架。", "metadata": {"source": "doc1"}},
            {"content": "ChromaDB是一个向量存储数据库。", "metadata": {"source": "doc2"}},
            {"content": "通义千问提供了强大的文本嵌入模型。", "metadata": {"source": "doc3"}},
        ]
        await retriever.add_documents(docs_to_add)

        # 搜索文档
        query = "什么是AutoGen？"
        search_results = await retriever.search(query)
        logger.info(f"搜索 '{query}' 的结果:")
        for res in search_results:
            logger.info(f"  内容: {res['content']}, 元数据: {res['metadata']}")

        query2 = "什么是ChromaDB"
        search_results2 = await retriever.search(query2)
        logger.info(f"搜索 '{query2}' 的结果:")
        for res in search_results2:
            logger.info(f"  内容: {res['content']}, 元数据: {res['metadata']}")

    except Exception as e:
        logger.error(f"示例用法中发生错误: {e}", exc_info=True)
    finally:
        if retriever.initialized:
            retriever.close()


if __name__ == "__main__":  # pragma: no cover
    import asyncio # 现在需要了
    # 配置日志记录器以查看输出
    # import sys # 如果要用stderr
    # logger.add(sys.stderr, level="DEBUG")
    asyncio.run(example_usage())
