from dotenv import load_dotenv
import os
import json
import csv
import ast
from langchain_openai import ChatOpenAI
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.documents import Document

#user specified libraries
from utils import kg_utils
from utils.kg_utils import german_prompt


# Initialize Knowledge Graph
kg = kg_utils.KnowledgeGraph()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
llm = ChatOpenAI(temperature=0, model_name="gpt-4-0125-preview", api_key = OPENAI_API_KEY)
llm_transformer = LLMGraphTransformer(llm=llm, prompt=german_prompt)

# Create Nodes for sections, pages, categories
# First Sections
with open("../data/small_embedded_chunks.csv") as input_csv:
    processed_rows = 0
    batch_size = 1
    document_batch = []
    reader = csv.DictReader(input_csv)

    #delete all existing nodes and relationshiops
    kg.query("""
    MATCH (n)
    DETACH DELETE n""")

    #write in new nodes and relationships
    for row in reader:
        processed_rows+=1
        row["cls_embed"] = ast.literal_eval(row["cls_embed"])
        #create node for each section
        kg.query(query=kg_utils.merge_section_node_query, params = row)
        #automatically extract nodes from each section
        doc = Document(page_content=row["section"])
        document_batch.append(doc)
        if len(document_batch) >= batch_size:
            graph_documents = llm_transformer.convert_to_graph_documents(document_batch)
            print(f"Num Nodes:{len(graph_documents[0].nodes)}")
            print(f"Num Relationships:{len(graph_documents[0].relationships)}")
            kg.add_graph_documents(graph_documents=graph_documents)
            for gdoc in graph_documents:
                for node in gdoc.nodes:
                    node_dict = {"section_id": row["section_id"], "node_id": node.id}
                    kg.query(query=kg_utils.sect_auto_nodes_query, params=node_dict)

            # manually add "mentions" connection
            document_batch = []


    print(f"Created {processed_rows} section-nodes")

#Section Pages & Categories
unique_categories = set()
with open("../data/small_embedded_pages.csv") as pages_input:
    pages_reader = csv.DictReader(pages_input)
    processed_rows = 0

    for row in pages_reader:
        #Create page node
        processed_rows+=1
        row["cls_embed"] = ast.literal_eval(row["cls_embed"])
        row["categories"] = ast.literal_eval(row["categories"])
        kg.query(query=kg_utils.merge_page_node_query, params=row)

        #create new category node if not yet existing
        for category in row["categories"]:
            if category not in unique_categories:
                unique_categories.add(category)
                cat_dict = {"category_name":category}
                kg.query(query=kg_utils.merge_category_node_query, params=cat_dict)
                print(f"Created Category node:{category}")
                del cat_dict

        #merge-create new page and category nodes
        kg.query(query=kg_utils.merge_page_node_query, params=row)
        #create relationship between all subsequent nodes of a page
        kg.query(query=kg_utils.sect_sect_edge_query, params=row)


    print(f"Created {processed_rows} page-nodes")
    print(f"Created {len(unique_categories)} category-nodes")


# Create Relationship between existing nodes
num_sect_page_rels = kg.query(query=kg_utils.sect_page_edge_query)
num_page_cat_rels = kg.query(query=kg_utils.page_cat_edge_query)
num_first_rels = kg.query(query=kg_utils.page_first_sect)

print(f"Created {num_sect_page_rels} relationships btw. sections and pages")
print(f"Created {num_page_cat_rels} relationships btw. pages and categories")
print(f"Created {num_first_rels} relationships of pages to their first chunks")









