import base64
import requests
import json
from openai import OpenAI
from google.cloud import storage
from google.cloud import firestore
from gcp import *
# in deployment using the following:
logger = gcp_logger()
PROJECT = gcp_project_id()
func_conf = gcp_get_config()
project_number = gcp_project_number(PROJECT)
OPENAI_API_KEY = gcp_get_secret(project_number,func_conf.get('openai_api_key', 'openai_api_key_name' ))

def read_collection_from_firestore(document_name, collection_name='mindmap_prompt_collection'):
    try:
        db = firestore.Client(project=PROJECT)

        # Get the document
        doc_ref = db.collection(collection_name).document(document_name)
        doc = doc_ref.get()

        # Check if the document exists
        if doc.exists:
            return doc.to_dict()
        else:
            logger.warning(f'No such document: {document_name} in collection: {collection_name}')
            return None
    except Exception as e:
        # Log the exception
        logger.error(f'An error occurred: {e}')
        return None

def encode_image_from_gs(file_name, bucket_name):
    '''
    Function to encode an image from Google Cloud Storage to base64.

    Inputs:
        - file_name (str): Name of the image file in Google Cloud Storage.
        - bucket_name (str): Name of the Google Cloud Storage bucket.

    Output:
        - base64_string (str): Base64 encoded string of the image.
    '''

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Read the bytes of the image data from the blob
    bytes_data = blob.download_as_bytes()

    # Encode the bytes data to base64
    base64_string = base64.b64encode(bytes_data).decode('utf-8')

    return base64_string

def detect_highest_hierarchy_nodes_with_gpt4(file_name, 
                                             bucket_name, 
                                             open_api_key=OPENAI_API_KEY):
    """
    Detects the highest hierarchy nodes in a mind map image using GPT-4's vision capabilities.

    This function takes an image file stored in a Google Cloud Storage bucket and uses the OpenAI GPT-4 API to analyze the mind map. It determines the top-level nodes based on visual indicators such as font size, color, boldness, and layer separation. The function returns the analysis as a JSON string.

    Parameters:
    file_name (str): The name of the image file in the Google Cloud Storage bucket.
    bucket_name (str): The name of the Google Cloud Storage bucket where the image is stored.
    open_api_key (str): The API key for accessing OpenAI's GPT-4 API.

    Returns:
    dict: A dictionary parsed from the JSON string returned by the GPT-4 API. This dictionary contains the highest hierarchy nodes of the mind map. If the top-level nodes are indiscernible, the function returns {"highest_hierarchy_nodes":"no"}.
    """

    document_name = 'mindmap_prompt_detect_highest_hierarchy_v_1'
    document = read_collection_from_firestore(document_name)
    prompt = document.get('prompt')

    base64_image_string = encode_image_from_gs(file_name, bucket_name)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_api_key}"
    }

    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
                "response_format": {"type": "json_object"},
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image_string}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"HTTP Error: {response.status_code} - {response.reason}")

        response_data = response.json()
        if 'choices' in response_data and 'message' in response_data['choices'][0] and 'content' in response_data['choices'][0]['message']:
            json_response = response_data['choices'][0]['message']['content']
            final_response = json.loads(json_response)
            return final_response
        else:
            raise ValueError("The response is not in the expected format.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {e}")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from response.")
        raise

def detect_unclear_backbone_with_gpt4(file_name, bucket_name, open_api_key=OPENAI_API_KEY):
    """
    Analyzes a mind map image to determine the presence of a 'clear backbone' using GPT-4's vision capabilities.

    This function assesses a mind map image for a central theme that connects all top-level nodes. If the top-level nodes are well-connected and exhibit a coherent flow around a central idea, the mind map is considered to have a 'clear backbone'. Otherwise, it's classified as having an 'unclear backbone'.

    Parameters:
    file_name (str): The name of the image file in the Google Cloud Storage bucket.
    bucket_name (str): The name of the Google Cloud Storage bucket where the image is stored.
    open_api_key (str): The API key for accessing OpenAI's GPT-4 API.

    Returns:
    dict: A dictionary parsed from the JSON string returned by the GPT-4 API. This dictionary indicates the presence of an 'unclear backbone' in the mind map. The response is either {"unclear_backbone": "true"} or {"unclear_backbone": "false"}.

    """
    document_name = 'mindmap_prompt_detect_unclear_backbone_v_1'
    document = read_collection_from_firestore(document_name)
    prompt = document.get('prompt')

    base64_image_string = encode_image_from_gs(file_name, bucket_name)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_api_key}"
    }

    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
                "response_format": {"type": "json_object"},
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image_string}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"HTTP Error: {response.status_code} - {response.reason}")

        response_data = response.json()
        if 'choices' in response_data and 'message' in response_data['choices'][0] and 'content' in response_data['choices'][0]['message']:
            json_response = response_data['choices'][0]['message']['content']
            final_response = json.loads(json_response)
            return final_response
        else:
            raise ValueError("The response is not in the expected format.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {e}")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from response.")
        raise

