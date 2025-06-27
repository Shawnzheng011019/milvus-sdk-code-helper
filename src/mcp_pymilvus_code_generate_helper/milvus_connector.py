import ast
import logging
import os

from openai import OpenAI
from pymilvus import AnnSearchRequest, MilvusClient, WeightedRanker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("milvus-connector")


class MilvusConnector:
    def __init__(
        self,
        milvus_uri: str = "http://localhost:19530",
        milvus_token: str = "",
        db_name: str = "default",
    ):
        logger.debug("Initializing MilvusConnector")
        self.milvus_uri = milvus_uri
        self.milvus_token = milvus_token
        self.db_name = db_name

        self.milvus_client = MilvusClient(uri=milvus_uri, token=milvus_token, db_name=db_name)
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        try:
            self.milvus_client.load_collection("pymilvus_user_guide")
            self.milvus_client.load_collection("mcp_orm")
            self.milvus_client.load_collection("mcp_milvus_client")
            self.milvus_client.load_collection("mcp_multi_language_docs")
        except Exception as e:
            logger.error(f"Fail to load collection: {e}")

    def create_embedding(self, text):
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small", input=text
            )
            embedding = response.data[0].embedding
            return embedding
        except Exception as e:
            logger.error(f"Fail to create embedding from user query: {e}")
            return None

    def search_similar_documents(
        self, collection_name, query_text, top_k=10, output_fields=["metadata", "content"]
    ):
        query_embedding = self.create_embedding(query_text)
        if query_embedding is None:
            logger.error("Fail to create embedding from user query. Stop.")
            return []

        try:
            vector_request = AnnSearchRequest(
                data=[query_embedding],
                anns_field="dense",
                param={
                    "metric_type": "IP",
                },
                limit=top_k,
            )

            text_request = AnnSearchRequest(
                data=[query_text],
                anns_field="sparse",
                param={
                    "metric_type": "BM25",
                },
                limit=top_k,
            )

            requests = [vector_request, text_request]

            ranker = WeightedRanker(0.5, 0.5)

            results = self.milvus_client.hybrid_search(
                collection_name=collection_name,
                reqs=requests,
                ranker=ranker,
                limit=top_k,
                output_fields=output_fields,
            )

            return results

        except Exception as e:
            logger.warning(f"Hybrid search failed when searching for similar documents: {e}")
            return []

    async def pypmilvus_code_generator(self, query) -> str:
        """
        Retrieve related pymilvus code/documents for a given query.

        Args:
            query: User query for generating code in natural language

        Returns:
            str: Related pymilvus code/documents for generating code from user query
        """
        results = self.search_similar_documents("pymilvus_user_guide", query)

        if not results:
            logger.warning("No related document found.")
            return "No related document found."

        related_documents = "Here are related pymilvus code/documents found to help you generate code from user query:\n\n"
        for i, hit in enumerate(results[0]):
            content = hit["entity"]["content"]
            metadata = hit["entity"].get("metadata", "")
            related_documents += f"{i + 1} (File: {metadata}):\n{content}\n\n"

        return related_documents

    async def orm_client_code_convertor(self, query) -> str:
        """
        Retrieve related orm and pymilvus client code/documents for a given query.

        Args:
            query: A string of Milvus API names in list format from user query and code context to translate between orm and milvus client

        Returns:
            str: Related orm and pymilvus client code/documents
        """

        orm_results = self.search_similar_documents("mcp_orm", query)

        if not orm_results:
            logger.warning("No related orm document found.")
            return "No related orm document found."

        milvus_client_results = self.search_similar_documents("mcp_milvus_client", query)

        if not milvus_client_results:
            logger.warning("No related milvus client document found.")
            return "No related milvus client document found."

        related_documents = "Here are related orm and pymilvus client code/documents found to help you translate orm code to milvus client from user query:\n\n"

        related_documents += "Related ORM documents:\n\n"
        for i, hit in enumerate(orm_results[0]):
            content = hit["entity"]["content"]
            metadata = hit["entity"].get("metadata", "")
            related_documents += f"{i + 1} (File: {metadata}):\n{content}\n\n"

        related_documents += "Related Milvus Client documents:\n\n"
        for i, hit in enumerate(milvus_client_results[0]):
            content = hit["entity"]["content"]
            metadata = hit["entity"].get("metadata", "")
            related_documents += f"{i + 1} (File: {metadata}):\n{content}\n\n"

        return related_documents

    async def milvus_code_translator(
        self, query: str, source_lang: str, target_lang: str
    ) -> str:
        """
        Retrieve related documents and code snippets in different programming languages for translation.

        Args:
            query (str): A string of Milvus API names in list format to translate from one programming language to another (e.g., ['create_collection', 'insert', 'search'])
            source_lang (str): The source programming language (e.g., 'python', 'java', 'go')
            target_lang (str): The target programming language (e.g., 'python', 'java', 'go')

        Returns:
            str: A formatted string containing the related documents and code snippets in both languages,
                 or an error message if no similar documents are found.
        """
        try:
            api_list = ast.literal_eval(query)
            query = ", ".join(api_list)
        except (ValueError, SyntaxError) as e:
            logger.error(f"Failed to parse query string: {e}")
            return f"Invalid query format. Expected a string representation of a list, got: {query}"

        valid_languages = ["python", "node", "java", "go", "csharp", "restful"]
        if source_lang not in valid_languages or target_lang not in valid_languages:
            logger.warning(
                f"Invalid language. source_lang: {source_lang}, target_lang: {target_lang}"
            )
            return f"Invalid language. Supported languages are: {', '.join(valid_languages)}"

        results = []

        for api in api_list:
            results.append(
                self.search_similar_documents(
                    "mcp_multi_language_docs",
                    api,
                    top_k=1,
                    output_fields=["file_name", source_lang, target_lang],
                )
            )

        results.append(
            self.search_similar_documents(
                "mcp_multi_language_docs",
                query,
                top_k=5,
                output_fields=["file_name", source_lang, target_lang],
            )
        )

        if not results:
            return "No similar documents found."

        # Remove duplicates from results
        unique_file_names = set()
        unique_results = []
        for result in results:
            print("result")
            print(result)
            for hit in result[0]:
                entity = hit["entity"]
                file_name = entity.get("file_name", "Unknown")
                if file_name not in unique_file_names:
                    unique_file_names.add(file_name)
                    unique_results.append(hit)
        results = unique_results

        formatted_results = f"Found similar documents and code snippets for translation from {source_lang} to {target_lang}:\n\n"

        for i, hit in enumerate(results):
            entity = hit["entity"]
            file_name = entity.get("file_name", "Unknown")
            source_content = entity.get(source_lang)
            target_content = entity.get(target_lang)

            formatted_results += f"Document {i + 1} (File: {file_name}):\n"
            formatted_results += f"Source ({source_lang}):\n{source_content}\n\n"
            formatted_results += f"Target ({target_lang}):\n{target_content}\n"
            formatted_results += "-" * 80 + "\n\n"

        return formatted_results
