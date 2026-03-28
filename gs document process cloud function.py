import functions_framework
import requests
from retrying import retry
# Above using in extracting text from online
import nltk
nltk.download('punkt')
import re
import os
import pinecone
import openai
from langchain.text_splitter import NLTKTextSplitter
from PyPDF2 import PdfReader
from langchain.embeddings import OpenAIEmbeddings
from google.cloud import storage
import json
import time
from io import BytesIO
import gcsfs
import tiktoken
from datetime import datetime
from flask import Flask, request, jsonify
import uuid
from gcp import *

logger = gcp_logger()
func_conf = gcp_get_config()
project_id = gcp_project_id()

tokenizer = tiktoken.get_encoding('cl100k_base')
def tiktoken_len(text):
    tokens = tokenizer.encode(
        text,
        disallowed_special=()
    )
    return len(tokens)

@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
def create_embedding(article):
    # vectorize with OpenAI text-emebdding-ada-002
    embedding_model = func_conf.get( 'embedding_model', 'text-embedding-ada-002' )
    embedding = openai.Embedding.create(
        input=article,
        model=embedding_model
    )
    
    return embedding["data"][0]["embedding"]

def get_all_files_in_directory(directory):
    return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]


def clean(text):
    if text:
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        return text
    return


text_splitter = NLTKTextSplitter(
    chunk_size=300, 
    chunk_overlap=20,  # number of tokens overlap between chunks
    length_function=tiktoken_len,
)


# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def main(cloud_event):
    data = cloud_event.data

    event_id = cloud_event["id"]
    event_type = cloud_event["type"]

    bucket = data["bucket"]
    name = data["name"]
    storage_client = storage.Client()
    bucket_ref = storage_client.get_bucket(bucket)
    if '.json' in name:
        print('Metadata Json uploaded')
        return

    logger.debug(f"Event ID: {event_id}")
    logger.debug(f"Event type: {event_type}")
    logger.debug(f"Bucket: {bucket}")
    logger.debug(f"File: {name}")
    metaJsonName = name.split('.')[0] + '.json'
    meta_json = read_jsoncontent(bucket, metaJsonName)
    if not meta_json:
        return "meta json not existed, please try again later"
    blob = bucket_ref.blob(name)
    pdf_bytes = blob.download_as_bytes()
    gcs_file_system = gcsfs.GCSFileSystem(project=project_id)
    gcs_pdf_path = f"gs://{bucket}/{name}"
    if 'https:' in name and '.pdf' not in name:
        logger.debug("Should not execute html extract function")
    else:
        f_object = gcs_file_system.open(gcs_pdf_path, "rb")
        logger.debug("start extract")
        extract_text_with_page_numbers(f_object, name, meta_json)
        f_object.close()
    return create_response('All docs are processed', 200)

def extract_text_with_page_numbers(f_object, file_path, meta_json):
    # Get the name only
    if '.' in file_path:
        file_path = file_path.split('.')[0]
    pdf = PdfReader(f_object)
    project_number = gcp_project_number(project_id)
    openai.api_key = gcp_get_secret(project_number,func_conf.get( 'openai_api_key', 'openai_api_key_name' ))
    pinecone_api = gcp_get_secret(project_number,func_conf.get( 'pinecone_api_key', 'pinecone_api_key_name' ))
    pinecone_env = func_conf.get( 'pinecone_env', 'eu-west4-gcp' )

    pinecone.init(api_key=pinecone_api, environment=pinecone_env)
    pine_index = func_conf.get( 'pinecone_index', 'gen-search-embedding')
    index = pinecone.Index(pine_index)

    # Initialize variables
    full_text = ''
    page_lengths = []
  
    # Extract all text and remember how many chunks are in each page
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            full_text += text
        page_lengths.append(len(text_splitter.split_text(full_text)))

    # Tokenize the full text
    chunks = text_splitter.split_text(full_text)
  
    # Map each chunk to a page
    page_number = 1
    pinecone_vectors = []
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    cleanFullText = clean(full_text)
    contentId = str( uuid.uuid4() )
    for i, chunk in enumerate(chunks):
        logger.debug(f"process chunk {i} of file {file_path}")
        cleanText = clean(chunk)
        cleanExpandChunk = expand_chunk(cleanText, cleanFullText)
        logger.debug(cleanExpandChunk)
        embedding = create_embedding(cleanExpandChunk)
        logger.debug(str(embedding))
        docId = file_path+'_chunk_{}'.format(i)
        docJson = {"docName": file_path, "chunkId": i, "originalText": cleanExpandChunk, 'pageLocation': page_number, 
        'processedTimestamp':timestamp, 'type': 'document', 'stage': 3, 'contentId': contentId}
        for key in meta_json.keys():
            docJson[key] = meta_json[key]
        pinecone_vectors.append((docId, embedding, docJson))
        # When we reach the end of a page, increment the page_number
        if i+1 == sum(page_lengths[:page_number]):
            page_number += 1
        if len(pinecone_vectors) % 100 == 0:
            logger.debug("Upserting batch of 100 vectors...")
            upsert_response = index.upsert(vectors=pinecone_vectors)
            pinecone_vectors = []
    if len(pinecone_vectors) > 0:
        logger.debug("Upserting remaining vectors...")
        upsert_response = index.upsert(vectors=pinecone_vectors)
        pinecone_vectors = []
              
    logger.debug(f"Upserting finishing to pinecone")


def read_jsoncontent(bucket_name, file_name):
    # Instantiate the Cloud Storage client
    storage_client = storage.Client()
    # Retrieve the file from Cloud Storage
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Read the file contents as a JSON object
    try:
        file_contents = blob.download_as_text()
        data_json = json.loads(file_contents)
    except Exception as e:
        logger.debug(f"Got an error when read the json file: {file_name}")
        return {}

    return data_json



def expand_chunk(chunk, article):
    start_index = article.find(chunk)
    if start_index == -1:
        return None 
    
    punctuation = {'.', '!', '?', ':'}
    
    end_index_forward = start_index + len(chunk)
    while end_index_forward < len(article) and article[end_index_forward] not in punctuation:
        end_index_forward += 1

    start_index_backward = start_index
    while start_index_backward > 0 and article[start_index_backward - 1] not in punctuation:
        start_index_backward -= 1
    
    chunkExpand = article[start_index_backward:end_index_forward + 1]
    return chunkExpand

def create_response(message, code):
    """
    Helper function to create a Flask Response object.
    Args:
        message (str): Response message.
        code (int): HTTP status code.
    Returns:
        Flask Response object
    """

    response = jsonify({'code': code, 'response': message})
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,DELETE")
    return response


def check_file_exists(bucket, file_name):
    blob = bucket.blob(file_name)
    return blob.exists()