def detect_single_node_chain_with_gpt4(file_name, bucket_name, open_api_key=OPENAI_API_KEY):
    """
    Analyzes a mind map image to detect the presence of a 'single node chain' pattern using GPT-4's vision capabilities.

    A 'single node chain' is defined as a sequence where three or more nodes are connected in a line, with the middle node(s) having only two connections, one to each adjacent node. This function examines the mind map for such patterns.

    Parameters:
    file_name (str): The name of the image file in the Google Cloud Storage bucket.
    bucket_name (str): The name of the Google Cloud Storage bucket where the image is stored.
    open_api_key (str): The API key for accessing OpenAI's GPT-4 API.

    Returns:
    dict: A dictionary parsed from the JSON string returned by the GPT-4 API. This dictionary indicates the presence or absence of a 'single node chain' in the mind map. The response is either {"single_node_chain": "true"} or {"single_node_chain": "false"}.
    """
    document_name = 'mindmap_prompt_detect_single_node_chain_v_1'
    document = read_collection_from_firestore(document_name)
    prompt = document.get('prompt')

    base64_image_string = encode_image_from_gs(file_name, bucket_name)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_api_key}"
    }

    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
                "response_format": {"type": "json_object"},
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image_string}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"HTTP Error: {response.status_code} - {response.reason}")

        response_data = response.json()
        if 'choices' in response_data and 'message' in response_data['choices'][0] and 'content' in response_data['choices'][0]['message']:
            json_response = response_data['choices'][0]['message']['content']
            final_response = json.loads(json_response)
            return final_response
        else:
            raise ValueError("The response is not in the expected format.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {e}")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from response.")
        raise

def detect_spiderwebbing_with_gpt4(image_name,bucket_name,openai_api_key=OPENAI_API_KEY):
    """
    Analyzes a mind map image to determine the presence of 'spiderwebbing', characterized by curvy or overlapping lines, using GPT-4's vision capabilities.

    This function examines a mind map for complex patterns that resemble a spider's web, which can indicate a dense or complicated information structure.

    Parameters:
    image_name (str): The name of the image file in the Google Cloud Storage bucket.
    bucket_name (str): The name of the Google Cloud Storage bucket where the image is stored.
    openai_api_key (str): The API key for accessing OpenAI's GPT-4 API.

    Returns:
    dict: A dictionary parsed from the JSON string returned by the GPT-4 API. This dictionary indicates the presence or absence of spiderwebbing in the mind map. The response is either {"spiderwebbing": "true"} or {"spiderwebbing": "false"}.
    """
    client = OpenAI(api_key= openai_api_key)
    
    document_name = 'mindmap_prompt_detect_spiderwebbing_v_2'
    document = read_collection_from_firestore(document_name)
    prompt = document.get('prompt')
    
    base64_image_string = encode_image_from_gs(image_name,bucket_name)
    try:
        response = client.chat.completions.create(
          model="gpt-4-vision-preview",
          messages=[
            {
              "role": "user",
              "response_format": {"type": "json_object"},
              "content": [
                {"type": "text", "text": prompt},
                {
                  "type": "image_url",
                  "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image_string}",
                    # "detail": "high"
                  },
                },
              ],
            }
          ],
          max_tokens=300,
        )
        
    except Exception as e:
        raise Exception(f"Error occurred: {e}")
    try:
        response_data = response.choices[0].message.content
        # print(response_data)
        final_response = json.loads(response_data)
        return final_response
    except json.JSONDecodeError:
        raise json.JSONDecodeError("The response could not be parsed as JSON.")
